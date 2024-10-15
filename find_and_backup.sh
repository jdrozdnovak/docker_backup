#!/bin/sh
LOCKFILE="/tmp/find_and_backup.lock"

# Check if lock file exists
if [ -f "$LOCKFILE" ]; then
    echo "Backup process already running."
    exit 1
fi

# Create lock file
touch "$LOCKFILE"

# Run the backup script
find /docker/ -type f \( -name "docker-compose*.yml" -o -name "docker-compose*.yaml" \) -exec python3 /usr/local/bin/backup.py {} \;

# Remove lock file
rm -f "$LOCKFILE"