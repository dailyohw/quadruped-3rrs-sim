### Usage

If didn't have a environments, it need to install it.
```bash
sudo apt install ros-humble-robot-localization
```

Open two separate terminals to run the simulation and the teleoperation node.

**Terminal 1: Simulation**
```bash
pixi shell
source install/setup.bash
ros2 launch unitree_go2_sim unitree_go2_launch.py
```

**Terminal 2: Teleoperation**
```bash
pixi shell
source install/setup.bash
python3 go2_teleop_key.py
```

### Features

- **Independent Leg Control**: Unlike the default `teleop_twist_keyboard`, this node allows independent vertical (up/down) control of the front and rear legs.
- **Auto-Height Reset**: When initiating directional movement, the robot automatically resets its height to `0` before executing the motion.
