#!/bin/bash

# Write the cron schedule and command to a file
echo "$CRON_SCHEDULE"
echo $RCLONE_REMOTE_FOLDER
echo $RCLONE_REMOTE_NAME
echo $FAIL_NOTIFY_URL
(crontab -l 2>/dev/null; printf "%s/bin/bash ./usr/local/bin/find_and_backup.sh >/proc/1/fd/1 2>/proc/1/fd/2\n" "$CRON_SCHEDULE") | crontab -

cron -f