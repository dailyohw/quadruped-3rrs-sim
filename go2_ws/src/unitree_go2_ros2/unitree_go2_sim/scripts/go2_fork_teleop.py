#!/usr/bin/env python3
"""
Combined keyboard teleop for Unitree Go2 + fork mechanism simulation.

This node publishes:
  - geometry_msgs/msg/Twist to /cmd_vel for Go2 driving
  - std_msgs/msg/Float64 to fork JointPositionController command topics

Default fork topics:
  - /object_lifter/z_lift_joint/cmd_pos
  - /object_lifter/roll_joint/cmd_pos
  - /object_lifter/pitch_joint/cmd_pos

Run example:
  python3 go2_fork_teleop.py

Or after copying into a ROS 2 package scripts directory:
  ros2 run <package_name> go2_fork_teleop.py
"""

import math
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
        Go2 + Fork Combined Keyboard Teleop
============================================================
Go2 driving:
  w / x        : forward / backward
  q / e        : strafe left / strafe right
  a / d        : rotate left / rotate right
  space or m   : stop robot velocity

Fork control (numpad-style):
  8 / 2        : fork Z up / down
  4 / 6        : fork roll left / right
  7 / 9        : fork pitch forward / backward
  5            : hold current fork positions
  0            : reset fork pose to zero

Speed / step tuning:
  u / j        : increase / decrease linear speed
  i / k        : increase / decrease angular speed
  o / l        : increase / decrease fork step size

Other:
  p            : print current command values
  h            : print this help
  Ctrl-C       : quit
============================================================
"""


class Go2ForkTeleop(Node):
    def __init__(self):
        super().__init__('go2_fork_teleop')

        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('z_topic', '/object_lifter/z_lift_joint/cmd_pos')
        self.declare_parameter('roll_topic', '/object_lifter/roll_joint/cmd_pos')
        self.declare_parameter('pitch_topic', '/object_lifter/pitch_joint/cmd_pos')

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
        z_topic = self.get_parameter('z_topic').value
        roll_topic = self.get_parameter('roll_topic').value
        pitch_topic = self.get_parameter('pitch_topic').value

        self.cmd_pub = self.create_publisher(Twist, cmd_vel_topic, 10)
        self.z_pub = self.create_publisher(Float64, z_topic, 10)
        self.roll_pub = self.create_publisher(Float64, roll_topic, 10)
        self.pitch_pub = self.create_publisher(Float64, pitch_topic, 10)

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

        self.get_logger().info('Go2 + fork combined teleop started.')
        self.get_logger().info(f'Publishing Go2 velocity to: {cmd_vel_topic}')
        self.get_logger().info(f'Publishing fork z/roll/pitch to: {z_topic}, {roll_topic}, {pitch_topic}')

    @staticmethod
    def clamp(value, low, high):
        return max(low, min(high, value))

    def publish_cmd_vel(self):
        msg = Twist()
        msg.linear.x = self.vx
        msg.linear.y = self.vy
        msg.linear.z = 0.0
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = self.wz
        self.cmd_pub.publish(msg)

    def publish_fork(self):
        z_msg = Float64()
        roll_msg = Float64()
        pitch_msg = Float64()
        z_msg.data = self.z_pos
        roll_msg.data = self.roll_pos
        pitch_msg.data = self.pitch_pos
        self.z_pub.publish(z_msg)
        self.roll_pub.publish(roll_msg)
        self.pitch_pub.publish(pitch_msg)

    def stop_robot(self):
        self.vx = 0.0
        self.vy = 0.0
        self.wz = 0.0
        self.publish_cmd_vel()

    def reset_fork(self):
        self.roll_pos = 0.0
        self.pitch_pos = 0.0
        self.publish_fork()

    def print_state(self):
        print(
            f'Go2: vx={self.vx:.3f}, vy={self.vy:.3f}, wz={self.wz:.3f} | '
            f'Fork: z={self.z_pos:.3f} m, roll={self.roll_pos:.3f} rad '
            f'({math.degrees(self.roll_pos):.1f} deg), pitch={self.pitch_pos:.3f} rad '
            f'({math.degrees(self.pitch_pos):.1f} deg) | '
            f'Speed: linear={self.linear_speed:.2f}, angular={self.angular_speed:.2f}, '
            f'z_step={self.z_step:.3f}, angle_step={self.angle_step:.3f}'
        )

    def handle_key(self, key):
        # Go2 driving controls
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
        
        # Fork controls (numpad-style)
        elif key == '8':
            self.z_pos = self.clamp(self.z_pos + self.z_step, self.z_min, self.z_max)
            self.publish_fork()
        elif key == '2':
            self.z_pos = self.clamp(self.z_pos - self.z_step, self.z_min, self.z_max)
            self.publish_fork()
        elif key == '4':
            self.roll_pos = self.clamp(self.roll_pos + self.angle_step, self.roll_min, self.roll_max)
            self.publish_fork()
        elif key == '6':
            self.roll_pos = self.clamp(self.roll_pos - self.angle_step, self.roll_min, self.roll_max)
            self.publish_fork()
        elif key == '7':
            self.pitch_pos = self.clamp(self.pitch_pos + self.angle_step, self.pitch_min, self.pitch_max)
            self.publish_fork()
        elif key == '9':
            self.pitch_pos = self.clamp(self.pitch_pos - self.angle_step, self.pitch_min, self.pitch_max)
            self.publish_fork()
        elif key == '5':
            self.publish_fork()
        elif key == '0':
            self.reset_fork()
        
        # Speed/step tuning
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
        
        # Other
        elif key == 'p':
            self.print_state()
        elif key.lower() == 'h':
            print(HELP_TEXT)

        # Print state after relevant commands
        if key in ('w', 'x', 'q', 'e', 'a', 'd'):
            self.publish_cmd_vel()
            self.print_state()
        elif key in ('8', '2', '4', '6', '7', '9', '5', '0', 'u', 'j', 'i', 'k', 'o', 'l'):
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
    node = Go2ForkTeleop()

    print(HELP_TEXT)
    node.publish_fork()
    node.publish_cmd_vel()

    try:
        while rclpy.ok():
            key = get_key(settings)
            if key == '\x03':  # Ctrl-C
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
