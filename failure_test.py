#!/usr/bin/env python3
"""Stop one backend, measure traffic, and prove recovery."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8090")
TARGET = "app-01"
REQUEST_COUNT = 40


def docker(*arguments):
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def instance_request():
    request = urllib.request.Request(
        BASE_URL + "/instance", headers={"Connection": "close"}
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            body = json.loads(response.read())
            return response.status, body.get("instance_id")
    except urllib.error.HTTPError as error:
        return error.code, None
    except (OSError, json.JSONDecodeError):
        return 0, None


def wait_for_container(name, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = docker("inspect", "--format", "{{.State.Health.Status}}", name)
        if result.returncode == 0 and result.stdout.strip() == "healthy":
            return True
        time.sleep(1)
    return False


def main():
    status, _ = instance_request()
    if status != 200:
        print("FAIL: the application was not available before the test")
        return 1
    print("PASS: application available before failure")

    stopped = False
    test_failed = False
    try:
        result = docker("stop", TARGET)
        if result.returncode != 0:
            print(f"FAIL: could not stop {TARGET}")
            return 1
        stopped = True
        print(f"PASS: stopped {TARGET}")

        successes = 0
        errors = 0
        identities = set()
        for _ in range(REQUEST_COUNT):
            status, identity = instance_request()
            if status == 200:
                successes += 1
                identities.add(identity)
            else:
                errors += 1

        print(f"Traffic while {TARGET} was stopped: {REQUEST_COUNT} requests, {successes} successful, {errors} errors")
        if successes > 0 and "app-02" in identities:
            print("PASS: app-02 continued serving traffic")
        else:
            print("FAIL: no successful traffic from app-02")
            test_failed = True

        if errors > 0:
            print("PASS: errors during the backend failure were measured")
        else:
            print("FAIL: the test did not observe the stopped backend failure")
            test_failed = True
    finally:
        if stopped:
            result = docker("start", TARGET)
            if result.returncode == 0:
                print(f"PASS: started {TARGET}")
            else:
                print(f"FAIL: could not restart {TARGET}")
                test_failed = True

    if not wait_for_container(TARGET):
        print(f"FAIL: {TARGET} did not become healthy within 30 seconds")
        return 1
    print(f"PASS: {TARGET} became healthy")

    recovered = False
    for _ in range(20):
        status, identity = instance_request()
        if status == 200 and identity == TARGET:
            recovered = True
            break
        time.sleep(0.2)

    if recovered:
        print(f"PASS: recovered {TARGET} served a request")
    else:
        print(f"FAIL: recovered {TARGET} did not serve a request")
        test_failed = True

    return 1 if test_failed else 0


if __name__ == "__main__":
    sys.exit(main())
