# Copyright 2019 eSol, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Add a test to perform static code analysis with HAROS.
#
# :param TESTNAME: the name of the test, default: "haros"
# :type TESTNAME: string
# :param ARGN: the files or directories to check
# :type ARGN: list of strings
#
# @public
#
function(ament_haros)
  cmake_parse_arguments(ARG "" "LANGUAGE;TESTNAME" "INCLUDE_DIRS" ${ARGN})
  if(NOT ARG_TESTNAME)
    set(ARG_TESTNAME "haros")
  endif()

  find_program(ament_haros_BIN NAMES "ament_haros")
  if(NOT ament_haros_BIN)
    message(FATAL_ERROR "ament_haros() could not find program 'ament_haros'")
  endif()

  set(result_file "${AMENT_TEST_RESULTS_DIR}/${PROJECT_NAME}/${ARG_TESTNAME}.xunit.xml")
  set(cmd "${ament_haros_BIN}" "--xunit-file" "${result_file}")
  list(APPEND cmd ${ARG_UNPARSED_ARGUMENTS})
  # if(ARG_INCLUDE_DIRS)
  #   list(APPEND cmd "--include_dirs" "${ARG_INCLUDE_DIRS}")
  # endif()
  # if(ARG_LANGUAGE)
  #   list(APPEND cmd "--language" "${ARG_LANGUAGE}")
  # endif()

  file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/ament_haros")
  ament_add_test(
    "${ARG_TESTNAME}"
    COMMAND ${cmd}
    TIMEOUT 120
    OUTPUT_FILE "${CMAKE_BINARY_DIR}/ament_haros/${ARG_TESTNAME}.txt"
    RESULT_FILE "${result_file}"
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  )
  set_tests_properties(
    "${ARG_TESTNAME}"
    PROPERTIES
    LABELS "haros;linter"
  )
endfunction()
