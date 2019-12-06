# Copyright 2019 eSOL Co.,Ltd.
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
from shutil import rmtree, copyfile, copytree
import subprocess
import sys
import time
import json
import re
import tempfile
import json
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
        '--cache-dir',
        metavar='cache',
        default=tempfile.gettempdir(),
        dest='cache_dir',
        help='The location HAROS will place its cache in. '
             'Defaults to system temp folder')
    parser.add_argument(
        '--xunit-file',
        help='Generate a xunit compliant XML file')
    parser.add_argument(
        '--report-dir',
        default=None,
        dest='report_dir',
        help='The location to export the HAROS html report to '
             '(if desired).')

    args = parser.parse_args(argv)

    # HACK:
    # For some reason python adds the venv/ paths
    # after the global dist-packages paths, which can lead to
    # python2 / python3 incompabilities (loading the wrong module).
    # Therefore we sort the paths first and override them
    # before calling HAROS.
    sys_path_venv = [p for p in sys.path if 'venv' in p]
    sys_path_rest = [p for p in sys.path if not p in sys_path_venv]
    sys.path = sys_path_venv + sys_path_rest
    os.environ["PYTHONPATH"] = os.pathsep.join(sys.path)

    # Prepare a temporary directory for running HAROS
    haros_tmp_dir = os.path.join(args.cache_dir, 'ament_haros')
    haros_home_dir = os.path.join(haros_tmp_dir, 'haros_home')
    haros_data_dir = os.path.join(haros_tmp_dir, 'haros_data')
    try:
        if os.path.exists(haros_tmp_dir):
            rmtree(haros_tmp_dir)
        os.makedirs(haros_tmp_dir)
        os.makedirs(haros_home_dir)
        os.makedirs(haros_data_dir)
    except:
        sys.stderr.write("Trying to create a HAROS tmp folders at "
                         + haros_tmp_dir + " failed.")
        return 1
    #

    haros_bin = os.path.join(sys.exec_prefix, 'bin', 'haros')
    if not os.path.exists(haros_bin):
        # should have been installed 
        sys.stderr.write("HAROS not found at " + haros_bin)
        return 1

    cmd = [haros_bin]
    
    package_dir = os.path.abspath(args.paths[0])
    # ^ TODO: Is it possible we could receive multiple paths?

    # If we were pointed at a package folder,
    # find the ROS2 workspace root.
    try:
        workspace_dir = package_dir[0:package_dir.rindex('/src/')]
    except ValueError:
        # Check if we are already in the workspace root directory.
        if os.path.exists(package_dir + '/src/') == False:
            sys.stderr.write("Failed to detect ROS workspace root folder")
            return 1
        # else: workspace_dir is already the workspace root directory
        workspace_dir = package_dir
    #
    packages = find_ros_packages(package_dir)
    if len(packages) == 0:
        sys.stderr.write("Failed to find any ROS packages to analyze")
        return 1
    #
    # Generate HAROS project.yaml file to direct HAROS to the package/project
    if len(packages) == 1:
        project_name = next(iter(packages)) # key is package name
    else:
        # somehow there were several packages in the folder
        # so let't use the folder name
        project_name = os.path.basename(package_dir)
        # ^ TODO: won't work when path ends with a '/'
    with open(os.path.join(haros_tmp_dir, project_name+'.yaml'), "w") as f:
        f.write('%YAML 1.1\n')
        f.write('---\n')
        f.write('project: '+project_name+'\n')
        f.write('packages:\n')
        for p in packages:
            f.write('    - %s\n' % p)
        #
    #
    # Generate HAROS configs.yaml file to customize our analysis
    with open(os.path.join(haros_home_dir, 'configs.yaml'), "w") as f:
        f.write('%YAML 1.1\n')
        f.write('---\n')
        f.write('workspace: "%s"\n' % workspace_dir)
        # Ignore conflicting or meaningless linter rules
        f.write('analysis:\n')
        f.write('    ignore:\n')
        f.write('        rules: [')
        # cpplint rules about opening curly braces contradict another
        f.write('"haros_plugin_cpplint:opening_curly_brace", ')
        f.write('"haros_plugin_cpplint:opening_brace_line" ]\n')
    #

    cmd.extend(['--cwd', workspace_dir])
    cmd.extend(['--home', haros_home_dir])
    cmd.extend(['--config',
                os.path.join(haros_home_dir, 'configs.yaml')])
    cmd.extend(['analyse'])
    cmd.extend(['--project-file',
                os.path.join(haros_tmp_dir, project_name+'.yaml')])
    cmd.extend(['--data-dir', haros_data_dir])
    cmd.extend(['--junit-xml-output'])
    try:
        p = subprocess.Popen(cmd) # , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = p.communicate()
    except subprocess.CalledProcessError as e:
        sys.stderr.write("The invocation of 'haros' failed with error code %d: %s" %
              (e.returncode, e))
        return 1
    #

    # Check if the output XML file is written
    xunit_file = os.path.join(
        haros_data_dir,
        'data',
        project_name,
        'compliance',
        project_name+'.xml'
    )
    if not os.path.exists(xunit_file):
        sys.stderr.write("HAROS failed to write xUnit (XML) output file")
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
            sys.stderr.write('[%s:%s]: (%s: %s) %s' % (file, line, severity, id, msg))
            error_count += 1
        # ^ for testcase in testsuite
    # ^ for testsuite in root[0]

    # output summary
    if not error_count:
        print('No problems found')
        rc = 0
    else:
        sys.stderr.write('%d errors' % error_count)
        rc = 1

    if args.xunit_file:
        copyfile(xunit_file, args.xunit_file)
    #

    if args.report_dir:
        report_dir = os.path.abspath(args.report_dir)
        # To preserve history, check if the target desination
        # already contains a data/<package_name>/summary.json
        # file, and if so, merge its 'history' entry with the
        # summary.json created in this report.
        summary_file = os.path.join(report_dir,
                                    'data',
                                    project_name,
                                    'summary.json')
        history = None
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                summary = json.load(f)
                history = summary.get('history')
        # Remove the old report if there is one:
        if os.path.exists(report_dir):
            rmtree(report_dir)
        if not os.path.exists(os.path.basename(report_dir)):
            os.makedirs(os.path.basename(report_dir))
        # Copy the report to destination.
        copytree(haros_data_dir, report_dir)
        # Restore history.
        if history:
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            for item, values in history.items():
                summary['history'][item] = values + summary['history'][item]
            with open(summary_file, "w") as f:
                json.dump(summary, f, indent=2, separators=(",", ":"))
            #
        # ^ if history
    # ^ if args.report_dir

    return rc
# ^ def main()

if __name__ == '__main__':
    sys.exit(main())
