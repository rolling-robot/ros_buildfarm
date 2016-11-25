# Copyright 2014, 2016 Open Source Robotics Foundation, Inc.
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

import os
import subprocess
import sys
from time import strftime
import traceback

from ros_buildfarm.common import get_debian_package_name
from ros_buildfarm.release_common import dpkg_parsechangelog

def build_binary_archlinux(rosdistro_name, package_name, sourcedeb_dir):
    # ensure that one source subfolder exists
    archlinux_package_name = get_debian_package_name(rosdistro_name, package_name)
    subfolders = _get_package_subfolders(sourcedeb_dir, archlinux_package_name)
    assert len(subfolders) == 1, subfolders
    source_dir = subfolders[0]

    cmd = ['makepkg']

    try:
        subprocess.check_call(cmd, cwd=source_dir)
    except subprocess.CalledProcessError:
        traceback.print_exc()
        sys.exit("""
--------------------------------------------------------------------------------------------------
`{0}` failed.
This is usually because of an error building the package.
The traceback from this failure (just above) is printed for completeness, but you can ignore it.
You should look above `E: Building failed` in the build log for the actual cause of the failure.
--------------------------------------------------------------------------------------------------
""".format(' '.join(cmd)))


def _get_package_subfolders(basepath, debian_package_name):
    subfolders = []
    for filename in os.listdir(basepath):
        path = os.path.join(basepath, filename)
        if not os.path.isdir(path):
            continue
        if filename.startswith('%s-' % debian_package_name):
            subfolders.append(path)
    return subfolders

