# generated from @template_name


@(TEMPLATE(
    'snippet/from_base_image.Dockerfile.em',
    os_name=os_name,
    os_code_name=os_code_name,
    arch=arch,
))@
MAINTAINER Dirk Thomas dthomas+buildfarm@@osrfoundation.org

VOLUME ["/var/cache/pacman/pkg"]

@(TEMPLATE(
    'snippet/setup_locale.Dockerfile.em',
    os_name=os_name,
    os_code_name=os_code_name,
    timezone=timezone,
))@

RUN useradd -u @uid -m buildfarm

@(TEMPLATE(
    'snippet/add_archlinux_distribution_repositories.Dockerfile.em',
    distribution_repository_keys=distribution_repository_keys,
    distribution_repository_urls=distribution_repository_urls,
    os_code_name=os_code_name,
    add_source=False,
))@

@(TEMPLATE(
    'snippet/add_wrapper_scripts.Dockerfile.em',
    wrapper_scripts=wrapper_scripts,
))@

# automatic invalidation once every day
RUN echo "@today_str"

RUN pacman -Sy --needed --noconfirm archlinux-keyring
RUN pacman -Syu --noconfirm
RUN pacman -S --needed --noconfirm git base-devel ccache python
RUN pacman -S @dependencies}

#@(TEMPLATE(
#    'snippet/install_dependencies.Dockerfile.em',
#    dependencies=dependencies,
#    dependency_versions=dependency_versions,
#))@

USER buildfarm
ENTRYPOINT ["sh", "-c"]
@{
cmd = \
    'PYTHONPATH=/tmp/ros_buildfarm:$PYTHONPATH' + \
    ' PATH=/usr/lib/ccache:$PATH' + \
    ' python3 -u' + \
    ' /tmp/ros_buildfarm/scripts/release/build_binary_archlinux.py' + \
    ' ' + rosdistro_name + \
    ' ' + package_name + \
    ' --sourcedeb-dir ' + binarydeb_dir
}@
CMD ["@cmd"]
