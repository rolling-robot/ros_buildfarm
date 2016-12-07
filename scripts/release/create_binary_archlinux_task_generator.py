#!/usr/bin/env python3

# Copyright 2014-2016 Open Source Robotics Foundation, Inc.
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

from __future__ import print_function

import argparse
import os
import sys

from ros_buildfarm.argument import add_argument_arch
from ros_buildfarm.argument import add_argument_binarydeb_dir
from ros_buildfarm.argument import \
    add_argument_distribution_repository_key_files
from ros_buildfarm.argument import add_argument_distribution_repository_urls
from ros_buildfarm.argument import add_argument_dockerfile_dir
from ros_buildfarm.argument import add_argument_os_code_name
from ros_buildfarm.argument import add_argument_os_name
from ros_buildfarm.argument import add_argument_package_name
from ros_buildfarm.argument import add_argument_rosdistro_name
from ros_buildfarm.common import get_binary_package_versions
from ros_buildfarm.common import get_debian_package_name
from ros_buildfarm.common import get_distribution_repository_keys
from ros_buildfarm.common import get_user_id
from ros_buildfarm.templates import create_dockerfile


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description="Generate a 'Dockerfile' for building the binarydeb")
    add_argument_rosdistro_name(parser)
    add_argument_package_name(parser)
    add_argument_os_name(parser)
    add_argument_os_code_name(parser)
    add_argument_arch(parser)
    add_argument_distribution_repository_urls(parser)
    add_argument_distribution_repository_key_files(parser)
    add_argument_binarydeb_dir(parser)
    add_argument_dockerfile_dir(parser)
    args = parser.parse_args(argv)

    debian_package_name = get_debian_package_name(
        args.rosdistro_name, args.package_name)

    # find PKGBUILD dependencies
    pkgbuild_proc = subprocess.Popen(["/bin/bash","-c","source  PKGBUILD ;  echo $(printf \"'%s' \" \"${makedepends[@]}\") $(printf \"'%s' \" \"${depends[@]}\")"], stdout=subprocess.PIPE)
    pkgbuild_out,_ = pkgbuild_proc.communicate()
    archlinux_pkg_names = pkgbuild_proc.decode('ascii').split(" ")

    # generate Dockerfile
    data = {
        'os_name': args.os_name,
        'os_code_name': args.os_code_name,
        'arch': args.arch,

        'uid': get_user_id(),

        'distribution_repository_urls': args.distribution_repository_urls,
        'distribution_repository_keys': get_distribution_repository_keys(
            args.distribution_repository_urls,
            args.distribution_repository_key_files),

        'dependencies': archlinux_pkg_names,

        'rosdistro_name': args.rosdistro_name,
        'package_name': args.package_name,
        'binarydeb_dir': args.binarydeb_dir,
    }
    create_dockerfile(
        'release/binary_archlinux_task.Dockerfile.em', data, args.dockerfile_dir)

    # output hints about necessary volumes to mount
    ros_buildfarm_basepath = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..'))
    print('Mount the following volumes when running the container:')
    print('  -v %s:/tmp/ros_buildfarm:ro' % ros_buildfarm_basepath)
    print('  -v %s:/tmp/binary_archlinux' % args.binarydeb_dir)

if __name__ == '__main__':
    main()
