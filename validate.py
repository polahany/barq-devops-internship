#!/usr/bin/env python3
"""Validate the running BARQ Compose environment."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


PUBLIC_PORT = os.getenv("PUBLIC_PORT", "8090")
BASE_URL = os.getenv("BASE_URL", f"http://127.0.0.1:{PUBLIC_PORT}")
failures = 0


def check(name, passed, detail=""):
    global failures
    result = "PASS" if passed else "FAIL"
    print(f"{result}: {name}" + (f" - {detail}" if detail else ""))
    if not passed:
        failures += 1


def request_json(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Connection": "close"},
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {}
        return error.code, body


def wait_for_readiness(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, body = request_json("/ready")
            if status == 200:
                return body
        except (OSError, json.JSONDecodeError):
            pass
        time.sleep(1)
    return None


def docker(*arguments):
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def container_health(name):
    result = docker("inspect", "--format", "{{.State.Health.Status}}", name)
    return result.stdout.strip() if result.returncode == 0 else "missing"


def container_networks(name):
    result = docker("inspect", "--format", "{{json .NetworkSettings.Networks}}", name)
    if result.returncode != 0:
        return set()
    return set(json.loads(result.stdout))


def published_ports(name):
    result = docker("port", name)
    return result.stdout.strip() if result.returncode == 0 else ""


def main():
    ready = wait_for_readiness()
    check("public readiness", ready is not None)
    if ready:
        dependencies = ready.get("dependencies", {})
        check("PostgreSQL readiness", dependencies.get("postgres") == "ready")
        check("Redis readiness", dependencies.get("redis") == "ready")

    for path, expected_status in (("/", 200), ("/health", 200), ("/ready", 200)):
        try:
            status, _ = request_json(path)
            check(f"GET {path}", status == expected_status, f"HTTP {status}")
        except (OSError, json.JSONDecodeError) as error:
            check(f"GET {path}", False, str(error))

    identities = set()
    for _ in range(60):
        try:
            status, body = request_json("/instance")
            if status == 200:
                identities.add(body.get("instance_id"))
        except (OSError, json.JSONDecodeError):
            pass
        if {"app-01", "app-02" , "app-03"}.issubset(identities):
            break
    check("both application backends", {"app-01", "app-02" , "app-03"}.issubset(identities), str(sorted(identities)))

    title = f"validation-{int(time.time())}"
    try:
        status, body = request_json("/records", "POST", {"title": title})
        check("create PostgreSQL record", status == 201 and body.get("record", {}).get("title") == title, f"HTTP {status}")
        status, body = request_json("/records")
        records = body.get("records", [])
        check("list PostgreSQL records", status == 200 and any(record.get("title") == title for record in records), f"HTTP {status}")
    except (OSError, json.JSONDecodeError) as error:
        check("PostgreSQL record operations", False, str(error))

    try:
        first_status, first = request_json("/counter")
        second_status, second = request_json("/counter")
        counter_increased = (
            first_status == 200
            and second_status == 200
            and isinstance(first.get("counter"), int)
            and second.get("counter") == first["counter"] + 1
        )
        check("Redis counter increases", counter_increased)
    except (OSError, json.JSONDecodeError) as error:
        check("Redis counter increases", False, str(error))

    for container in ("app-01", "app-02","app-03" , "nginx", "postgres", "redis"):
        health = container_health(container)
        check(f"{container} container health", health == "healthy", health)

    nginx_ports = published_ports("nginx")
    check("NGINX publishes the public port", f":{PUBLIC_PORT}" in nginx_ports, nginx_ports)
    for container in ("app-01", "app-02","app-03" , "postgres", "redis"):
        check(f"{container} has no published ports", not published_ports(container))

    app_01_networks = container_networks("app-01")
    app_02_networks = container_networks("app-02")
    app_03_networks = container_networks("app-03")
    nginx_networks = container_networks("nginx")
    postgres_networks = container_networks("postgres")
    redis_networks = container_networks("redis")

    check("app-01 uses frontend and backend", any(name.endswith("_frontend") for name in app_01_networks) and any(name.endswith("_backend") for name in app_01_networks))
    check("app-02 uses frontend and backend", any(name.endswith("_frontend") for name in app_02_networks) and any(name.endswith("_backend") for name in app_02_networks))
    check("app-03 uses frontend and backend", any(name.endswith("_frontend") for name in app_03_networks) and any(name.endswith("_backend") for name in app_03_networks))
    check("NGINX uses frontend only", any(name.endswith("_frontend") for name in nginx_networks) and not any(name.endswith("_backend") for name in nginx_networks))
    check("PostgreSQL uses backend only", any(name.endswith("_backend") for name in postgres_networks) and not any(name.endswith("_frontend") for name in postgres_networks))
    check("Redis uses backend only", any(name.endswith("_backend") for name in redis_networks) and not any(name.endswith("_frontend") for name in redis_networks))

    if failures:
        print(f"\nValidation failed: {failures} check(s) failed.")
        return 1
    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
