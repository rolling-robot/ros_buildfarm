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

from collections import OrderedDict
import sys
import tempfile
import urllib
import os
import subprocess

from rosdistro import get_distribution_cache
from rosdistro import get_index

from ros_buildfarm.common import get_binarydeb_job_name
from ros_buildfarm.common import get_debian_package_name
from ros_buildfarm.common import get_default_node_label
from ros_buildfarm.common import get_github_project_url
from ros_buildfarm.common import get_node_label
from ros_buildfarm.common import get_release_binary_view_name
from ros_buildfarm.common import get_release_job_prefix
from ros_buildfarm.common import get_release_source_view_name
from ros_buildfarm.common import get_release_view_name
from ros_buildfarm.common \
    import get_repositories_and_script_generating_key_files
from ros_buildfarm.common import get_sourcedeb_job_name
from ros_buildfarm.common import get_system_architecture
from ros_buildfarm.common import JobValidationError
from ros_buildfarm.common import write_groovy_script_and_configs
from ros_buildfarm.config import get_distribution_file
from ros_buildfarm.config import get_index as get_config_index
from ros_buildfarm.config import get_release_build_files
from ros_buildfarm.git import get_repository
from ros_buildfarm.jenkins import configure_job
from ros_buildfarm.jenkins import configure_view
from ros_buildfarm.jenkins import connect
from ros_buildfarm.jenkins import remove_jobs
from ros_buildfarm.templates import expand_template


def configure_arch_prereq_jobs(
        config_url, rosdistro_name, release_build_name, groovy_script=None,
        dry_run=False, whitelist_package_names=None):
    """
    Configure all Jenkins release jobs.

    L{configure_release_job} will be invoked for every released package and
    target which matches the build file criteria.

    Additionally a job to import Debian packages into the Debian repository is
    created.
    """

    config = get_config_index(config_url)
    build_files = get_release_build_files(config, rosdistro_name)
    build_file = build_files[release_build_name]

    # get targets
    platforms = []
    for os_name in build_file.targets.keys():
        for os_code_name in build_file.targets[os_name].keys():
            platforms.append((os_name, os_code_name))
    print('The build file contains the following targets:')
    for os_name, os_code_name in platforms:
        print('  - %s %s: %s' % (os_name, os_code_name, ', '.join(
            build_file.targets[os_name][os_code_name])))

    prerequisites = [
            "log4cxx",
            "python2-rosdep",
            "python2-rosdistro",
            "python2-rospkg",
            "ros-build-tools",
            "python2-empy",
            "python2-catkin-pkg",
            "tango-icon-theme",
            "poco",
            "collada-dom",
            "console-bridge",
            "urdfdom",
            "urdfdom-headers",
            "pcl",
            #"flann"
            ]

    temp_directory = tempfile.mkdtemp()

    pkgs = {}
    dependencies = {}

    for prereq in prerequisites:
        open(os.path.join(temp_directory, "PKGBUILD"), "wb").write(
            urllib.request.urlopen("https://raw.githubusercontent.com/ros-archlinux/%s/rosarch/PKGBUILD" % prereq).read())
        pkgbuild_proc = subprocess.Popen(["/bin/bash","-c","source  PKGBUILD ;  echo $(printf \"'%s' \" \"${makedepends[@]}\"); echo ""; echo $(printf \"'%s' \" \"${depends[@]}\")"], stdout=subprocess.PIPE, cwd=temp_directory)
        pkgbuild_out,_ = pkgbuild_proc.communicate()
        fields = pkgbuild_out.decode('ascii').split("\n")
        makedepends = fields[0].split(" ")
        depends = fields[1].split(" ")

        from catkin_pkg.package import Package
        from catkin_pkg.package import Dependency
        pkg = Package(depends=[Dependency(dep) for dep in makedepends], run_depends=[Dependency(dep) for dep in depends])
        pkg.name = prereq
        pkgs[prereq] = pkg
        dependencies[prereq] = makedepends + depends


    from ros_buildfarm.common import topological_order_packages
    ordered_pkg_tuples = topological_order_packages(pkgs)
    
    # all further configuration will be handled by either the Jenkins API
    # or by a generated groovy script
    jenkins = connect(config.jenkins_url) if groovy_script is None else False

    for pkg_name in [p.name for _, p in ordered_pkg_tuples]:
        for os_name, os_code_name in platforms:
            configure_release_job(
                config_url, rosdistro_name, release_build_name,
                pkg_name, os_name, os_code_name, dependencies[pkg_name],
                config=config, build_file=build_file,
                jenkins=jenkins,
                dry_run=dry_run)


def _get_downstream_package_names(pkg_names, dependencies):
    downstream_pkg_names = set([])
    for pkg_name, deps in dependencies.items():
        if deps.intersection(pkg_names):
            downstream_pkg_names.add(pkg_name)
    return downstream_pkg_names

def configure_release_job(
        config_url, rosdistro_name, release_build_name,
        pkg_name, os_name, os_code_name, dependency_names,
        config=None, build_file=None,
        jenkins=None,
        dry_run=False):
    """
    Configure a Jenkins release job.

    The following jobs are created for each package:
    - M * N binary jobs, one for each combination of OS code name and arch
    """
    if config is None:
        config = get_config_index(config_url)
    if build_file is None:
        build_files = get_release_build_files(config, rosdistro_name)
        build_file = build_files[release_build_name]

    if os_name not in build_file.targets.keys():
        raise JobValidationError(
            "Invalid OS name '%s' " % os_name +
            'choose one of the following: ' +
            ', '.join(sorted(build_file.targets.keys())))

    if os_code_name not in build_file.targets[os_name].keys():
        raise JobValidationError(
            "Invalid OS code name '%s' " % os_code_name +
            'choose one of the following: ' +
            ', '.join(sorted(build_file.targets[os_name].keys())))

    if jenkins is None:
        jenkins = connect(config.jenkins_url)

    #if generate_sync_packages_jobs:
    #    configure_sync_packages_to_main_job(
    #        config_url, rosdistro_name, release_build_name,
    #        config=config, build_file=build_file, jenkins=jenkins,
    #        dry_run=dry_run)
    #    for arch in build_file.targets[os_name][os_code_name]:
    #        configure_sync_packages_to_testing_job(
    #            config_url, rosdistro_name, release_build_name,
    #            os_code_name, arch,
    #            config=config, build_file=build_file, jenkins=jenkins,
    #            dry_run=dry_run)

    binary_job_names = []
    job_configs = {}

    # binary jobs
    for arch in build_file.targets[os_name][os_code_name]:
        job_name = get_binarydeb_job_name(
            rosdistro_name, release_build_name,
            pkg_name, os_name, os_code_name, arch)

        upstream_job_names = [
            get_binarydeb_job_name(
                rosdistro_name, release_build_name,
                dependency_name, os_name, os_code_name, arch)
            for dependency_name in dependency_names]

        job_config = _get_binary_archlinux_job_config(
            config_url, rosdistro_name, release_build_name,
            config, build_file, os_name, os_code_name, arch,
            pkg_name, 'https://github.com/ros-archlinux/%s' % pkg_name,
            upstream_job_names=upstream_job_names,
            )
        # jenkinsapi.jenkins.Jenkins evaluates to false if job count is zero
        if isinstance(jenkins, object) and jenkins is not False:
            configure_job(jenkins, job_name, job_config, dry_run=dry_run)
        binary_job_names.append(job_name)
        job_configs[job_name] = job_config

    return [], binary_job_names, job_configs


def configure_release_views(
        jenkins, rosdistro_name, release_build_name, targets, dry_run=False):
    views = {}

    for os_name, os_code_name, arch in targets:
        view_name = get_release_view_name(
            rosdistro_name, release_build_name, os_name, os_code_name,
            arch)
        if arch == 'source':
            include_regex = '%s__.+__%s_%s__source' % \
                (view_name, os_name, os_code_name)
        else:
            include_regex = '%s__.+__%s_%s_%s__binary' % \
                (view_name, os_name, os_code_name, arch)
        views[view_name] = configure_view(
            jenkins, view_name, include_regex=include_regex,
            template_name='dashboard_view_all_jobs.xml.em', dry_run=dry_run)

    return views


def _get_direct_dependencies(pkg_name, dist_cache, pkg_names):
    from catkin_pkg.package import parse_package_string
    if pkg_name not in dist_cache.release_package_xmls:
        return None
    pkg_xml = dist_cache.release_package_xmls[pkg_name]
    pkg = parse_package_string(pkg_xml)
    depends = set([
        d.name for d in (
            pkg.buildtool_depends +
            pkg.build_depends +
            pkg.buildtool_export_depends +
            pkg.build_export_depends +
            pkg.exec_depends +
            pkg.test_depends)
        if d.name in pkg_names])
    return depends

def _get_binary_archlinux_job_config(
        config_url, rosdistro_name, release_build_name,
        config, build_file, os_name, os_code_name, arch,
        pkg_name, repo_name,
        upstream_job_names=None,
        is_disabled=False):
    template_name = 'release/binary_archlinux_job.xml.em'

    repository_args, script_generating_key_files = \
        get_repositories_and_script_generating_key_files(build_file=build_file, os_name="arch")
    repository_args.append(
        '--target-repository ' + build_file.archlinux_target_repository)
    repository_args.append('--download-arch-prerequisite')

    binarydeb_files = [
        'binarydeb/*.changes',
        'binarydeb/*.deb',
    ]

    sync_to_testing_job_name = [get_sync_packages_to_testing_job_name(
        rosdistro_name, os_code_name, arch)]

    maintainer_emails = _get_maintainer_emails(dist_cache, pkg_name) \
        if build_file.notify_maintainers \
        else set([])

    job_data = {
        'github_url': repo_name,

        'job_priority': build_file.jenkins_binary_job_priority,
        'node_label': get_node_label(
            build_file.jenkins_binary_job_label,
            get_default_node_label('%s_%s_%s' % (
                rosdistro_name, 'binarydeb', release_build_name))),

        'disabled': is_disabled,

        'upstream_projects': upstream_job_names,

        'ros_buildfarm_repository': get_repository(),

        'script_generating_key_files': script_generating_key_files,

        'rosdistro_index_url': config.rosdistro_index_url,
        'rosdistro_name': rosdistro_name,
        'release_build_name': release_build_name,
        'pkg_name': pkg_name,
        'os_name': os_name,
        'os_code_name': os_code_name,
        'arch': arch,
        'repository_args': repository_args,

        'append_timestamp': build_file.abi_incompatibility_assumed,

        'binarydeb_files': binarydeb_files,

        'import_package_job_name': get_import_package_job_name(rosdistro_name),
        'debian_package_name': pkg_name,

        'child_projects': sync_to_testing_job_name,

        'notify_emails': build_file.notify_emails,
        'maintainer_emails': maintainer_emails,
        'notify_maintainers': build_file.notify_maintainers,

        'timeout_minutes': build_file.jenkins_binary_job_timeout,

        'credential_id': build_file.upload_credential_id,
    }
    job_config = expand_template(template_name, job_data)
    return job_config


def configure_import_package_job(
        config_url, rosdistro_name, release_build_name,
        config=None, build_file=None, jenkins=None, dry_run=False):
    if config is None:
        config = get_config_index(config_url)
    if build_file is None:
        build_files = get_release_build_files(config, rosdistro_name)
        build_file = build_files[release_build_name]
    if jenkins is None:
        jenkins = connect(config.jenkins_url)

    job_name = get_import_package_job_name(rosdistro_name)
    job_config = _get_import_package_job_config(build_file)

    # jenkinsapi.jenkins.Jenkins evaluates to false if job count is zero
    if isinstance(jenkins, object) and jenkins is not False:
        configure_job(jenkins, job_name, job_config, dry_run=dry_run)
    return (job_name, job_config)


def get_import_package_job_name(rosdistro_name):
    view_name = get_release_job_prefix(rosdistro_name)
    return '%s_import-package' % view_name


def _get_import_package_job_config(build_file):
    template_name = 'release/import_package_job.xml.em'
    job_data = {
        'target_queue': build_file.target_queue,
        'abi_incompatibility_assumed': build_file.abi_incompatibility_assumed,
        'notify_emails': build_file.notify_emails,
    }
    job_config = expand_template(template_name, job_data)
    return job_config


def configure_sync_packages_to_testing_job(
        config_url, rosdistro_name, release_build_name, os_code_name, arch,
        config=None, build_file=None, jenkins=None, dry_run=False):
    if config is None:
        config = get_config_index(config_url)
    if build_file is None:
        build_files = get_release_build_files(config, rosdistro_name)
        build_file = build_files[release_build_name]
    if jenkins is None:
        jenkins = connect(config.jenkins_url)

    job_name = get_sync_packages_to_testing_job_name(
        rosdistro_name, os_code_name, arch)
    job_config = _get_sync_packages_to_testing_job_config(
        config_url, rosdistro_name, release_build_name, os_code_name, arch,
        config, build_file)

    # jenkinsapi.jenkins.Jenkins evaluates to false if job count is zero
    if isinstance(jenkins, object) and jenkins is not False:
        configure_job(jenkins, job_name, job_config, dry_run=dry_run)
    return (job_name, job_config)


def get_sync_packages_to_testing_job_name(
        rosdistro_name, os_code_name, arch):
    view_name = get_release_job_prefix(rosdistro_name)
    return '%s_sync-packages-to-testing_%s_%s' % \
        (view_name, os_code_name, arch)


def _get_sync_packages_to_testing_job_config(
        config_url, rosdistro_name, release_build_name, os_code_name, arch,
        config, build_file):
    template_name = 'release/sync_packages_to_testing_job.xml.em'

    repository_args, script_generating_key_files = \
        get_repositories_and_script_generating_key_files(build_file=build_file)

    job_data = {
        'ros_buildfarm_repository': get_repository(),

        'script_generating_key_files': script_generating_key_files,

        'config_url': config_url,
        'rosdistro_name': rosdistro_name,
        'release_build_name': release_build_name,
        'os_code_name': os_code_name,
        'arch': arch,
        'repository_args': repository_args,

        'notify_emails': build_file.notify_emails,
    }
    job_config = expand_template(template_name, job_data)
    return job_config


def configure_sync_packages_to_main_job(
        config_url, rosdistro_name, release_build_name,
        config=None, build_file=None, jenkins=None, dry_run=False):
    if config is None:
        config = get_config_index(config_url)
    if build_file is None:
        build_files = get_release_build_files(config, rosdistro_name)
        build_file = build_files[release_build_name]
    if jenkins is None:
        jenkins = connect(config.jenkins_url)

    job_name = get_sync_packages_to_main_job_name(
        rosdistro_name)
    job_config = _get_sync_packages_to_main_job_config(
        rosdistro_name, build_file)

    # jenkinsapi.jenkins.Jenkins evaluates to false if job count is zero
    if isinstance(jenkins, object) and jenkins is not False:
        configure_job(jenkins, job_name, job_config, dry_run=dry_run)
    return (job_name, job_config)


def get_sync_packages_to_main_job_name(rosdistro_name):
    view_name = get_release_job_prefix(rosdistro_name)
    return '%s_sync-packages-to-main' % view_name


def _get_sync_packages_to_main_job_config(rosdistro_name, build_file):
    template_name = 'release/sync_packages_to_main_job.xml.em'
    job_data = {
        'rosdistro_name': rosdistro_name,

        'notify_emails': build_file.notify_emails,
    }
    job_config = expand_template(template_name, job_data)
    return job_config


def _get_maintainer_emails(dist_cache, pkg_name):
    maintainer_emails = set([])
    # add maintainers listed in latest release to recipients
    if dist_cache and pkg_name in dist_cache.release_package_xmls:
        from catkin_pkg.package import parse_package_string
        pkg_xml = dist_cache.release_package_xmls[pkg_name]
        pkg = parse_package_string(pkg_xml)
        for m in pkg.maintainers:
            maintainer_emails.add(m.email)
    return maintainer_emails

configure_arch_prereq_jobs("https://raw.githubusercontent.com/gdlg/ros_buildfarm_config/rosarchfarm/index.yaml", "kinetic", "default")

