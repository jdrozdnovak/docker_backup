
FROM ubuntu

RUN apt update
RUN apt install -y ca-certificates curl gnupg python3.11 python3-pip unzip
RUN python3.11 -m pip install --upgrade pip
RUN python3.11 -m pip install --upgrade pyyaml
RUN install -m 0755 -d /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
RUN chmod a+r /etc/apt/keyrings/docker.gpg
RUN echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt update
RUN apt install docker-ce-cli -y
RUN curl https://rclone.org/install.sh | bash
RUN apt upgrade -y

VOLUME /docker/
VOLUME /var/run/docker.sock
VOLUME /root/.config/rclone/rclone.conf


COPY find_and_backup.sh /usr/local/bin/
COPY backup.py /usr/local/bin/
COPY entry.sh /usr/local/bin/

RUN chmod +x /usr/local/bin/find_and_backup.sh
RUN chmod +x /usr/local/bin/entry.sh

CMD ["/entry.sh"]
