# Use Ubuntu 24.04 as the base image
FROM ubuntu:24.04 as build-stage

# Update and install all necessary packages in a single RUN command
RUN apt update && \
    apt install -y ca-certificates curl gnupg python3 unzip cron build-essential libssl-dev && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
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

# Set up Poetry path environment variable
ENV PATH="/root/.local/bin:$PATH"

# Copy pyproject.toml and poetry.lock into the container
COPY pyproject.toml /usr/src/app/
COPY poetry.lock /usr/src/app/

# Change to the app directory
WORKDIR /usr/src/app

# Install Python dependencies using Poetry, relying on the pre-existing lock file
RUN poetry config virtualenvs.in-project true
RUN poetry install --no-dev

# Copy only necessary shell scripts and Python files
COPY find_and_backup.sh /usr/local/bin/
COPY backup.py /usr/local/bin/
COPY entry.sh /usr/local/bin/

# Set permissions for shell scripts
RUN chmod +x /usr/local/bin/find_and_backup.sh && \
    chmod +x /usr/local/bin/entry.sh

# Declare volumes
VOLUME /docker/
VOLUME /var/run/docker.sock
VOLUME /root/.config/rclone/tmp/

# Final CMD
CMD ["/usr/local/bin/entry.sh"]
