#!/usr/bin/env python3
"""
Go2 + Fork combined keyboard teleop with dual fork command backend.

Why this version exists:
  - Go2 usually listens to ROS 2 /cmd_vel.
  - Ignition/Gazebo JointPositionController may listen on Gazebo Transport topics,
    not directly on ROS 2 topics unless a ros_gz_bridge/ros_ign_bridge is running.
  - Therefore this script publishes fork commands to ROS 2 Float64 topics and,
    optionally, also sends the same command through the gz/ign command-line topic tool.

Recommended first test:
  python3 go2_fork_teleop_dual.py --ros-args -p fork_backend:=both

If fork starts moving with fork_backend:=both but not with fork_backend:=ros,
then the fork controller is Gazebo-transport only and needs a bridge for pure ROS control.
"""

import math
import shutil
import subprocess
import select
import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float64


HELP_TEXT = r"""
============================================================
        Go2 + Fork Combined Keyboard Teleop, Dual Backend
============================================================
Go2 driving:
  w / x        : forward / backward
  q / e        : strafe left / strafe right
  a / d        : rotate left / rotate right
  space or m   : stop robot velocity

Fork control:
  r / f        : fork Z up / down
  y / h        : fork roll + / -
  t / g        : fork pitch + / -
  c            : reset fork pose to zero

Speed / step tuning:
  u / j        : increase / decrease linear speed
  i / k        : increase / decrease angular speed
  o / l        : increase / decrease fork step size

Other:
  p            : print current command values
  Ctrl-C       : quit
============================================================
"""


class Go2ForkTeleopDual(Node):
    def __init__(self):
        super().__init__('go2_fork_teleop_dual')

        self.declare_parameter('cmd_vel_topic', '/cmd_vel')

        # ROS-side fork topics. These work only if the fork controller command topics
        # are exposed to ROS 2 directly or through ros_gz_bridge/ros_ign_bridge.
        self.declare_parameter('z_topic', '/object_lifter/z_lift_joint/cmd_pos')
        self.declare_parameter('roll_topic', '/object_lifter/roll_joint/cmd_pos')
        self.declare_parameter('pitch_topic', '/object_lifter/pitch_joint/cmd_pos')

        # Gazebo-side fork topics. In the current project these are usually the same
        # textual topic names, but they are transported by gz/ign instead of ROS 2.
        self.declare_parameter('gz_z_topic', '/object_lifter/z_lift_joint/cmd_pos')
        self.declare_parameter('gz_roll_topic', '/object_lifter/roll_joint/cmd_pos')
        self.declare_parameter('gz_pitch_topic', '/object_lifter/pitch_joint/cmd_pos')

        # ros, gz, or both. Use both while debugging.
        self.declare_parameter('fork_backend', 'both')

        self.declare_parameter('linear_speed', 0.35)
        self.declare_parameter('strafe_speed', 0.25)
        self.declare_parameter('angular_speed', 0.8)

        self.declare_parameter('z_step', 0.02)
        self.declare_parameter('angle_step', 0.05)
        self.declare_parameter('z_min', -0.05)
        self.declare_parameter('z_max', 0.45)
        self.declare_parameter('roll_min', -0.75)
        self.declare_parameter('roll_max', 0.75)
        self.declare_parameter('pitch_min', -0.75)
        self.declare_parameter('pitch_max', 0.75)

        cmd_vel_topic = self.get_parameter('cmd_vel_topic').value
        self.z_topic = self.get_parameter('z_topic').value
        self.roll_topic = self.get_parameter('roll_topic').value
        self.pitch_topic = self.get_parameter('pitch_topic').value
        self.gz_z_topic = self.get_parameter('gz_z_topic').value
        self.gz_roll_topic = self.get_parameter('gz_roll_topic').value
        self.gz_pitch_topic = self.get_parameter('gz_pitch_topic').value
        self.fork_backend = str(self.get_parameter('fork_backend').value).lower()

        self.cmd_pub = self.create_publisher(Twist, cmd_vel_topic, 10)
        self.z_pub = self.create_publisher(Float64, self.z_topic, 10)
        self.roll_pub = self.create_publisher(Float64, self.roll_topic, 10)
        self.pitch_pub = self.create_publisher(Float64, self.pitch_topic, 10)

        self.linear_speed = float(self.get_parameter('linear_speed').value)
        self.strafe_speed = float(self.get_parameter('strafe_speed').value)
        self.angular_speed = float(self.get_parameter('angular_speed').value)
        self.z_step = float(self.get_parameter('z_step').value)
        self.angle_step = float(self.get_parameter('angle_step').value)

        self.z_min = float(self.get_parameter('z_min').value)
        self.z_max = float(self.get_parameter('z_max').value)
        self.roll_min = float(self.get_parameter('roll_min').value)
        self.roll_max = float(self.get_parameter('roll_max').value)
        self.pitch_min = float(self.get_parameter('pitch_min').value)
        self.pitch_max = float(self.get_parameter('pitch_max').value)

        self.vx = 0.0
        self.vy = 0.0
        self.wz = 0.0
        self.z_pos = 0.0
        self.roll_pos = 0.0
        self.pitch_pos = 0.0

        self.gz_cli = self.detect_gazebo_cli()
        self.get_logger().info('Go2 + fork dual-backend teleop started.')
        self.get_logger().info(f'Go2 cmd_vel topic: {cmd_vel_topic}')
        self.get_logger().info(f'Fork backend: {self.fork_backend}')
        self.get_logger().info(f'ROS fork topics: {self.z_topic}, {self.roll_topic}, {self.pitch_topic}')
        self.get_logger().info(f'Gazebo fork topics: {self.gz_z_topic}, {self.gz_roll_topic}, {self.gz_pitch_topic}')
        self.get_logger().info(f'Detected Gazebo CLI: {self.gz_cli if self.gz_cli else "none"}')

    @staticmethod
    def detect_gazebo_cli():
        if shutil.which('gz'):
            return 'gz'
        if shutil.which('ign'):
            return 'ign'
        return None

    @staticmethod
    def clamp(value, low, high):
        return max(low, min(high, value))

    def publish_cmd_vel(self):
        msg = Twist()
        msg.linear.x = self.vx
        msg.linear.y = self.vy
        msg.angular.z = self.wz
        self.cmd_pub.publish(msg)

    def publish_fork_ros(self):
        z_msg = Float64(); z_msg.data = float(self.z_pos)
        roll_msg = Float64(); roll_msg.data = float(self.roll_pos)
        pitch_msg = Float64(); pitch_msg.data = float(self.pitch_pos)
        self.z_pub.publish(z_msg)
        self.roll_pub.publish(roll_msg)
        self.pitch_pub.publish(pitch_msg)

    def publish_one_gazebo(self, topic, value):
        if not self.gz_cli:
            return False

        if self.gz_cli == 'gz':
            msg_type_candidates = ['gz.msgs.Double', 'ignition.msgs.Double']
        else:
            msg_type_candidates = ['ignition.msgs.Double', 'gz.msgs.Double']

        for msg_type in msg_type_candidates:
            cmd = [
                self.gz_cli, 'topic',
                '-t', topic,
                '-m', msg_type,
                '-p', f'data: {float(value)}',
            ]
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=0.7,
                    check=False,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                continue
        return False

    def publish_fork_gazebo(self):
        ok_z = self.publish_one_gazebo(self.gz_z_topic, self.z_pos)
        ok_r = self.publish_one_gazebo(self.gz_roll_topic, self.roll_pos)
        ok_p = self.publish_one_gazebo(self.gz_pitch_topic, self.pitch_pos)
        return ok_z and ok_r and ok_p

    def publish_fork(self):
        if self.fork_backend in ('ros', 'both'):
            self.publish_fork_ros()
        if self.fork_backend in ('gz', 'ign', 'gazebo', 'both'):
            ok = self.publish_fork_gazebo()
            if not ok and self.fork_backend not in ('ros',):
                self.get_logger().warn(
                    'Gazebo fork publish failed. Check whether gz/ign exists and whether the fork topic names are correct.',
                    throttle_duration_sec=2.0,
                )

    def stop_robot(self):
        self.vx = 0.0
        self.vy = 0.0
        self.wz = 0.0
        self.publish_cmd_vel()

    def reset_fork(self):
        self.z_pos = 0.0
        self.roll_pos = 0.0
        self.pitch_pos = 0.0
        self.publish_fork()

    def print_state(self):
        print(
            f'Go2: vx={self.vx:.3f}, vy={self.vy:.3f}, wz={self.wz:.3f} | '
            f'Fork: z={self.z_pos:.3f} m, roll={self.roll_pos:.3f} rad '
            f'({math.degrees(self.roll_pos):.1f} deg), pitch={self.pitch_pos:.3f} rad '
            f'({math.degrees(self.pitch_pos):.1f} deg) | backend={self.fork_backend}'
        )

    def handle_key(self, key):
        fork_changed = False

        if key == 'w':
            self.vx = self.linear_speed
        elif key == 'x':
            self.vx = -self.linear_speed
        elif key == 'q':
            self.vy = self.strafe_speed
        elif key == 'e':
            self.vy = -self.strafe_speed
        elif key == 'a':
            self.wz = self.angular_speed
        elif key == 'd':
            self.wz = -self.angular_speed
        elif key in (' ', 'm'):
            self.stop_robot()
        elif key == 'r':
            self.z_pos = self.clamp(self.z_pos + self.z_step, self.z_min, self.z_max)
            fork_changed = True
        elif key == 'f':
            self.z_pos = self.clamp(self.z_pos - self.z_step, self.z_min, self.z_max)
            fork_changed = True
        elif key == 'y':
            self.roll_pos = self.clamp(self.roll_pos + self.angle_step, self.roll_min, self.roll_max)
            fork_changed = True
        elif key == 'h':
            self.roll_pos = self.clamp(self.roll_pos - self.angle_step, self.roll_min, self.roll_max)
            fork_changed = True
        elif key == 't':
            self.pitch_pos = self.clamp(self.pitch_pos + self.angle_step, self.pitch_min, self.pitch_max)
            fork_changed = True
        elif key == 'g':
            self.pitch_pos = self.clamp(self.pitch_pos - self.angle_step, self.pitch_min, self.pitch_max)
            fork_changed = True
        elif key == 'c':
            self.reset_fork()
            self.print_state()
            return
        elif key == 'u':
            self.linear_speed = min(self.linear_speed + 0.05, 1.50)
            self.strafe_speed = min(self.strafe_speed + 0.05, 1.50)
        elif key == 'j':
            self.linear_speed = max(self.linear_speed - 0.05, 0.05)
            self.strafe_speed = max(self.strafe_speed - 0.05, 0.05)
        elif key == 'i':
            self.angular_speed = min(self.angular_speed + 0.10, 2.50)
        elif key == 'k':
            self.angular_speed = max(self.angular_speed - 0.10, 0.10)
        elif key == 'o':
            self.z_step = min(self.z_step + 0.005, 0.10)
            self.angle_step = min(self.angle_step + 0.01, 0.30)
        elif key == 'l':
            self.z_step = max(self.z_step - 0.005, 0.005)
            self.angle_step = max(self.angle_step - 0.01, 0.01)
        elif key == 'p':
            self.print_state()
            return

        if key in ('w', 'x', 'q', 'e', 'a', 'd'):
            self.publish_cmd_vel()
        if fork_changed:
            self.publish_fork()
        if key in ('w', 'x', 'q', 'e', 'a', 'd', 'r', 'f', 'y', 'h', 't', 'g', 'u', 'j', 'i', 'k', 'o', 'l'):
            self.print_state()


def get_key(settings, timeout=0.05):
    tty.setraw(sys.stdin.fileno())
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    key = sys.stdin.read(1) if ready else ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


def main(args=None):
    settings = termios.tcgetattr(sys.stdin)
    rclpy.init(args=args)
    node = Go2ForkTeleopDual()

    print(HELP_TEXT)
    node.publish_fork()
    node.publish_cmd_vel()

    try:
        while rclpy.ok():
            key = get_key(settings)
            if key == '\x03':
                break
            if key:
                node.handle_key(key)
            node.publish_cmd_vel()
            rclpy.spin_once(node, timeout_sec=0.0)
    finally:
        node.stop_robot()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.shutdown()
        print('\nTeleop finished. Robot velocity stopped.')


if __name__ == '__main__':
    main()
