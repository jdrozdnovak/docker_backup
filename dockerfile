# Use a minimal base image
FROM ubuntu:latest as build-stage

# Update and install all packages in a single RUN command to minimize layers
# Also clean up package lists to free up space
RUN apt update && \
    apt install -y ca-certificates curl gnupg python3.11 python3-pip unzip cron && \
    python3.11 -m pip install --upgrade pip && \
    python3.11 -m pip install pyyaml requests && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt update && \
    apt install docker-ce-cli -y && \
    curl https://rclone.org/install.sh | bash && \
    apt upgrade -y && \
    apt remove gnupg curl python3-pip unzip -y && \
    apt autoremove -y  && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    touch /var/spool/cron/crontabs/root && \
    mkdir -p ~/.config/rclone/

# Copy only necessary files
COPY find_and_backup.sh /usr/local/bin/
COPY backup.py /usr/local/bin/
COPY entry.sh /usr/local/bin/

# Set permissions
RUN chmod +x /usr/local/bin/find_and_backup.sh && \
    chmod +x /usr/local/bin/entry.sh

# Declare volumes
VOLUME /docker/
VOLUME /var/run/docker.sock
VOLUME /root/.config/rclone/rclone.conf

# Final CMD
CMD ["/usr/local/bin/entry.sh"]