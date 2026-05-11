#!/usr/bin/env python3
"""
Numpad teleop node for the object_lifter preview model.

This node is intentionally independent from any quadruped or mobile-base teleop node.
It reads numpad-like single-key input from the focused terminal, updates the target
positions of the object lifter's three controllable joints, and publishes commands
for Ignition Gazebo JointPositionController plugins.

Default key mapping:
  8 / 2 : z_lift_joint up / down
  4 / 6 : roll_joint left / right
  7 / 9 : pitch_joint forward / backward
  5     : hold current positions
  0     : reset all joints to zero
  h     : print help
  Ctrl-C: exit
"""

import math
import select
import shutil
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass
from typing import Dict, Optional, TextIO

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64


@dataclass(frozen=True)
class JointConfig:
    name: str
    lower: float
    upper: float
    step: float
    unit: str


class ObjectLifterNumpadTeleop(Node):
    def __init__(self) -> None:
        super().__init__('object_lifter_numpad_teleop')

        self.declare_parameter('model_name', 'object_lifter')
        self.declare_parameter('use_ign_transport', True)
        self.declare_parameter('publish_ros_topics', True)
        self.declare_parameter('ros_topic_prefix', '/object_lifter')
        self.declare_parameter('ign_topic_prefix', '/object_lifter')
        self.declare_parameter('ign_executable', '')
        self.declare_parameter('command_timeout_sec', 1.0)

        self.model_name = self.get_parameter('model_name').get_parameter_value().string_value
        self.use_ign_transport = self.get_parameter('use_ign_transport').get_parameter_value().bool_value
        self.publish_ros_topics = self.get_parameter('publish_ros_topics').get_parameter_value().bool_value
        self.ros_topic_prefix = self.get_parameter('ros_topic_prefix').get_parameter_value().string_value.rstrip('/')
        self.ign_topic_prefix = self.get_parameter('ign_topic_prefix').get_parameter_value().string_value.rstrip('/')
        self.command_timeout_sec = self.get_parameter('command_timeout_sec').get_parameter_value().double_value

        requested_ign_executable = self.get_parameter('ign_executable').get_parameter_value().string_value
        self.ign_executable = self._resolve_ign_executable(requested_ign_executable)

        self.joints: Dict[str, JointConfig] = {
            'z': JointConfig('z_lift_joint', 0.000, 0.120, 0.005, 'm'),
            'roll': JointConfig('roll_joint', -0.5236, 0.5236, math.radians(2.0), 'rad'),
            'pitch': JointConfig('pitch_joint', -0.5236, 0.5236, math.radians(2.0), 'rad'),
        }
        self.positions: Dict[str, float] = {
            config.name: 0.0 for config in self.joints.values()
        }

        self.publishers_by_joint: Dict[str, object] = {}
        if self.publish_ros_topics:
            for config in self.joints.values():
                topic = f'{self.ros_topic_prefix}/{config.name}/cmd_pos'
                self.publishers_by_joint[config.name] = self.create_publisher(Float64, topic, 10)

        self._print_help()

    def _resolve_ign_executable(self, requested: str) -> Optional[str]:
        if requested:
            return requested
        for candidate in ('ign', 'gz'):
            path = shutil.which(candidate)
            if path:
                return candidate
        return None

    def _print_help(self) -> None:
        self.get_logger().info('\n'
            'Object lifter numpad teleop\n'
            '----------------------------------------\n'
            '  8 : lift up          2 : lift down\n'
            '  4 : roll left        6 : roll right\n'
            '  7 : pitch forward    9 : pitch backward\n'
            '  5 : hold current target positions\n'
            '  0 : reset all joint targets to zero\n'
            '  h : show this help\n'
            '  Ctrl-C : exit\n'
            '----------------------------------------\n'
            f'ROS command prefix: {self.ros_topic_prefix}\n'
            f'Ignition command prefix: {self.ign_topic_prefix}\n'
        )
        if self.use_ign_transport and self.ign_executable is None:
            self.get_logger().warning(
                'Ignition transport publishing is enabled, but neither `ign` nor `gz` was found in PATH. '
                'The node will still publish ROS Float64 command topics.'
            )

    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _adjust_joint(self, key: str, delta: float) -> None:
        config = self.joints[key]
        current = self.positions[config.name]
        new_value = self._clamp(current + delta, config.lower, config.upper)
        self.positions[config.name] = new_value
        self._publish_joint(config, reason=f'{config.name} -> {new_value:.4f} {config.unit}')
        self._log_positions(f'{config.name} command')

    def _reset(self) -> None:
        for config in self.joints.values():
            self.positions[config.name] = 0.0
        self._publish_all(reason='reset all joints')

    def _hold(self) -> None:
        self._publish_all(reason='hold current targets')

    def _publish_all(self, reason: str) -> None:
        for config in self.joints.values():
            self._publish_joint(config, reason=reason)
        self._log_positions(reason)

    def _publish_joint(self, config: JointConfig, reason: str) -> None:
        value = self.positions[config.name]

        if self.publish_ros_topics and config.name in self.publishers_by_joint:
            msg = Float64()
            msg.data = float(value)
            self.publishers_by_joint[config.name].publish(msg)

        if self.use_ign_transport and self.ign_executable is not None:
            topic = f'{self.ign_topic_prefix}/{config.name}/cmd_pos'
            self._publish_ign_double(topic, value)

        self.get_logger().debug(reason)

    def _publish_ign_double(self, topic: str, value: float) -> None:
        if self.ign_executable is None:
            return

        command = [
            self.ign_executable,
            'topic',
            '--once',
            '-t', topic,
            '-m', 'ignition.msgs.Double',
            '-p', f'data: {value:.8f}',
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=self.command_timeout_sec,
            )
            if completed.returncode != 0:
                fallback_command = [
                    self.ign_executable,
                    'topic',
                    '-t', topic,
                    '-m', 'ignition.msgs.Double',
                    '-p', f'data: {value:.8f}',
                ]
                subprocess.run(
                    fallback_command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=self.command_timeout_sec,
                )
        except subprocess.TimeoutExpired:
            self.get_logger().warning(
                f'Timed out while publishing Ignition command to {topic}. '
                'If Gazebo still moves, this warning can be ignored; otherwise try use_ign_transport:=false and a ROS bridge/controller setup.'
            )
        except OSError as exc:
            self.get_logger().warning(f'Failed to run Ignition topic command: {exc}')

    def _log_positions(self, reason: str) -> None:
        z = self.positions['z_lift_joint']
        roll = self.positions['roll_joint']
        pitch = self.positions['pitch_joint']
        self.get_logger().info(
            f'{reason}: z={z:.3f} m, roll={math.degrees(roll):.1f} deg, pitch={math.degrees(pitch):.1f} deg'
        )

    def handle_key(self, key: str) -> None:
        if key == '8':
            self._adjust_joint('z', self.joints['z'].step)
        elif key == '2':
            self._adjust_joint('z', -self.joints['z'].step)
        elif key == '4':
            self._adjust_joint('roll', self.joints['roll'].step)
        elif key == '6':
            self._adjust_joint('roll', -self.joints['roll'].step)
        elif key == '7':
            self._adjust_joint('pitch', self.joints['pitch'].step)
        elif key == '9':
            self._adjust_joint('pitch', -self.joints['pitch'].step)
        elif key == '5':
            self._hold()
        elif key == '0':
            self._reset()
        elif key.lower() == 'h':
            self._print_help()
        elif key in ('\x03', '\x04'):
            raise KeyboardInterrupt
        elif key not in ('', '\n', '\r'):
            self.get_logger().debug(f'Ignored key: {repr(key)}')


def open_keyboard_stream(node: Node) -> TextIO:
    """Return a terminal stream suitable for raw key input.

    When a Python node is started by `ros2 launch`, stdin is often not a TTY even
    if the launch command was started from a terminal. In that case, /dev/tty is
    usually still the controlling terminal and can be used for teleop input.
    """
    if sys.stdin.isatty():
        return sys.stdin

    try:
        keyboard_stream = open('/dev/tty', 'r', buffering=1)
        node.get_logger().info('stdin is not interactive; using /dev/tty for keyboard input.')
        return keyboard_stream
    except OSError as exc:
        node.get_logger().error(
            'No interactive terminal is available for keyboard input. '
            'Run this node from a real terminal with `ros2 run object_lifter_description object_lifter_numpad_teleop.py`, '
            f'or check terminal/launch environment. Original error: {exc}'
        )
        raise


def read_single_key(input_stream: TextIO, timeout_sec: float = 0.1) -> str:
    ready, _, _ = select.select([input_stream], [], [], timeout_sec)
    if not ready:
        return ''
    return input_stream.read(1)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ObjectLifterNumpadTeleop()

    keyboard_stream: Optional[TextIO] = None
    old_settings = None
    try:
        keyboard_stream = open_keyboard_stream(node)
        keyboard_fd = keyboard_stream.fileno()
        old_settings = termios.tcgetattr(keyboard_fd)
        tty.setcbreak(keyboard_fd)

        node.get_logger().info('Teleop is ready. Keep this terminal focused and press numpad keys.')
        node._publish_all(reason='initial command')

        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            key = read_single_key(keyboard_stream, timeout_sec=0.05)
            if key:
                node.handle_key(key)
    except KeyboardInterrupt:
        node.get_logger().info('Stopping object lifter numpad teleop.')
    except OSError:
        pass
    finally:
        if keyboard_stream is not None and old_settings is not None:
            termios.tcsetattr(keyboard_stream.fileno(), termios.TCSADRAIN, old_settings)
        if keyboard_stream is not None and keyboard_stream is not sys.stdin:
            keyboard_stream.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
