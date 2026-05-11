from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = FindPackageShare('object_lifter_description')
    ros_ign_gazebo_share = FindPackageShare('ros_ign_gazebo')

    urdf_file = PathJoinSubstitution([
        package_share,
        'urdf',
        'object_lifter_preview.urdf'
    ])
    world_file = PathJoinSubstitution([
        package_share,
        'worlds',
        'object_lifter_empty.sdf'
    ])

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        arguments=[urdf_file]
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                ros_ign_gazebo_share,
                'launch',
                'ign_gazebo.launch.py'
            ])
        ),
        launch_arguments={
            'ign_args': ['-r ', world_file]
        }.items()
    )

    spawn_entity = Node(
        package='ros_ign_gazebo',
        executable='create',
        name='spawn_object_lifter',
        output='screen',
        arguments=[
            '-name', 'object_lifter',
            '-file', urdf_file,
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.0'
        ]
    )

    return LaunchDescription([
        robot_state_publisher,
        gazebo,
        TimerAction(period=2.0, actions=[spawn_entity]),
    ])
