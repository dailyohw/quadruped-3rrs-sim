cmake_minimum_required(VERSION 3.8)
project(object_lifter_description)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY urdf models docs launch rviz worlds
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/object_lifter_numpad_teleop.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
