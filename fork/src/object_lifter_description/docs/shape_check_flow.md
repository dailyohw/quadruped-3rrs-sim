# Launch 파일 작성 전 모양 확인 Flow

이 문서는 `object_lifter_preview.urdf`를 먼저 확인하고, 사용자가 형태를 승인한 다음 launch 파일을 만드는 흐름을 정리한 것입니다.

## 1. 현재 단계의 목표

현재 단계의 목표는 **실제 제어 launch 파일을 만들기 전에 모델 형상과 조인트 축이 맞는지 확인하는 것**입니다. 이 단계에서는 `z_lift_joint`, `roll_joint`, `pitch_joint`가 원하는 방향으로 움직이는지 확인하는 것이 가장 중요합니다.

| 확인 항목 | 기대 동작 |
| --- | --- |
| `z_lift_joint` | 상단 적재 면 전체가 z축 방향으로 위아래 이동합니다. |
| `roll_joint` | 상단 적재 면이 x축 기준으로 기울어집니다. |
| `pitch_joint` | 상단 적재 면이 y축 기준으로 기울어집니다. |
| `top_plate_link` 크기 | 140 mm × 135 mm 정도의 물체 적재 면으로 보입니다. |
| 전체 길이 | 약 230 mm 수준의 preview 비율로 보입니다. |

## 2. workspace에 저장하는 방법

압축 파일을 받은 뒤 ROS 2 workspace의 `src` 폴더 아래에 넣습니다.

```bash
cd ~/ros2_ws/src
unzip ~/Downloads/object_lifter_description_preview.zip
cd ~/ros2_ws
colcon build --packages-select object_lifter_description
source install/setup.bash
```

이미 압축이 풀려 있다면 `object_lifter_description` 폴더만 `~/ros2_ws/src/` 아래로 복사하면 됩니다.

```bash
cp -r object_lifter_description ~/ros2_ws/src/
```

## 3. RViz에서 먼저 확인하는 방법

Gazebo보다 먼저 RViz에서 조인트 방향을 확인하는 편이 좋습니다. RViz에서는 물리 충돌이나 중력 영향 없이 링크와 조인트 방향만 빠르게 볼 수 있기 때문입니다.

터미널 1에서 다음을 실행합니다.

```bash
cd ~/ros2_ws
source install/setup.bash
ros2 run robot_state_publisher robot_state_publisher \
  $(ros2 pkg prefix object_lifter_description)/share/object_lifter_description/urdf/object_lifter_preview.urdf
```

터미널 2에서 joint GUI를 실행합니다.

```bash
source ~/ros2_ws/install/setup.bash
ros2 run joint_state_publisher_gui joint_state_publisher_gui
```

터미널 3에서 RViz를 실행합니다.

```bash
source ~/ros2_ws/install/setup.bash
rviz2
```

RViz에서 `RobotModel` display를 추가하고 fixed frame을 `base_link`로 맞춥니다. 이후 GUI에서 `z_lift_joint`, `roll_joint`, `pitch_joint`를 움직여 방향을 확인합니다.

## 4. Ignition Gazebo 6에서 launch 없이 확인하는 방법

Gazebo 창을 먼저 띄운 뒤, 다른 터미널에서 URDF를 spawn합니다.

```bash
ign gazebo -r empty.sdf
```

다른 터미널에서 다음을 실행합니다.

```bash
source ~/ros2_ws/install/setup.bash
ros2 run ros_ign_gazebo create \
  -file $(ros2 pkg prefix object_lifter_description)/share/object_lifter_description/urdf/object_lifter_preview.urdf \
  -name object_lifter_preview \
  -x 0 -y 0 -z 0.05
```

환경에 따라 패키지명이 `ros_gz_sim`으로 되어 있다면 아래 명령을 사용합니다.

```bash
ros2 run ros_gz_sim create \
  -file $(ros2 pkg prefix object_lifter_description)/share/object_lifter_description/urdf/object_lifter_preview.urdf \
  -name object_lifter_preview \
  -x 0 -y 0 -z 0.05
```

## 5. 사용자가 확인해주면 다음에 만들 launch 구성

형태가 맞다고 확인되면 다음 단계에서 launch 파일을 만들면 됩니다. 그때 추가할 내용은 아래와 같습니다.

| 파일 | 역할 |
| --- | --- |
| `launch/display.launch.py` | RViz 확인용 launch 파일입니다. |
| `launch/gazebo_spawn.launch.py` | Ignition Gazebo 6 실행과 모델 spawn을 한 번에 처리합니다. |
| `config/joint_limits.yaml` | 조인트 limit와 속도 값을 관리합니다. |
| `config/bridge.yaml` | 필요하면 ROS 2와 Ignition Gazebo topic bridge를 설정합니다. |

## 6. 수정이 필요한 경우 알려주면 되는 값

모양을 보고 아래 값 중 하나를 알려주면 URDF를 바로 수정할 수 있습니다.

| 수정 요청 예시 | 수정되는 위치 |
| --- | --- |
| 상단 판을 더 앞으로 보내기 | `top_plate_link` visual/collision origin의 x값 |
| 상단 판을 더 크게/작게 하기 | `top_plate_link` box size |
| 기둥을 더 길게 하기 | `z_slider_link` box height와 `roll_joint` origin z값 |
| z 이동 범위를 늘리기 | `z_lift_joint` limit upper 값 |
| 회전 각도를 키우기 | `roll_joint`, `pitch_joint` limit 값 |
| 베이스를 더 길게 하기 | `base_link` box size x값 |

