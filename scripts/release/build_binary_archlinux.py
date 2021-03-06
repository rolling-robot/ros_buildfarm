#!/usr/bin/env python3

# Copyright 2014 Open Source Robotics Foundation, Inc.
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
import sys

from ros_buildfarm.argument import add_argument_package_name
from ros_buildfarm.argument import add_argument_rosdistro_name
from ros_buildfarm.argument import add_argument_sourcedeb_dir
from ros_buildfarm.binary_archlinux_job import build_binary_archlinux
from ros_buildfarm.common import Scope


def main(argv=sys.argv[1:]):
    with Scope('SUBSECTION', 'build binary_archlinux'):
        parser = argparse.ArgumentParser(
            description='Build package binary_archlinux')
        add_argument_rosdistro_name(parser)
        add_argument_package_name(parser)
        add_argument_sourcedeb_dir(parser)
        args = parser.parse_args(argv)

        return build_binary_archlinux(
            args.rosdistro_name, args.package_name, args.sourcedeb_dir)


if __name__ == '__main__':
    sys.exit(main())
