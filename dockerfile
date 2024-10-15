FROM python:3.12-bookworm

COPY requirements.txt .

RUN apt update && \
    apt upgrade -y && \
    apt install -y ca-certificates curl cron && \
    python3 -m pip install -r requirements.txt && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt update && \
    apt install docker-ce-cli -y && \
    curl https://rclone.org/install.sh | bash && \
    apt autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    touch /var/spool/cron/crontabs/root && \
    mkdir -p ~/.config/rclone/

COPY find_and_backup.sh /usr/local/bin/
COPY backup.py /usr/local/bin/
COPY entry.sh /usr/local/bin/

RUN chmod +x /usr/local/bin/find_and_backup.sh && \
    chmod +x /usr/local/bin/entry.sh

VOLUME /docker/
VOLUME /var/run/docker.sock
VOLUME /root/.config/rclone/tmp/

CMD ["/usr/local/bin/entry.sh"]
