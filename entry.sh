#!/bin/bash

# Write the cron schedule and command to a file
CRON_SCHEDULE="${CRON_SCHEDULE:-* * * * *}"
crontab -l | { cat; echo "$CRON_SCHEDULE /usr/local/bin/find_and_backup.sh"; } | crontab -

# Give the cron file appropriate permissions
chmod 0644 /etc/cron.d/find_and_backup