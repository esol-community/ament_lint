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
from shutil import which
import subprocess
import sys
import time
from xml.etree import ElementTree
from xml.sax.saxutils import escape
from xml.sax.saxutils import quoteattr

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

    #haros_bin = which('haros')
    #if not haros_bin:
    #    print("Could not find 'haros' executable", file=sys.stderr)
    #    return 1
    #cmd = [haros_bin]
    # ^ TODO: the official release of HAROS is not yet compatible with ROS2/ament
    # work spaces. So we'll download a different version for it.

    try:
        p = subprocess.Popen(["rm",
                              "-rf",
                              "/tmp/haros*",
                              ";",
                              "wget",
                              "-O",
                              "/tmp/haros_ros2-support.zip",
                              "https://github.com/esol-community/haros/archive/ros2-support.zip",
                              ";",
                              "unzip",
                              "/tmp/haros_ros2-support.zip"],
                              stderr=subprocess.PIPE)
        output = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("Trying to download HAROS failed with error code %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1

    cmd = [which('python2'), '/tmp/haros-ros2-support/haros-runner.py']

    # OVERRIDE: use local HAROS repo
    # subprocess.Popen([which('export'), 'ROS_WORKSPACE="/home/osboxes/ros/"'])
    # cmd = [which('python2'), '/home/osboxes/haros/haros-runner.py']

    #cmd.extend(['--junit-xml-output'])
    cmd.extend(['--cwd', args.paths[0]]) # TODO: Support multiple paths.
    cmd.extend(['full'])
    print(*cmd)
    try:
        p = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        output = p.communicate()[1]
    except subprocess.CalledProcessError as e:
        print("The invocation of 'haros' failed with error code %d: %s" %
              (e.returncode, e), file=sys.stderr)
        return 1

    print(output)

    # TODO: output errors
    # TODO: output summary
    # TODO: return 1 if any violations were found, 0 if none were found
    error_count = 1
    if not error_count:
        print('No problems found')
        rc = 0
    else:
        print('%d errors' % error_count, file=sys.stderr)
        rc = 1

    return rc


def get_files(paths, extensions):
    files = []
    for path in paths:
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                if 'AMENT_IGNORE' in filenames:
                    dirnames[:] = []
                    continue
                # ignore folder starting with . or _
                dirnames[:] = [d for d in dirnames if d[0] not in ['.', '_']]
                dirnames.sort()

                # select files by extension
                for filename in sorted(filenames):
                    _, ext = os.path.splitext(filename)
                    if ext in ['.%s' % e for e in extensions]:
                        files.append(os.path.join(dirpath, filename))
        if os.path.isfile(path):
            files.append(path)
    return [os.path.normpath(f) for f in files]

if __name__ == '__main__':
    sys.exit(main())
