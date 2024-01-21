#!/bin/sh

# Write the cron schedule and command to a file
echo "$CRON_SCHEDULE"
echo $RCLONE_REMOTE_FOLDER
echo $RCLONE_REMOTE_NAME
echo $FAIL_NOTIFY_URL
cp /root/.config/rclone/tmp/rclone.conf /root/.config/rclone/rclone.conf
echo "RCLONE_REMOTE_FOLDER=$RCLONE_REMOTE_FOLDER" > /env_var
echo "RCLONE_REMOTE_NAME=$RCLONE_REMOTE_NAME" >> /env_var
echo "FAIL_NOTIFY_URL=$FAIL_NOTIFY_URL" >> /env_var
(crontab -l 2>/dev/null; printf "%s /usr/local/bin/find_and_backup.sh >/proc/1/fd/1 2>/proc/1/fd/2\n" "$CRON_SCHEDULE") | crontab -

cron -f