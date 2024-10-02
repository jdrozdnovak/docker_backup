#!/bin/bash
PYTHON_EXEC="/usr/src/app/.venv/bin/python"
# Search for docker-compose files and perform backup
find /docker/ -type f \( -name "docker-compose*.yml" -o -name "docker-compose*.yaml" \) -exec $PYTHON_EXEC /usr/local/bin/backup.py {} \;