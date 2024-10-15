#!/bin/bash
# Search for docker-compose files and perform backup
find /docker/ -type f \( -name "docker-compose*.yml" -o -name "docker-compose*.yaml" \) -exec python /usr/local/bin/backup.py {} \;