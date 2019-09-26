#!/usr/bin/env python3

# Copyright 2014-2015 Open Source Robotics Foundation, Inc.
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

import argparse
from collections import defaultdict
import os
from shutil import which, rmtree, copyfile
import subprocess
import sys
import time
import json
import re
from xml.etree.cElementTree import ElementTree

def find_ros_packages(path, as_stack = False):
    """
    Find ROS packages inside a folder.
    :param path: [str] File system path to search.
    :returns: [dict] Dictionary of [str]package_name -> [str]package_path.
    """
    resources = {} # the packages
    basename = os.path.basename
    for d, dirs, files in os.walk(path, topdown=True, followlinks=True):
        if ('CATKIN_IGNORE' in files or
            'COLCON_IGNORE' in files or
            'AMENT_IGNORE' in files
        ):
            del dirs[:]
            continue  # leaf
        if 'package.xml' in files:
            # parse package.xml and decide if it matches the search criteria
            root = ElementTree(None, os.path.join(d, 'package.xml'))
            is_metapackage = root.find('./export/metapackage') is not None
            if not is_metapackage:
                resource_name = root.findtext('name').strip(' \n\r\t')
                if resource_name not in resources:
                    resources[resource_name] = d
                del dirs[:]
                continue  # leaf
        if 'manifest.xml' in files:
            # resource_name = basename(d)
            # if resource_name not in resources:
            #     resources[resource_name] = d
            del dirs[:]
            continue  # leaf
        if 'rospack_nosubdirs' in files:
            del dirs[:]
            continue   # leaf
        # remove hidden dirs (esp. .svn/.git)
        [dirs.remove(di) for di in dirs if di[0] == '.']
    # ^ for d, dirs, files in os.walk(path, topdown=True, followlinks=True)
    return resources
# ^ def find_ros_packages(path)

def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Perform static code analysis using HAROS.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'paths',
        nargs='*',
        default=[os.curdir],
        help='Files and/or directories to be checked. '
             'Directories are searched recursively for ROS/ROS2 package(s)')
    parser.add_argument(
        '--xunit-file',
        help='Generate a xunit compliant XML file')
    args = parser.parse_args(argv)

    # Prepare a temporary directory for running HAROS
    haros_tmp_dir = '/tmp/ament_haros'
    try:
        if os.path.exists(haros_tmp_dir):
            rmtree(haros_tmp_dir)
        os.mkdir(haros_tmp_dir)
        os.mkdir(haros_tmp_dir + '/haros_home')
        os.mkdir(haros_tmp_dir + '/haros_data')
    except:
        print("Trying to create a HAROS tmp folders failed.")
        return 1
    #

    # Prepare a virtual environment with HAROS installed
    python_bin = which('python2')
    if not python_bin:
        print("Could not find 'python2' executable - python2.x not installed",
              file=sys.stderr)
        return 1
    pip_bin = which('pip')
    if not pip_bin:
        print("Could not find 'pip' executable - pip not installed",
              file=sys.stderr)
        return 1
    venv_bin = which('virtualenv')
    if not venv_bin:
        # try to install it
        try:
            p = subprocess.Popen([pip_bin, 'install', 'virtualenv'],
                                 stderr=subprocess.PIPE)
            output = p.communicate()[1]
        except subprocess.CalledProcessError as e:
            print("Trying to install virtualenv failed %d: %s" %
                  (e.returncode, e), file=sys.stderr)
            return 1
        # since we may run pip as non-root,
        # the package may be installed in the users' site packages folder
        try:
            venv_info = subprocess.check_output([pip_bin, 'show', 'virtualenv']).decode('utf-8')
            venv_loc = re.search("Location: (.*)", venv_info).group(1)
            venv_bin = venv_loc + '/virtualenv'
        except:
            print("Trying to find virtualenv installation failed", file=sys.stderr)
            return 1
        #
    #
    try:
        p = subprocess.Popen(
            [
                python_bin,
                venv_bin,
                '-p',
                python_bin,
                haros_tmp_dir + '/venv'
            ],
            stderr=subprocess.PIPE
        )
        output = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("Trying to create virtual environment failed: %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1
    #
    try:
        p = subprocess.Popen(['bash', '-c', "'source "+haros_tmp_dir+"/venv/bin/activate'"],
            stderr=subprocess.PIPE
        )
        output = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("Trying to activate virtual environment failed: %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1
    #
    try:
        p = subprocess.Popen(['pip', 'install', 'haros', 'haros-plugins'],
            stderr=subprocess.PIPE
        )
        output = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("Failed to install haros and plugins: %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1
    #
    haros_bin = which('haros')
    if not haros_bin:
        print("Could not find 'haros' executable", file=sys.stderr)
        return 1

    #cmd = [haros_bin]
    # ^ TODO: the pip release of HAROS is not yet compatible with ROS2/ament
    # work spaces. So we'll download the latest version from github.
    download_cmd = [
        "wget",
        "-O",
        haros_tmp_dir + "/haros.zip",
        "https://github.com/git-afsantos/haros/archive/master.zip"
    ]
    try:
        p = subprocess.Popen(download_cmd, stderr=subprocess.PIPE)
        output = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("Trying to download HAROS failed with error code %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1
    #
    unzip_cmd = [
        "unzip",
        "-qq",
        haros_tmp_dir + "/haros.zip",
        "-d",
        haros_tmp_dir
    ]
    try:
        p = subprocess.Popen(unzip_cmd, stderr=subprocess.PIPE)
        output = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("Trying to unzip HAROS failed with error code %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1
    #
    cmd = [python_bin, haros_tmp_dir + '/haros-master/haros-runner.py']
    package_dir = os.path.abspath(args.paths[0])
    # If we were pointed at a package folder,
    # find the ROS2 workspace root.
    try:
        workspace_dir = package_dir[0:package_dir.rindex('/src/')]
    except ValueError:
        # Check if we are already in the workspace root directory.
        if os.path.exists(package_dir + '/src/') == False:
            print("Failed to detect ROS workspace root folder",
                  file=sys.stderr)
            return 1
        # else: workspace_dir is already the workspace root directory
        workspace_dir = package_dir
    #
    packages = find_ros_packages(package_dir)
    if len(packages) == 0:
        print("Failed to find any ROS packages to analyze",
              file=sys.stderr)
        return 1
    #
    # Generate HAROS project.yaml file to direct HAROS to the package/project
    with open(haros_tmp_dir + '/ament_haros_project.yaml', "w") as f:
        f.write('%YAML 1.1\n')
        f.write('---\n')
        f.write('project: ament_haros_project\n')
        f.write('packages:\n')
        for p in packages:
            f.write('    - %s\n' % p)
        #
    #

    cmd.extend(['--cwd', workspace_dir]) # TODO: Support multiple paths.
    cmd.extend(['--home', haros_tmp_dir + '/haros_home'])
    cmd.extend(['analyse'])
    cmd.extend(['--project-file', haros_tmp_dir + '/ament_haros_project.yaml'])
    cmd.extend(['--data-dir', haros_tmp_dir + '/haros_data'])
    cmd.extend(['--junit-xml-output'])
    # print(*cmd)
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = p.communicate()
    except subprocess.CalledProcessError as e:
        print("The invocation of 'haros' failed with error code %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1
    #

    # Check if the output XML file is written
    xunit_file = haros_tmp_dir + '/haros_data/data/ament_haros_project/compliance/ament_haros_project.xml'
    if not os.path.exists(xunit_file):
        print("HAROS failed to write xUnit (XML) output file")
        return 1
    #

    # Read the resulting XML output files
    error_count = 0
    tree = ElementTree(None, xunit_file)
    testsuites = tree.getroot()
    for testsuite in testsuites:
        for testcase in testsuite:
            id = testcase.attrib.get('id', 'UNKNOWN ISSUE')
            failure = testcase[0]
            severity = failure.attrib.get('type', 'FAILURE')
            data = failure.text.split('\n')
            msg = data[1]
            category = data[2][10:] # "Category: [...]"
            file = data[3][6:] # "File: [...]"
            line = data[4][6:] # "Line: [...]"
            print('[%s:%s]: (%s: %s) %s' % (file, line, severity, id, msg),
                  file=sys.stderr)
            error_count += 1
        # ^ for testcase in testsuite
    # ^ for testsuite in root[0]

    # output summary
    if not error_count:
        print('No problems found')
        rc = 0
    else:
        print('%d errors' % error_count, file=sys.stderr)
        rc = 1

    if args.xunit_file:
        copyfile(xunit_file, args.xunit_file)
    #
    return rc
# ^ def main()

if __name__ == '__main__':
    sys.exit(main())
