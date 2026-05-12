### Usage

If didn't have a environments, it need to install it.
```bash
sudo apt install ros-humble-robot-localization
```

Open two separate terminals to run the simulation and the teleoperation node.

**Terminal 1: Simulation**
```bash
source install/setup.bash
ros2 launch unitree_go2_sim unitree_go2_launch.py
```

**Terminal 2: Teleoperation**
```bash
source install/setup.bash
python3 go2_int_teleop_key.py
```

## Go2 Keyboard Teleop Controls

### Movement
| Key (Opposites) | Action |
| :---: | :--- |
| `w` / `s` | Forward / Backward |
| `a` / `d` | Strafe Left / Right |
| `q` / `e` | Rotate Left / Right (Yaw) |
| *Any other key* | Stop |

### Speed Adjustment
| Key (Up / Down) | Action |
| :---: | :--- |
| `t` / `b` | Linear speed +10% / -10% |
| `y` / `n` | Angular speed +10% / -10% |

### Body Pose
> Applied immediately and maintained while moving.

| Key (Up / Down) | Action |
| :---: | :--- |
| `r` / `f` | Body height Up / Down |
| `z` / `x` | Front legs Up / Down |
| `c` / `v` | Rear legs Up / Down |
| `h` / `j` | Left legs Up / Down |
| `k` / `l` | Right legs Up / Down |
| `0` | Reset pose to neutral |

### Miscellaneous
| Key | Action |
| :---: | :--- |
| `5` | Print help menu |
| `Ctrl-C` | Quit |

