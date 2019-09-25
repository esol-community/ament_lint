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
#from xml.etree import ElementTree
#from xml.sax.saxutils import escape
#from xml.sax.saxutils import quoteattr
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
    extensions = ['c', 'cc', 'cpp', 'cxx', 'h', 'hh', 'hpp', 'hxx']

    parser = argparse.ArgumentParser(
        description='Perform static code analysis using cppcheck.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'paths',
        nargs='*',
        default=[os.curdir],
        help='Files and/or directories to be checked. Directories are searched recursively for '
             'files ending in one of %s.' %
             ', '.join(["'.%s'" % e for e in extensions]))
    parser.add_argument(
        '--include_dirs',
        nargs='*',
        help="Include directories for C/C++ files being checked."
             "Each directory is passed to cppcheck as '-I <include_dir>'")
    # not using a file handle directly
    # in order to prevent leaving an empty file when something fails early
    parser.add_argument(
        '--xunit-file',
        help='Generate a xunit compliant XML file')
    args = parser.parse_args(argv)

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

    #haros_bin = which('haros')
    #if not haros_bin:
    #    print("Could not find 'haros' executable", file=sys.stderr)
    #    return 1
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
    cmd = [which('python2'), haros_tmp_dir + '/haros-master/haros-runner.py']
    workspace_dir = os.path.abspath(args.paths[0])
    # If we were pointed at a package folder,
    # find the ROS2 workspace root.
    try:
        workspace_dir = workspace_dir[0:workspace_dir.rindex('/src/')]
    except ValueError:
        # Check if we are already in the workspace root directory.
        if os.path.exists(workspace_dir + '/src/') == False:
            print("Failed to detect ROS workspace root folder",
                  file=sys.stderr)
            return 1
        # else: workspace_dir is already the workspace root directory
    #
    packages = find_ros_packages(os.path.abspath(args.paths[0]))
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

    # Read the resulting JSON output files
    #with open(haros_tmp_dir + '/haros_data/data/ament_haros_project/summary.json') as f:
    #    summary = json.load(f)
    #error_count = summary["issues"]["total"]

    # Read the resulting XML output files
    error_count = 0
    tree = ElementTree(None, haros_tmp_dir + '/haros_data/data/ament_haros_project/compliance/ament_haros_project.xml')
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
        copyfile(haros_tmp_dir + '/haros_data/data/ament_haros_project/compliance/ament_haros_project.xml',
                 args.xunit_file)
    #
    return rc
# ^ def main()

if __name__ == '__main__':
    sys.exit(main())
