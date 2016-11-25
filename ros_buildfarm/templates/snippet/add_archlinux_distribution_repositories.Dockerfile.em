RUN mkdir /tmp/keys
@[for i, key in enumerate(distribution_repository_keys)]@
RUN echo -e "@('\\n'.join(key.splitlines()))" > /tmp/keys/@(i).key && pacman-key --add /tmp/keys/@(i).key && pacman-key --lsign $(gpg --list-packets /tmp/keys/0.key|grep keyid|head -n1|awk '{print $2 }')
@[end for]@
@[for url in distribution_repository_urls]@
RUN echo
RUN echo -e "[ros]\nServer = @url/\$arch" | tee -a /etc/pacman.conf
@[end for]@
