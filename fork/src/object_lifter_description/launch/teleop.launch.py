from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_ign_transport = LaunchConfiguration('use_ign_transport')
    publish_ros_topics = LaunchConfiguration('publish_ros_topics')
    bridge_enabled = LaunchConfiguration('bridge_enabled')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_ign_transport',
            default_value='false',
            description='Use direct ign/gz CLI publish. Normally false.'
        ),
        DeclareLaunchArgument(
            'publish_ros_topics',
            default_value='true',
            description='Publish ROS Float64 command topics.'
        ),
        DeclareLaunchArgument(
            'bridge_enabled',
            default_value='true',
            description='Bridge ROS Float64 topics to Ignition Double topics.'
        ),

        Node(
            package='ros_ign_bridge',
            executable='parameter_bridge',
            name='object_lifter_z_lift_joint_bridge',
            output='screen',
            condition=IfCondition(bridge_enabled),
            arguments=[
                '/object_lifter/z_lift_joint/cmd_pos@std_msgs/msg/Float64@ignition.msgs.Double'
            ],
        ),
        Node(
            package='ros_ign_bridge',
            executable='parameter_bridge',
            name='object_lifter_roll_joint_bridge',
            output='screen',
            condition=IfCondition(bridge_enabled),
            arguments=[
                '/object_lifter/roll_joint/cmd_pos@std_msgs/msg/Float64@ignition.msgs.Double'
            ],
        ),
        Node(
            package='ros_ign_bridge',
            executable='parameter_bridge',
            name='object_lifter_pitch_joint_bridge',
            output='screen',
            condition=IfCondition(bridge_enabled),
            arguments=[
                '/object_lifter/pitch_joint/cmd_pos@std_msgs/msg/Float64@ignition.msgs.Double'
            ],
        ),

        Node(
            package='object_lifter_description',
            executable='object_lifter_numpad_teleop.py',
            name='object_lifter_numpad_teleop',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'use_ign_transport': use_ign_transport,
                'publish_ros_topics': publish_ros_topics,
                'ros_topic_prefix': '/object_lifter',
                'ign_topic_prefix': '/object_lifter',
            }],
        ),
    ])

