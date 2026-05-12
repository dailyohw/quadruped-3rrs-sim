#!/usr/bin/env python3
"""
Go2 Keyboard Teleop
  Movement:
    w / s        Forward / Backward
    a / d        Strafe Left / Right
    q / e        Rotate Left / Right (yaw)
    anything else -> stop

  Speed adjust:
    t / b        Linear speed  +10% / -10%
    y / n        Angular speed +10% / -10%

  Body pose (only while stopped):
    r / f        Body height Up / Down
    z / x        Front legs  Up / Down
    c / v        Rear  legs  Up / Down
    0            Reset pose to 0

  Ctrl-C        Quit
"""
import sys
import math
import time
import threading
import termios
import tty

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, Twist

# ── params ────────────────────────────────────────────────
BODY_LENGTH  = 0.6     # Go2 body length (m) for pitch calc

LIN_SPEED    = 0.5
ANG_SPEED    = 1.0

Z_STEP       = 0.005   # m per keypress (target 조정 단위)
BODY_LIMIT   = 0.10
LEG_LIMIT    = 0.10

INTERP_SPEED = 0.08    # m/s — 현재값 → 목표값 보간 속도
TIMER_DT     = 0.05    # 20 Hz
# ─────────────────────────────────────────────────────────

moveBindings = {
    'w': ( 1,  0,  0),
    's': (-1,  0,  0),
    'a': ( 0,  1,  0),
    'd': ( 0, -1,  0),
    'q': ( 0,  0,  1),
    'e': ( 0,  0, -1),
}

speedBindings = {
    't': (1.1, 1.0),
    'b': (0.9, 1.0),
    'y': (1.0, 1.1),
    'n': (1.0, 0.9),
}


def get_key(settings):
    tty.setraw(sys.stdin.fileno())
    key = sys.stdin.read(1)
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

def save_terminal_settings():
    return termios.tcgetattr(sys.stdin)

def restore_terminal_settings(old_settings):
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def step_toward(cur, tgt, step):
    diff = tgt - cur
    if abs(diff) <= step:
        return tgt
    return cur + step * (1.0 if diff > 0 else -1.0)

def euler_to_quat(roll, pitch, yaw):
    cr, sr = math.cos(roll  / 2), math.sin(roll  / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw   / 2), math.sin(yaw   / 2)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


class Go2PosePublisher(Node):
    """
    body_pose를 20 Hz로 상시 발행.
    목표값(tgt_*)을 설정하면 현재값(cur_*)이 INTERP_SPEED로 부드럽게 따라감.
    기본(이동 중) 목표는 모두 0.
    """
    def __init__(self):
        super().__init__('go2_pose_pub')
        self.pub = self.create_publisher(Pose, '/body_pose', 10)

        # 목표값 (사용자가 키로 조정)
        self.tgt_body = 0.0
        self.tgt_front = 0.0
        self.tgt_rear  = 0.0

        # 현재 발행값 (목표값으로 보간 중)
        self.cur_body  = 0.0
        self.cur_front = 0.0
        self.cur_rear  = 0.0

        self._lock = threading.Lock()
        self.create_timer(TIMER_DT, self._publish)

    def _publish(self):
        step = INTERP_SPEED * TIMER_DT
        with self._lock:
            # 현재값을 목표값 쪽으로 한 스텝 이동
            self.cur_body  = step_toward(self.cur_body,  self.tgt_body,  step)
            self.cur_front = step_toward(self.cur_front, self.tgt_front, step)
            self.cur_rear  = step_toward(self.cur_rear,  self.tgt_rear,  step)

            z     = self.cur_body + (self.cur_front + self.cur_rear) / 2.0
            pitch = math.atan2(self.cur_front - self.cur_rear, BODY_LENGTH)

        qx, qy, qz, qw = euler_to_quat(0.0, pitch, 0.0)
        p = Pose()
        p.position.z    = z
        p.orientation.x = qx
        p.orientation.y = qy
        p.orientation.z = qz
        p.orientation.w = qw
        self.pub.publish(p)

    def adjust(self, field, delta, limit):
        with self._lock:
            setattr(self, field, clamp(getattr(self, field) + delta, -limit, limit))

    def reset_targets(self):
        with self._lock:
            self.tgt_body = self.tgt_front = self.tgt_rear = 0.0

    def wait_until_leveled(self, tol=0.003, timeout=5.0):
        """cur_* 가 실제로 0 에 도달할 때까지 폴링 대기."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                done = (abs(self.cur_body)  < tol and
                        abs(self.cur_front) < tol and
                        abs(self.cur_rear)  < tol)
            if done:
                return
            time.sleep(TIMER_DT)

    def status(self):
        with self._lock:
            z     = self.cur_body + (self.cur_front + self.cur_rear) / 2.0
            pitch = math.degrees(math.atan2(self.cur_front - self.cur_rear, BODY_LENGTH))
            return z, self.tgt_body, self.tgt_front, self.tgt_rear, pitch


def main():
    settings = save_terminal_settings()
    rclpy.init()

    vel_node = rclpy.create_node('go2_vel_pub')
    vel_pub  = vel_node.create_publisher(Twist, '/cmd_vel', 10)
    pose_node = Go2PosePublisher()

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(vel_node)
    executor.add_node(pose_node)
    threading.Thread(target=executor.spin, daemon=True).start()

    lin_speed = LIN_SPEED
    ang_speed = ANG_SPEED
    vx = vy = wz = 0.0
    is_moving = False

    poseBindings = {
        'r': ('tgt_body',  +Z_STEP, BODY_LIMIT),
        'f': ('tgt_body',  -Z_STEP, BODY_LIMIT),
        'z': ('tgt_front', +Z_STEP, LEG_LIMIT),
        'x': ('tgt_front', -Z_STEP, LEG_LIMIT),
        'c': ('tgt_rear',  +Z_STEP, LEG_LIMIT),
        'v': ('tgt_rear',  -Z_STEP, LEG_LIMIT),
    }

    print(__doc__)
    print(f"speed: linear={lin_speed:.2f} m/s  angular={ang_speed:.2f} rad/s")

    def publish_vel():
        t = Twist()
        t.linear.x  = vx
        t.linear.y  = vy
        t.angular.z = wz
        vel_pub.publish(t)

    try:
        while True:
            key = get_key(settings)

            if key == '\x03':
                break

            if key in moveBindings:
                # 무조건 0으로 복귀 후 이동
                pose_node.reset_targets()
                print("Leveling to 0 ...")
                pose_node.wait_until_leveled()
                print("Moving.")

                mx, my, mw = moveBindings[key]
                vx = mx * lin_speed
                vy = my * lin_speed
                wz = mw * ang_speed
                is_moving = True
                publish_vel()

            elif key in speedBindings:
                lm, am = speedBindings[key]
                lin_speed *= lm
                ang_speed *= am
                print(f"speed: linear={lin_speed:.2f} m/s  angular={ang_speed:.2f} rad/s")

            elif key in poseBindings:
                if is_moving:
                    print("Stop first before adjusting pose.")
                else:
                    field, delta, limit = poseBindings[key]
                    pose_node.adjust(field, delta, limit)
                    z, tb, tf, tr, pitch = pose_node.status()
                    print(f"pose: z={z:+.3f}m  "
                          f"body={tb:+.3f}  front={tf:+.3f}  rear={tr:+.3f}  pitch={pitch:+.1f}deg")

            elif key == '0':
                pose_node.reset_targets()
                print("pose target -> 0")

            else:
                vx = vy = wz = 0.0
                is_moving = False
                publish_vel()

    finally:
        vx = vy = wz = 0.0
        publish_vel()
        pose_node.reset_targets()
        rclpy.shutdown()
        restore_terminal_settings(settings)


if __name__ == '__main__':
    main()
