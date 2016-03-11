@[if os_name in ['ubuntu', 'debian'] and arch in ['i386', 'armhf', 'arm64']]@
@[if arch == 'i386']@
FROM i386/@os_name:@os_code_name
@[end if]@
@[if arch == 'armhf']@
FROM armhf/@os_name:@os_code_name
@[else]@
FROM aarch64/@os_name:@os_code_name
@[end if]@
@[else]@
FROM @os_name:@os_code_name
@[end if]@
