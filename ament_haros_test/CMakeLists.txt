cmake_minimum_required(VERSION 3.5)
project(ament_haros_test)

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(ament_haros_main main.cpp)
ament_target_dependencies(ament_haros_main rclcpp std_msgs)

install(TARGETS ament_haros_main
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
    find_package(ament_cmake_haros REQUIRED)
    ament_haros()
endif()

ament_package()
