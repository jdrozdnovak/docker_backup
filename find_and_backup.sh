#!/bin/bash

# Search for docker-compose files and perform backup
find /docker/ -name "docker-compose*.yml" -exec python3 /usr/local/bin/backup.py {} \;