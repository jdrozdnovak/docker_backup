#!/bin/bash

# Write the cron schedule and command to a file
CRON_SCHEDULE="${CRON_SCHEDULE:-* * * * *}"
crontab -l | { cat; echo "$CRON_SCHEDULE /usr/local/bin/find_and_backup.sh"; } | crontab -