cmake_minimum_required(VERSION 3.5)

project(ament_cmake_haros NONE)

find_package(ament_cmake_core REQUIRED)
find_package(ament_cmake_test REQUIRED)

# Use ament_virtualenv to create a Python virtualenv in which to run HAROS.
find_package(ament_cmake_virtualenv REQUIRED)
install(FILES requirements.txt
  DESTINATION ${CMAKE_INSTALL_PREFIX}/share/${PROJECT_NAME}
)
ament_generate_virtualenv()

# Build package and provide cmake files to client package.
ament_package(
  CONFIG_EXTRAS "ament_cmake_haros-extras.cmake"
)
install(
  DIRECTORY cmake
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_copyright REQUIRED)
  ament_copyright()

  find_package(ament_cmake_lint_cmake REQUIRED)
  ament_lint_cmake()
endif()
