#!/usr/bin/env bash
set -euo pipefail

container_name="postgres"
database_user="barq_app"
database_name="barq_tasks"
restore_database="barq_restore_test"
dump_file="${1:-}"
marker="${2:-}"

if [[ -z "$dump_file" || ! -s "$dump_file" ]]; then
    echo "Usage: $0 <backup.dump> [record-title]" >&2
    exit 1
fi

docker exec "$container_name" pg_isready -U "$database_user" -d "$database_name" >/dev/null
docker exec "$container_name" dropdb -U "$database_user" --if-exists "$restore_database" >/dev/null
docker exec "$container_name" createdb -U "$database_user" "$restore_database"
cat "$dump_file" | docker exec -i "$container_name" pg_restore \
    -U "$database_user" \
    -d "$restore_database" \
    --no-owner

if [[ -n "$marker" ]]; then
    if [[ ! "$marker" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
        echo "FAIL: record title contains unsupported characters" >&2
        exit 1
    fi
    count=$(docker exec "$container_name" psql -At \
        -U "$database_user" \
        -d "$restore_database" \
        -c "SELECT count(*) FROM records WHERE title = '$marker';")
else
    count=$(docker exec "$container_name" psql -At \
        -U "$database_user" \
        -d "$restore_database" \
        -c "SELECT count(*) FROM records;")
fi

count=$(echo "$count" | tr -d '[:space:]')
if [[ "$count" =~ ^[0-9]+$ && "$count" -gt 0 ]]; then
    echo "PASS: backup restored to $restore_database; matching records: $count"
else
    echo "FAIL: no matching records found in restored database" >&2
    exit 1
fi
