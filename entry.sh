#!/bin/bash

# Write the cron schedule and command to a file
echo "${CRON_SCHEDULE:-* * * * *} /usr/local/bin/find_and_backup.sh" > /etc/cron.d/find_and_backup

# Give the cron file appropriate permissions
chmod 0644 /etc/cron.d/find_and_backup

# Start cron in the foreground
cron -f