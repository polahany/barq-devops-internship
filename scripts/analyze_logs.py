#!/usr/bin/env python3

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"

ACCESS_FIELDS = {
    "timestamp",
    "request_id",
    "method",
    "path",
    "status",
    "upstream",
    "upstream_status",
    "request_time",
}
APP_COMMON_FIELDS = {"timestamp", "level", "event", "request_id", "instance_id"}
APP_HTTP_FIELDS = {"method", "path", "status", "duration_ms"}
APP_DEPENDENCY_FIELDS = {"dependency", "error_type"}

ERROR_LINE = re.compile(
    r"^(?P<timestamp>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[(?P<level>[a-z]+)\] (?P<message>.+)$"
)
REQUEST_ID = re.compile(r"request_id=(?P<request_id>[^,\s]+)")
REQUEST = re.compile(r'request: "(?P<method>[A-Z]+) (?P<path>\S+) HTTP/[^\"]+"')
UPSTREAM = re.compile(r'upstream: "(?P<upstream>[^\"]+)"')


def parse_iso_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_timestamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def validate_json_record(record, kind):
    if not isinstance(record, dict):
        raise ValueError("record is not an object")

    required = ACCESS_FIELDS if kind == "access" else APP_COMMON_FIELDS
    if kind == "application" and record.get("event") == "http_request":
        required = required | APP_HTTP_FIELDS
    if kind == "application" and record.get("event") == "dependency_error":
        required = required | APP_DEPENDENCY_FIELDS

    missing = required - record.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")

    parse_iso_timestamp(record["timestamp"])


def read_json_log(path, kind):
    records = []
    seen = set()
    total = valid = malformed = duplicates = 0

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        total += 1
        raw = line.strip()
        duplicate = raw in seen
        if duplicate:
            duplicates += 1
        else:
            seen.add(raw)

        try:
            record = json.loads(raw)
            validate_json_record(record, kind)
            record["_timestamp"] = parse_iso_timestamp(record["timestamp"])
            record["_line"] = line_number
            valid += 1
            if not duplicate:
                records.append(record)
        except (json.JSONDecodeError, TypeError, ValueError):
            malformed += 1

    return {
        "name": path.name,
        "total": total,
        "valid": valid,
        "malformed": malformed,
        "duplicates": duplicates,
        "records": records,
    }


def read_error_log(path):
    records = []
    seen = set()
    total = valid = malformed = duplicates = 0

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        total += 1
        raw = line.strip()
        duplicate = raw in seen
        if duplicate:
            duplicates += 1
        else:
            seen.add(raw)

        match = ERROR_LINE.match(raw)
        if not match:
            malformed += 1
            continue

        timestamp = datetime.strptime(
            match.group("timestamp"), "%Y/%m/%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        message = match.group("message")
        request_id_match = REQUEST_ID.search(message)
        request_match = REQUEST.search(message)
        upstream_match = UPSTREAM.search(message)
        valid += 1

        if not duplicate:
            records.append(
                {
                    "timestamp": match.group("timestamp"),
                    "level": match.group("level"),
                    "message": message,
                    "request_id": (
                        request_id_match.group("request_id") if request_id_match else None
                    ),
                    "method": request_match.group("method") if request_match else None,
                    "path": request_match.group("path") if request_match else None,
                    "upstream": (
                        upstream_match.group("upstream") if upstream_match else None
                    ),
                    "_timestamp": timestamp,
                    "_line": line_number,
                }
            )

    return {
        "name": path.name,
        "total": total,
        "valid": valid,
        "malformed": malformed,
        "duplicates": duplicates,
        "records": records,
    }


def comma_values(value):
    return [part.strip() for part in str(value).split(",") if part.strip()]


def latest_access_records(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[record["request_id"]].append(record)
    return {
        request_id: max(items, key=lambda item: item["_timestamp"])
        for request_id, items in grouped.items()
    }, sum(1 for items in grouped.values() if len(items) > 1)


def print_counter(counter):
    if not counter:
        print("  none")
        return
    for key, count in sorted(counter.items(), key=lambda item: str(item[0])):
        print(f"  {key}: {count}")


def error_kind(record):
    message = record["message"]
    if "connect() failed" in message:
        return "connection refused"
    if "upstream timed out" in message:
        return "upstream timeout"
    return record["level"]


def main():
    access_log = read_json_log(LOG_DIR / "access.log", "access")
    error_log = read_error_log(LOG_DIR / "error.log")
    app_log = read_json_log(LOG_DIR / "application.log", "application")
    logs = [access_log, error_log, app_log]

    access_by_id, repeated_request_ids = latest_access_records(access_log["records"])
    access_records = sorted(access_by_id.values(), key=lambda item: item["_timestamp"])

    app_by_id = defaultdict(list)
    for record in app_log["records"]:
        app_by_id[record["request_id"]].append(record)

    error_by_id = defaultdict(list)
    for record in error_log["records"]:
        if record["request_id"]:
            error_by_id[record["request_id"]].append(record)

    # question 1
    print("Q1 : What UTC interval is covered? How many valid, malformed and duplicate lines are in each file? ")
    for log in logs:
        timestamps = [record["_timestamp"] for record in log["records"]]
        interval = (
            f"{format_timestamp(min(timestamps))} to {format_timestamp(max(timestamps))}"
            if timestamps
            else "no valid timestamps"
        )
        print(
            f"  {log['name']}: {interval}; total={log['total']}, "
            f"valid={log['valid']}, malformed={log['malformed']}, "
            f"duplicate extra lines={log['duplicates']}"
        )
    print("  Valid includes parseable duplicate lines; duplicate extras are removed")

    # question 2

    print("\nQ2 : How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?")
    print(f"  Distinct request_id values in access.log: {len(access_records)}")
    print(
        f"  Exact duplicate access lines removed: {access_log['duplicates']}; "
    )
    print(
        f"  Using dictionary that only counts the valid request_id only once"
    )

    # question 3

    print("\nQ3 : What are the final client status counts and error rate? State your denominator.")
    status_counts = Counter(int(record["status"]) for record in access_records)
    print_counter(status_counts)
    server_errors = sum(count for status, count in status_counts.items() if status >= 500)
    denominator = len(access_records)
    error_rate = (server_errors / denominator * 100) if denominator else 0.0
    print(
        f"  5xx error rate: {server_errors}/{denominator} = {error_rate:.2f}% "
        "(denominator: distinct client requests)."
    )

    failures = [record for record in access_records if int(record["status"]) >= 500]

    # question 4
    print("\n Q4 : Which paths, time windows and backends account for the failures?")
    print("  Paths:")
    print_counter(Counter(record["path"] for record in failures))
    print("  UTC minutes:")
    print_counter(
        Counter(record["_timestamp"].strftime("%Y-%m-%dT%H:%MZ") for record in failures)
    )
    print("  Final upstream backends:")
    print_counter(
        Counter(
            comma_values(record["upstream"])[-1]
            if comma_values(record["upstream"])
            else "none"
            for record in failures
        )
    )

    # question 5

    print("\nQ5 : What are the median and p95 client latencies? State the percentile method and units")
    latencies_seconds = sorted(float(record["request_time"]) for record in access_records)
    if latencies_seconds:
        median_seconds = statistics.median(latencies_seconds)
        p95_index = math.ceil(0.95 * len(latencies_seconds)) - 1
        p95_seconds = latencies_seconds[p95_index]
        print(f"  Median: {median_seconds:.3f} seconds ({median_seconds * 1000:.1f} ms)")
        print(f"  p95: {p95_seconds:.3f} seconds ({p95_seconds * 1000:.1f} ms)")
        print(
            f"  Method: median of {len(latencies_seconds)} sorted request_time values; "
            "p95 is  latencies_seconds[ceil(0.95 * n)] ."
        )
    else:
        print("  No valid request_time values.")

    # question 6
    print("\nQ6 : Which requests retried upstream? How many succeeded after retrying?")
    retried = [
        record
        for record in access_records
        if len(comma_values(record["upstream"])) > 1
        or len(comma_values(record["upstream_status"])) > 1
    ]
    retry_successes = 0

    if not retried:
        print("  none")
    for record in retried:
        upstreams = comma_values(record["upstream"])
        statuses = comma_values(record["upstream_status"])
        attempts = "; ".join(
            f"{upstream or 'unknown'} -> {status or 'unknown'}"
            for upstream, status in zip_longest(upstreams, statuses, fillvalue=None)
        )
        succeeded = 200 <= int(record["status"]) < 400
        retry_successes += int(succeeded)
        print(
            f"  {record['request_id']} {record['path']}: {attempts}; "
            f"final client status={record['status']}"
        )
    print(f"  Retried requests: {len(retried)}; succeeded after retry: {retry_successes}.")

    # question 7
    print("\nQ7 :  Build an incident timeline using evidence from access, error AND application logs.")
    timeline = []
    if access_records:
        timeline.append(
            (
                access_records[0]["_timestamp"],
                f"access.log begins with {access_records[0]['request_id']} status "
                f"{access_records[0]['status']}",
            )
        )
    if failures:
        timeline.append(
            (
                failures[0]["_timestamp"],
                f"access.log first 5xx: {failures[0]['request_id']} "
                f"{failures[0]['path']} status {failures[0]['status']}",
            )
        )

    error_groups = defaultdict(list)
    for record in error_log["records"]:
        error_groups[error_kind(record)].append(record)
    for kind, records in error_groups.items():
        records.sort(key=lambda item: item["_timestamp"])
        timeline.append(
            (
                records[0]["_timestamp"],
                f"error.log {kind}: {len(records)} events through "
                f"{format_timestamp(records[-1]['_timestamp'])}",
            )
        )

    dependency_groups = defaultdict(list)
    for record in app_log["records"]:
        if record["event"] == "dependency_error":
            dependency_groups[(record["dependency"], record["error_type"])].append(record)
    for (dependency, failure_type), records in dependency_groups.items():
        records.sort(key=lambda item: item["_timestamp"])
        timeline.append(
            (
                records[0]["_timestamp"],
                f"application.log {dependency} {failure_type}: {len(records)} events "
                f"through {format_timestamp(records[-1]['_timestamp'])}",
            )
        )

    if failures:
        timeline.append(
            (
                failures[-1]["_timestamp"],
                f"access.log last 5xx: {failures[-1]['request_id']} "
                f"{failures[-1]['path']} status {failures[-1]['status']}",
            )
        )
    if access_records:
        timeline.append(
            (
                access_records[-1]["_timestamp"],
                f"access.log ends with {access_records[-1]['request_id']} status "
                f"{access_records[-1]['status']}",
            )
        )
    for timestamp, description in sorted(timeline, key=lambda item: item[0]):
        print(f"  {format_timestamp(timestamp)} - {description}")

    # question 8

    print("\nQ8 : Show one correlated failed request and one successful request. Include IDs and timestamps.")
    failed_example = next(
        (
            record
            for record in failures
            if record["request_id"] in error_by_id
            and not any(
                item["event"] == "http_request"
                for item in app_by_id.get(record["request_id"], [])
            )
        ),
        next((record for record in failures if record["request_id"] in error_by_id), None),
    )
    if failed_example:
        request_id = failed_example["request_id"]
        print(
            f"  Failed {request_id}: access.log {failed_example['timestamp']} "
            f"{failed_example['path']} status={failed_example['status']} "
            f"upstream={failed_example['upstream']} "
            f"upstream_status={failed_example['upstream_status']}."
        )
        error = error_by_id[request_id][0]
        print(
            f"  error.log {format_timestamp(error['_timestamp'])}: "
            f"{error_kind(error)} to {error['upstream']}."
        )
        app_http = [
            item for item in app_by_id.get(request_id, []) if item["event"] == "http_request"
        ]
        if app_http:
            item = app_http[0]
            print(
                f"  application.log {item['timestamp']}: {item['instance_id']} "
                f"status={item['status']}."
            )
        else:
            print("  application.log: no matching http_request; the app did not handle it.")
    else:
        print("  No failed request correlated with error.log.")

    successful_example = next(
        (
            record
            for record in access_records
            if 200 <= int(record["status"]) < 300
            and any(
                item["event"] == "http_request" and 200 <= int(item["status"]) < 300
                for item in app_by_id.get(record["request_id"], [])
            )
            and record["request_id"] not in error_by_id
        ),
        None,
    )
    if successful_example:
        request_id = successful_example["request_id"]
        app_record = next(
            item
            for item in app_by_id[request_id]
            if item["event"] == "http_request" and 200 <= int(item["status"]) < 300
        )
        print(
            f"  Successful {request_id}: access.log {successful_example['timestamp']} "
            f"{successful_example['path']} status={successful_example['status']} "
            f"upstream={successful_example['upstream']}; application.log "
            f"{app_record['timestamp']} {app_record['instance_id']} "
            f"status={app_record['status']}; no matching error.log entry."
        )
    else:
        print("  No successful request correlated with application.log.")

    # question 9

    print("\nQ9 : Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?")
    proxy_ids = {
        record["request_id"]
        for record in error_log["records"]
        if record["request_id"] and record["level"] == "error"
    }
    proxy_final_failures = sum(
        1
        for request_id in proxy_ids
        if request_id in access_by_id and int(access_by_id[request_id]["status"]) >= 500
    )
    proxy_recovered = sum(
        1
        for request_id in proxy_ids
        if request_id in access_by_id and int(access_by_id[request_id]["status"]) < 500
    )
    proxy_missing_app = sum(
        1
        for request_id in proxy_ids
        if not any(
            record["event"] == "http_request" for record in app_by_id.get(request_id, [])
        )
    )
    print(
        f"  Proxy/connectivity: {len(proxy_ids)} request IDs appear in NGINX error "
        f"records; {proxy_final_failures} ended as 5xx, {proxy_recovered} recovered, "
        f"and {proxy_missing_app} have no matching application http_request."
    )
    print("  Proof: error.log reports connection refusals or upstream timeouts.")

    dependency_events = [
        record for record in app_log["records"] if record["event"] == "dependency_error"
    ]
    dependency_ids = {record["request_id"] for record in dependency_events}
    dependency_client_failures = sum(
        1
        for request_id in dependency_ids
        if request_id in access_by_id and int(access_by_id[request_id]["status"]) >= 500
    )
    print(
        f"  Dependency/application: {len(dependency_ids)} request IDs have "
        f"dependency_error events; {dependency_client_failures} ended as client 5xx."
    )
    print("  Dependency event types:")
    print_counter(
        Counter(
            f"{record['dependency']} {record['error_type']}" for record in dependency_events
        )
    )
    print(
        "  Proof: application.log names the dependency and error type for the same "
        "request_id found in access.log."
    )

if __name__ == "__main__":
    main()
