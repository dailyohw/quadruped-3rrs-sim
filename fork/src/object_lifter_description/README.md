# object_lifter_description

이 패키지는 사용자가 제공한 사진과 치수를 바탕으로 만든 **object lifter preview용 ROS 2 description 패키지**입니다. 현재 버전은 RViz에서의 조인트 방향 확인, Ignition Gazebo 6/Fortress에서의 모델 spawn, 그리고 숫자패드 기반 조인트 위치 제어까지 포함합니다.

> 현재 모델은 CAD mesh 기반이 아니라 box와 cylinder primitive로 만든 preview 모델입니다. 따라서 실제 외형보다 단순하지만, Gazebo에서 링크 구조, 조인트 축, 제어 topic을 빠르게 확인하기 좋습니다.

## 1. 모델 좌표계와 치수 가정

URDF의 기본 단위는 meter입니다. 사용자가 준 140 mm, 135 mm 치수는 각각 0.140 m, 0.135 m로 변환해 적용했습니다. 전체 세로 길이 220~260 mm는 preview에서 base plate 길이 230 mm로 잡았습니다.

| 항목 | 적용값 | 설명 |
|---|---:|---|
| 전체 길이 방향 | x축 | 스케치에서 앞뒤 길이 방향입니다. |
| 좌우 폭 방향 | y축 | 물체가 올라가는 판의 가로 방향입니다. |
| 위아래 방향 | z축 | 리프트 이동 방향입니다. |
| 상단 물체 적재 면 | x 135 mm, y 140 mm, 두께 6 mm | 사용자가 준 140 mm × 135 mm를 URDF 좌표계에 맞춰 배치했습니다. |
| 베이스 판 | x 230 mm, y 180 mm, 두께 10 mm | 전체 세로 길이 220~260 mm의 중간값에 맞춘 preview 값입니다. |
| z축 리프트 이동 | 0~120 mm | `z_lift_joint`의 prismatic 이동 범위입니다. |
| x축 회전 | ±30° | `roll_joint`입니다. |
| y축 회전 | ±30° | `pitch_joint`입니다. |

## 2. 링크와 조인트 구조

URDF는 closed-loop 기구를 직접 표현하기 어렵기 때문에, 이 모델은 Gazebo에서 안정적으로 확인할 수 있도록 **직렬 체인 구조**로 단순화했습니다. 실제 기구가 2축 짐벌 또는 병렬 링크 형태라면, 외형 확인 이후 mimic joint, plugin, SDF constraint 등을 검토하는 방식으로 확장하는 것이 좋습니다.

| 순서 | 이름 | 타입 | 역할 |
|---:|---|---|---|
| 1 | `base_link` | link | 바닥에 놓이는 베이스 판입니다. |
| 2 | `lower_mount_link` | fixed child link | 베이스 위의 하부 마운트 블록입니다. |
| 3 | `z_slider_link` | prismatic child link | z축으로 위아래 이동하는 기둥입니다. |
| 4 | `roll_link` | revolute child link | x축 회전 중심입니다. |
| 5 | `pitch_link` | revolute child link | y축 회전 중심입니다. |
| 6 | `top_plate_link` | fixed child link | 물체를 올리는 상단 판입니다. |

## 3. 빌드 방법

ROS 2 workspace가 `~/ros2_ws`라고 가정하면, 다음 위치에 패키지를 넣으면 됩니다. 사용자의 현재 workspace가 `/mnt/data/2026_1/fork`라면 `~/ros2_ws` 대신 해당 경로를 사용하면 됩니다.

```bash
mkdir -p ~/ros2_ws/src
cp -r object_lifter_description ~/ros2_ws/src/
cd ~/ros2_ws
colcon build --packages-select object_lifter_description
source install/setup.bash
```

패키지의 주요 파일 구조는 아래와 같습니다.

```text
object_lifter_description/
├── CMakeLists.txt
├── package.xml
├── launch/
│   ├── display.launch.py
│   ├── gazebo_ros_ign.launch.py
│   ├── gazebo_ros_gz.launch.py
│   └── teleop.launch.py
├── rviz/
│   └── object_lifter_preview.rviz
├── scripts/
│   └── object_lifter_numpad_teleop.py
├── urdf/
│   └── object_lifter_preview.urdf
└── worlds/
    └── object_lifter_empty.sdf
```

## 4. RViz에서 모양과 조인트 방향 확인

RViz에서는 `joint_state_publisher_gui`를 사용하여 `z_lift_joint`, `roll_joint`, `pitch_joint`가 의도한 방향으로 움직이는지 먼저 확인할 수 있습니다.

```bash
ros2 launch object_lifter_description display.launch.py
```

이 launch 파일은 `robot_state_publisher`, `joint_state_publisher_gui`, `rviz2`를 함께 실행합니다. RViz의 fixed frame은 `base_link`로 설정되어 있습니다.

## 5. Ignition Gazebo 6에서 spawn

Ignition Gazebo 6/Fortress 환경에서는 다음 launch 파일을 사용합니다. 이 launch 파일은 빈 월드를 열고, 2초 뒤 `object_lifter`라는 이름으로 URDF 모델을 spawn합니다.

```bash
ros2 launch object_lifter_description gazebo_ros_ign.launch.py
```

환경에 따라 `ros_gz_sim` 계열 launch가 필요한 경우에는 대체 launch 파일을 사용할 수 있습니다.

```bash
ros2 launch object_lifter_description gazebo_ros_gz.launch.py
```

## 6. 숫자패드 teleop 제어

현재 URDF에는 Ignition Gazebo의 `JointPositionController` 플러그인이 각 제어 조인트마다 추가되어 있습니다. teleop 노드는 각 조인트의 목표 위치를 조금씩 증감하고 ROS 2 `std_msgs/Float64` topic으로 publish합니다. `teleop.launch.py`는 기본적으로 `ros_ign_bridge`를 함께 실행하여 이 ROS topic을 Ignition Gazebo의 `ignition.msgs.Double` command topic으로 전달합니다.

| 조인트 | Ignition command topic | 기본 범위 | 기본 증분 |
|---|---|---:|---:|
| `z_lift_joint` | `/object_lifter/z_lift_joint/cmd_pos` | 0.000~0.120 m | 0.005 m |
| `roll_joint` | `/object_lifter/roll_joint/cmd_pos` | -0.5236~0.5236 rad | 2° |
| `pitch_joint` | `/object_lifter/pitch_joint/cmd_pos` | -0.5236~0.5236 rad | 2° |

Gazebo가 실행 중인 상태에서 별도 터미널을 열고 아래 명령을 실행합니다.

```bash
source ~/ros2_ws/install/setup.bash
ros2 launch object_lifter_description teleop.launch.py
```

숫자패드 사용 시에는 가능하면 **NumLock을 켠 상태**에서 사용합니다. 키 입력은 teleop launch를 실행한 터미널에 focus가 있을 때만 동작합니다. 이번 버전은 `ros2 launch`로 실행해도 `/dev/tty`를 통해 키 입력을 읽도록 수정되어, stdin이 TTY가 아니라는 이유로 바로 종료되지 않습니다.

| 키 | 동작 |
|---:|---|
| `8` | `z_lift_joint` 위로 이동 |
| `2` | `z_lift_joint` 아래로 이동 |
| `4` | `roll_joint` 양의 방향으로 회전 |
| `6` | `roll_joint` 음의 방향으로 회전 |
| `7` | `pitch_joint` 양의 방향으로 회전 |
| `9` | `pitch_joint` 음의 방향으로 회전 |
| `5` | 현재 목표 위치 유지 |
| `0` | 세 조인트 목표 위치를 모두 0으로 초기화 |
| `h` | 도움말 출력 |
| `Ctrl-C` | teleop 종료 |

## 7. 기존 Go2 teleop과의 병행 실행

object lifter teleop은 Go2의 기존 `w/s/a/d/q/e`, `t/b/y/n`, `r/f/z/x/c/v/0` 키 구조와 분리하기 위해 숫자패드 중심으로 만들었습니다. 다만 terminal focus는 한 번에 하나의 process만 받을 수 있으므로, Go2 teleop과 object lifter teleop을 동시에 띄울 때는 각각 다른 터미널에서 실행하고 필요한 터미널에 focus를 옮겨가며 조작하는 방식이 안전합니다.

나중에 Go2 앞쪽에 object lifter를 부착할 때도 이 패키지의 teleop 노드는 별도 독립 노드로 유지할 수 있습니다. 이후 통합 단계에서는 TF parent link, mounting joint, namespace, controller topic prefix만 정리하면 됩니다.

## 8. 문제 해결 참고

Ignition에서 조인트가 움직이지 않는다면 먼저 Gazebo가 모델을 `object_lifter`라는 이름으로 spawn했는지 확인합니다. 현재 controller topic은 `/object_lifter/...` prefix로 고정되어 있으므로, spawn 이름이나 topic prefix를 바꾸면 `teleop.launch.py`의 `ign_topic_prefix` 또는 URDF의 controller topic도 함께 맞춰야 합니다.

| 증상 | 확인할 항목 |
|---|---|
| Gazebo 모델은 보이지만 조인트가 움직이지 않음 | `ign topic -l` 또는 `gz topic -l`에서 `/object_lifter/.../cmd_pos` topic이 보이는지 확인합니다. |
| teleop 실행은 되지만 아무 키도 반응하지 않음 | teleop terminal에 focus가 있는지, NumLock이 켜져 있는지 확인합니다. |
| `ros_ign_bridge`를 찾지 못함 | Fortress 계열에서는 `ros_ign_bridge`가 필요합니다. 설치가 어렵다면 `ros2 launch object_lifter_description teleop.launch.py bridge_enabled:=false use_ign_transport:=true`로 CLI 직접 publish 모드를 시도할 수 있습니다. |
| 움직임이 너무 빠르거나 느림 | `scripts/object_lifter_numpad_teleop.py`의 `step` 값 또는 URDF의 `p_gain`, `d_gain`을 조정합니다. |
