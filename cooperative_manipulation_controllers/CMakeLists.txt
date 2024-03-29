cmake_minimum_required(VERSION 3.0.2)
project(cooperative_manipulation_controllers)


## Compile as C++11, supported in ROS Kinetic and newer
add_compile_options(-std=c++17)

## Find catkin macros and libraries
## if COMPONENTS list like find_package(catkin REQUIRED COMPONENTS xyz)
## is used, also find other catkin packages
find_package(catkin REQUIRED COMPONENTS
  controller_interface
  pluginlib
  roscpp
  rospy
  std_msgs
  dynamic_reconfigure
  eigen_conversions
  franka_hw
  franka_gripper
  geometry_msgs
  hardware_interface
  joint_limits_interface
  tf
  tf_conversions
  message_generation
  realtime_tools
  urdf
  visualization_msgs
  franka_example_controllers
)

find_package(Eigen3 REQUIRED)
find_package(Franka 0.9.0 QUIET)
if(NOT Franka_FOUND)
  find_package(Franka 0.8.0 REQUIRED)
endif()


# generate_dynamic_reconfigure_options(
#   cfg/compliance_param.cfg
#   cfg/desired_mass_param.cfg
#   cfg/dual_arm_compliance_param.cfg
#   cfg/teleop_param.cfg
#   cfg/teleop_gripper_param.cfg
# )


## System dependencies are found with CMake's conventions
# find_package(Boost REQUIRED COMPONENTS system)


## Uncomment this if the package has a setup.py. This macro ensures
## modules and global scripts declared therein get installed
## See http://ros.org/doc/api/catkin/html/user_guide/setup_dot_py.html
#catkin_python_setup()

################################################
## Declare ROS messages, services and actions ##
################################################

## To declare and build messages, services or actions from within this
## package, follow these steps:
## * Let MSG_DEP_SET be the set of packages whose message types you use in
##   your messages/services/actions (e.g. std_msgs, actionlib_msgs, ...).
## * In the file package.xml:
##   * add a build_depend tag for "message_generation"
##   * add a build_depend and a exec_depend tag for each package in MSG_DEP_SET
##   * If MSG_DEP_SET isn't empty the following dependency has been pulled in
##     but can be declared for certainty nonetheless:
##     * add a exec_depend tag for "message_runtime"
## * In this file (CMakeLists.txt):
##   * add "message_generation" and every package in MSG_DEP_SET to
##     find_package(catkin REQUIRED COMPONENTS ...)
##   * add "message_runtime" and every package in MSG_DEP_SET to

##   * uncomment the add_*_files sections below as needed
##     and list every .msg/.srv/.action file to be processed
##   * uncomment the generate_messages entry below
##   * add every package in MSG_DEP_SET to generate_messages(DEPENDENCIES ...)

catkin_python_setup()

## Generate messages in the 'msg' folder
add_message_files(
  FILES
  SingularityAvoidance.msg
  WorkspaceViolation.msg
)
## Generate services in the 'srv' folder
# add_service_files(
#   FILES
#   Service1.srv
#   Service2.srv
# )

## Generate actions in the 'action' folder
# add_action_files(
#   FILES
#   Action1.action
#   Action2.action
# )

## Generate added messages and services with any dependencies listed here
generate_messages(
  DEPENDENCIES
  std_msgs
)

################################################
## Declare ROS dynamic reconfigure parameters ##
################################################

## To declare and build dynamic reconfigure parameters within this
## package, follow these steps:
## * In the file package.xml:
##   * add a build_depend and a exec_depend tag for "dynamic_reconfigure"
## * In this file (CMakeLists.txt):
##   * add "dynamic_reconfigure" to
##     find_package(catkin REQUIRED COMPONENTS ...)
##   * uncomment the "generate_dynamic_reconfigure_options" section below
##     and list every .cfg file to be processed

## Generate dynamic reconfigure parameters in the 'cfg' folder
# generate_dynamic_reconfigure_options(
#   cfg/DynReconf1.cfg
#   cfg/DynReconf2.cfg
# )

###################################
## catkin specific configuration ##
###################################
## The catkin_package macro generates cmake config files for your package
## Declare things to be passed to dependent projects
## INCLUDE_DIRS: uncomment this if your package contains header files
## LIBRARIES: libraries you create in this project that dependent projects also need
## CATKIN_DEPENDS: catkin_packages dependent projects also need
## DEPENDS: system dependencies of this project that dependent projects also need
catkin_package(
  INCLUDE_DIRS include
  LIBRARIES cooperative_manipulation_controllers
  CATKIN_DEPENDS 
    roscpp
    rospy
    std_msgs
    controller_interface
    dynamic_reconfigure
    eigen_conversions
    franka_hw
    franka_gripper
    geometry_msgs
    hardware_interface
    joint_limits_interface
    tf
    tf_conversions
    message_runtime
    pluginlib
    realtime_tools
    urdf
    visualization_msgs
    franka_example_controllers
  DEPENDS Franka
  )



###########
## Build ##
###########

## Specify additional locations of header files
## Your package locations should be listed before other locations
include_directories( 
  include 
  ${catkin_INCLUDE_DIRS}
  ${EIGEN3_INCLUDE_DIR}
  #${GAZEBO_INCLUDE_DIRS}
)

add_library(cooperative_manipulation_controllers
  src/franka_joint_impedance_control_hardware.cpp
  src/franka_cartesian_impedance_control_hardware.cpp
)

## Declare a C++ library

## Add cmake target dependencies of the library
## as an example, code may need to be generated before libraries
## either from message generation or dynamic reconfigure
# add_dependencies(cooperative_manipulation_controllers 
#       ${${PROJECT_NAME}_EXPORTED_TARGETS} 
#       ${catkin_EXPORTED_TARGETS})
add_dependencies(cooperative_manipulation_controllers
  ${${PROJECT_NAME}_EXPORTED_TARGETS}
  ${catkin_EXPORTED_TARGETS}
)

## Declare a C++ executable
## With catkin_make all packages are built within a single CMake context
# ## The recommended prefix ensures that target names across packages don't collide
# add_executable(cooperative_manipulation_controllers src/franka_joint_torque_controller.cpp)

## Rename C++ executable without prefix
## The above recommended prefix causes long target names, the following renames the
## target back to the shorter version for ease of user use
## e.g. "rosrun someones_pkg node" instead of "rosrun someones_pkg someones_pkg_node"
# set_target_properties(${PROJECT_NAME}_node PROPERTIES OUTPUT_NAME node PREFIX "")

## Add cmake target dependencies of the executable
## same as for the library above
# add_dependencies(${PROJECT_NAME}_node ${${PROJECT_NAME}_EXPORTED_TARGETS} ${catkin_EXPORTED_TARGETS})

## Specify libraries to link a library or executable target against
target_link_libraries(cooperative_manipulation_controllers PUBLIC
  ${Franka_LIBRARIES}
  ${catkin_LIBRARIES}
)

target_include_directories(cooperative_manipulation_controllers SYSTEM PUBLIC
  ${Franka_INCLUDE_DIRS}
  ${EIGEN3_INCLUDE_DIRS}
  ${catkin_INCLUDE_DIRS}
)

target_include_directories(cooperative_manipulation_controllers PUBLIC
  include
)

# link_directories(${GAZEBO_LIBRARY_DIRS})
# list(APPEND CMAKE_CXX_FLAGS "${GAZEBO_CXX_FLAGS}")
#############
## Install ##
#############

# all install targets should use catkin DESTINATION variables
# See http://ros.org/doc/api/catkin/html/adv_user_guide/variables.html

## Mark executable scripts (Python etc.) for installation
## in contrast to setup.py, you can choose the destination
# catkin_install_python(PROGRAMS
#   scripts/my_python_script
#   DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
# )
## Installation

install(FILES cooperative_manipulation_controllers_plugin.xml
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)




## Mark executables for installation
## See http://docs.ros.org/melodic/api/catkin/html/howto/format1/building_executables.html
#catkin_install_python(PROGRAMS scripts/cooperative_manipulation_controllers/franka_impedance_control_sim.py
#                               scripts/cooperative_manipulation_controllers/franka_rviz_markers.py
#                               scripts/cooperative_manipulation_controllers/universal_robot_admittance_control.py
#                      DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
#                      )

## Mark libraries for installation
## See http://docs.ros.org/melodic/api/catkin/html/howto/format1/building_libraries.html
# install(TARGETS ${PROJECT_NAME}
#   ARCHIVE DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION}
#   LIBRARY DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION}
#   RUNTIME DESTINATION ${CATKIN_GLOBAL_BIN_DESTINATION}
# )

## Mark cpp header files for installation
# install(DIRECTORY include/${PROJECT_NAME}/
#   DESTINATION ${CATKIN_PACKAGE_INCLUDE_DESTINATION}
#   FILES_MATCHING PATTERN "*.h"
#   PATTERN ".svn" EXCLUDE
# )

## Mark other files for installation (e.g. launch and bag files, etc.)
# install(FILES
#   # myfile1
#   # myfile2
#   DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
# )



#############
## Testing ##
#############

## Add gtest based cpp test target and link libraries
# catkin_add_gtest(${PROJECT_NAME}-test test/test_cooperative_manipulation_controllers.cpp)
# if(TARGET ${PROJECT_NAME}-test)
#   target_link_libraries(${PROJECT_NAME}-test ${PROJECT_NAME})
# endif()

## Add folders to be run by python nosetests
# catkin_add_nosetests(test)
