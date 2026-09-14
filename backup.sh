#!/usr/bin/env bash
set -euo pipefail

container_name="postgres"
database_user="barq_app"
database_name="barq_tasks"
backup_dir="backups"
timestamp=$(date -u +%Y%m%d-%H%M%S)
backup_file="${backup_dir}/barq_tasks-${timestamp}.dump"

mkdir -p "$backup_dir"
docker exec "$container_name" pg_isready -U "$database_user" -d "$database_name" >/dev/null
docker exec "$container_name" pg_dump -U "$database_user" -d "$database_name" -Fc > "$backup_file"

if [[ ! -s "$backup_file" ]]; then
    echo "FAIL: backup file is empty: $backup_file" >&2
    exit 1
fi

echo "PASS: backup created at $backup_file"
