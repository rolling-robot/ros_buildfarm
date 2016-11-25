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
    add_source=True,
    target_repository=target_repository,
))@

@(TEMPLATE(
    'snippet/add_wrapper_scripts.Dockerfile.em',
    wrapper_scripts=wrapper_scripts,
))@

# automatic invalidation once every day
RUN echo "@today_str"

RUN pacman -Sy --needed --noconfirm archlinux-keyring
RUN pacman -Syu --noconfirm
RUN pacman -Sy --needed --noconfirm git base-devel
RUN pacman -S --noconfirm python

# always invalidate to actually have the latest apt repo state
RUN echo "@now_str"
RUN pacman -Sy --needed --noconfirm archlinux-keyring
RUN pacman -Syu --noconfirm
RUN pacman -S --noconfirm python-empy

USER buildfarm
ENTRYPOINT ["sh", "-c"]
@{
cmds = [
]

if not skip_download_sourcedeb:
    cmds = [
        'PYTHONPATH=/tmp/ros_buildfarm:$PYTHONPATH python3 -u' +
        ' /tmp/ros_buildfarm/scripts/release/get_sources.py' +
        ' --rosdistro-index-url ' + rosdistro_index_url +
        ' ' + rosdistro_name +
        ' ' + package_name +
        ' ' + os_name +
        ' ' + os_code_name +
        ' --source-dir ' + binarydeb_dir
    ]

cmds.append(
    'PYTHONPATH=/tmp/ros_buildfarm:$PYTHONPATH python3 -u' +
    ' /tmp/ros_buildfarm/scripts/release/create_binary_archlinux_task_generator.py' +
    ' ' + rosdistro_name +
    ' ' + package_name +
    ' ' + os_name +
    ' ' + os_code_name +
    ' ' + arch +
    ' --distribution-repository-urls ' + ' '.join(distribution_repository_urls) +
    ' --distribution-repository-key-files ' + ' ' .join(['/tmp/keys/%d.key' % i for i in range(len(distribution_repository_keys))]) +
    ' --binarydeb-dir ' + binarydeb_dir +
    ' --dockerfile-dir ' + dockerfile_dir)
}@
CMD ["@(' && '.join(cmds))"]
