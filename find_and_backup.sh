#!/bin/sh
# Search for docker-compose files and perform backup
find /docker/ -type f \( -name "docker-compose*.yml" -o -name "docker-compose*.yaml" \) -exec python3 /usr/local/bin/backup.py {} \;