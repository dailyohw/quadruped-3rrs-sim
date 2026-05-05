#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose

class BodyUpDown(Node):
    def __init__(self):
        super().__init__('body_updown')
        self.z_min  = -0.05   # 가장 낮은 높이 오프셋 (m)
        self.z_max  =  0.05   # 가장 높은 높이 오프셋 (m)
        self.period = 2.0     # 한 주기 (초)
        self.dt     = 0.05    # 20 Hz
        self.elapsed = 0.0

        self.pub = self.create_publisher(Pose, '/body_pose', 10)
        self.create_timer(self.dt, self.tick)
        self.get_logger().info('Started body up-down motion')

    def tick(self):
        # 코사인으로 부드러운 위아래 운동
        z = self.z_min + (self.z_max - self.z_min) * \
            (1 - math.cos(2 * math.pi * self.elapsed / self.period)) / 2

        msg = Pose()
        msg.position.z = z
        msg.orientation.w = 1.0   # 자세 유지 (수평)
        self.pub.publish(msg)

        self.elapsed += self.dt

def main():
    rclpy.init()
    rclpy.spin(BodyUpDown())

if __name__ == '__main__':
    main()
