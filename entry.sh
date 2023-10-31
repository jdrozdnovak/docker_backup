#!/bin/bash

# Write the cron schedule and command to a file
(crontab -l 2>/dev/null; printf "%s /usr/local/bin/find_and_backup.sh >/proc/1/fd/1 2>/proc/1/fd/2\n" "$CRON_SCHEDULE") | crontab -

cron -f