from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    bridge_enabled = LaunchConfiguration('bridge_enabled')
    start_teleop = LaunchConfiguration('start_teleop')
    use_dual_teleop = LaunchConfiguration('use_dual_teleop')

    z_topic = LaunchConfiguration('z_topic')
    roll_topic = LaunchConfiguration('roll_topic')
    pitch_topic = LaunchConfiguration('pitch_topic')

    return LaunchDescription([
        DeclareLaunchArgument(
            'bridge_enabled',
            default_value='true',
            description='Start ROS <-> Ignition bridge nodes for fork command topics.'
        ),
        DeclareLaunchArgument(
            'start_teleop',
            default_value='true',
            description='Start the combined Go2 + fork keyboard teleop node.'
        ),
        DeclareLaunchArgument(
            'use_dual_teleop',
            default_value='false',
            description='If true, run go2_fork_teleop_dual.py. Otherwise run go2_fork_teleop.py.'
        ),
        DeclareLaunchArgument(
            'z_topic',
            default_value='/object_lifter/z_lift_joint/cmd_pos',
            description='Fork z-lift command topic. Must match the Gazebo JointPositionController topic.'
        ),
        DeclareLaunchArgument(
            'roll_topic',
            default_value='/object_lifter/roll_joint/cmd_pos',
            description='Fork roll command topic. Must match the Gazebo JointPositionController topic.'
        ),
        DeclareLaunchArgument(
            'pitch_topic',
            default_value='/object_lifter/pitch_joint/cmd_pos',
            description='Fork pitch command topic. Must match the Gazebo JointPositionController topic.'
        ),

        # Same bridge style as object_lifter_description/launch/teleop.launch.py.
        # The topic name must be the real Ignition/Gazebo controller topic.
        Node(
            package='ros_ign_bridge',
            executable='parameter_bridge',
            name='go2_fork_z_lift_joint_bridge',
            output='screen',
            condition=IfCondition(bridge_enabled),
            arguments=[
                PythonExpression(["'", z_topic, "@std_msgs/msg/Float64@ignition.msgs.Double'"])
            ],
        ),
        Node(
            package='ros_ign_bridge',
            executable='parameter_bridge',
            name='go2_fork_roll_joint_bridge',
            output='screen',
            condition=IfCondition(bridge_enabled),
            arguments=[
                PythonExpression(["'", roll_topic, "@std_msgs/msg/Float64@ignition.msgs.Double'"])
            ],
        ),
        Node(
            package='ros_ign_bridge',
            executable='parameter_bridge',
            name='go2_fork_pitch_joint_bridge',
            output='screen',
            condition=IfCondition(bridge_enabled),
            arguments=[
                PythonExpression(["'", pitch_topic, "@std_msgs/msg/Float64@ignition.msgs.Double'"])
            ],
        ),

        Node(
            package='unitree_go2_sim',
            executable='go2_fork_teleop.py',
            name='go2_fork_teleop',
            output='screen',
            emulate_tty=True,
            condition=IfCondition(PythonExpression(["'", start_teleop, "' == 'true' and '", use_dual_teleop, "' == 'false'"])),
            parameters=[{
                'z_topic': z_topic,
                'roll_topic': roll_topic,
                'pitch_topic': pitch_topic,
            }],
        ),
        Node(
            package='unitree_go2_sim',
            executable='go2_fork_teleop_dual.py',
            name='go2_fork_teleop_dual',
            output='screen',
            emulate_tty=True,
            condition=IfCondition(PythonExpression(["'", start_teleop, "' == 'true' and '", use_dual_teleop, "' == 'true'"])),
            parameters=[{
                'fork_backend': 'ros',
                'z_topic': z_topic,
                'roll_topic': roll_topic,
                'pitch_topic': pitch_topic,
                'gz_z_topic': z_topic,
                'gz_roll_topic': roll_topic,
                'gz_pitch_topic': pitch_topic,
            }],
        ),
    ])
