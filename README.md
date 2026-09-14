# BARQ DevOps Internship Task

This repository contains the repaired BARQ Flask application, PostgreSQL, Redis,
and NGINX environment. I kept the supplied logs unchanged and made small changes
to investigate, repair, validate, and document the system.

## Current status

The current Compose setup has two Flask instances behind NGINX:

- NGINX is the only service published to the host: `127.0.0.1:8080` to container port `80`.
- `app-01` and `app-02` listen on container port `8080` and have different identities.
- NGINX and the apps use the `frontend` network.
- The apps, PostgreSQL, and Redis use the internal `backend` network.
- PostgreSQL uses the named `postgres-data` volume.
- Redis uses append-only persistence and the named `redis-data` volume.
- All services have health checks, restart policies, and small CPU/memory limits.
- The app image runs as the non-root `app` user.
- Secrets are read from the local ignored `.env` file. `.env.example` contains safe example values.
- `validate.py`, `failure_test.py`, `backup.sh`, `restore.sh`, log analysis, CI, and the report-only Trivy scan are implemented.

The recorded challenge still has to be performed in its video working copy. It
requires the live port change from `8080` to `8090` and adding a third app instance.
The current README describes the verified two-instance setup before that live change.

## Prerequisites

- Linux or WSL2, Python 3.12, Git, and Docker Desktop using Linux containers.
- At least about 2 CPU cores, 4 GB free RAM, and 3 GB free disk space.
- Ports and container names `app-01`, `app-02`, `nginx`, `postgres`, and `redis` must be free.

Run shell scripts from WSL or Git Bash. Run the Python commands from the repository root.

## Setup, build, and start

```bash
git status
git log -5 --oneline
docker version
docker compose version
docker compose -p barq-assessment up --build -d
docker compose -p barq-assessment ps -a
docker compose -p barq-assessment logs --no-color
```

The `.env` file is local only. Do not commit it. The initial supplied environment
was intentionally broken, so the first run should be recorded before repairs.

## Basic endpoint tests

```bash
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/ready
curl -i http://127.0.0.1:8080/instance
curl -i http://127.0.0.1:8080/records
curl -i http://127.0.0.1:8080/counter
for i in $(seq 1 60); do curl -sS http://127.0.0.1:8080/instance; echo; done | sort | uniq -c
```

Repeat `/instance` several times. The responses should include both `app-01` and
`app-02`, showing that NGINX sends requests to both backends.

## Tests and validation

App-only unit tests use fake dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Run the required Part 3 checks while the Compose services are healthy:

```bash
python validate.py
python failure_test.py
```

`validate.py` waits for readiness and checks all required endpoints, both app
identities, real PostgreSQL and Redis operations, all container health checks,
host-port exposure, and frontend/backend network membership. It prints `PASS` or
`FAIL` and exits non-zero when a required check fails.

`failure_test.py` stops `app-01`, sends 40 requests through NGINX, counts successful
and failed requests, starts `app-01` again, waits for it to become healthy, and
proves that it serves a request after recovery.

command to test failure
```aiignore
docker stop app-01
for i in $(seq 1 40); do curl -sS --max-time 4 -w ' HTTP %{http_code}\n' http://127.0.0.1:8080/instance || true; done
docker start app-01
until [ "$(docker inspect -f '{{.State.Health.Status}}' app-01)" = "healthy" ]; do sleep 1; done
docker compose -p barq-assessment ps -a
for i in $(seq 1 60); do curl -sS http://127.0.0.1:8080/instance; echo; done | sort | uniq -c
```

Analyze the supplied historical logs with:

```bash
python scripts/analyze_logs.py
```

The results are recorded in [log_analysis.md](log_analysis.md). The original files
under `logs/` are synthetic test data and were not edited.

## Persistence proof

This test creates a unique PostgreSQL record, recreates the app and PostgreSQL
containers without deleting the named volume, and checks that the record remains.
Run the commands in one PowerShell window:

```powershell
MARKER="video-persistence-$(date -u +%Y%m%d-%H%M%S)"
curl -fsS -X POST http://127.0.0.1:8080/records -H 'Content-Type: application/json' -d "{\"title\":\"$MARKER\"}"
BEFORE_ID=$(docker inspect -f '{{.Id}}' postgres)
echo "Before PostgreSQL container ID: $BEFORE_ID"
docker inspect postgres --format '{{range .Mounts}}{{.Name}} -> {{.Destination}}{{println}}{{end}}'
docker compose -p barq-assessment up -d --force-recreate postgres app-01 app-02
until [ "$(docker inspect -f '{{.State.Health.Status}}' postgres)" = "healthy" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' app-01)" = "healthy" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' app-02)" = "healthy" ]; do sleep 1; done
docker exec nginx nginx -s reload
until curl -fsS http://127.0.0.1:8080/ready >/dev/null; do sleep 1; done
AFTER_ID=$(docker inspect -f '{{.Id}}' postgres)
echo "After PostgreSQL container ID: $AFTER_ID"
test "$BEFORE_ID" != "$AFTER_ID" && echo "PASS: PostgreSQL container was recreated"
curl -fsS http://127.0.0.1:8080/records | MARKER="$MARKER" python3 -c 'import json,os,sys; records=json.load(sys.stdin)["records"]; assert any(item["title"] == os.environ["MARKER"] for item in records); print("PASS: timestamped record survived recreation")'
```

The timestamp makes each test record unique, so a record found after recreation is
from this test and not an old record. Do not use `docker compose down -v` during this
test because it deletes the data volumes.

## PostgreSQL backup and restore proof

Run these commands from WSL or Git Bash while the services are healthy:

```bash
MARKER="backup-$(date -u +%Y%m%d-%H%M%S)"
curl -fsS -X POST http://127.0.0.1:8080/records -H 'Content-Type: application/json' -d "{\"title\":\"$MARKER\"}"
./backup.sh
DUMP=$(ls -t backups/*.dump | head -n1)
./restore.sh "$DUMP" "$MARKER"
```

`backup.sh` creates a PostgreSQL custom-format dump under `backups/`. `restore.sh`
restores it into the separate `barq_restore_test` database and checks for the marker.
Expected output includes `PASS: backup created` and `PASS: backup restored`. Do not
commit files in `backups/`.

## CI and image scan

The workflow in [.github/workflows/ci.yml](.github/workflows/ci.yml) runs on pushes
and pull requests. It performs these steps:

1. Checks out the repository and installs Python dependencies.
2. Runs Python, shell, unit-test, and Compose syntax checks.
3. Builds the application image.
4. Runs Trivy for HIGH and CRITICAL findings.
5. Starts Compose and waits for `/ready` and all five current services to be healthy.
6. Runs `validate.py` and shows Compose logs if a step fails.
7. Stops the services after the job.

The Trivy scan currently uses `exit-code: "0"` because the first strict scan found
62 findings (57 HIGH and 5 CRITICAL) and stopped CI before validation. Findings are
reported for this lab but do not currently block the job. A production pipeline
should review the findings, update the image and dependencies, and then use a
reviewed blocking policy.

A green CI run proves that these checks passed for that commit and runner. It does
not prove that the system is secure, survives loss of the Docker host, or behaves
the same under production traffic. Branch protection is still needed if merges must
be blocked until the CI check is green.

## Initial investigation and repairs

- The first health problem was `/healthz` returning `404`. The app implemented `/health`, so the Compose health check was changed to `/health`.
- `/ready` returned `503` when the dependency addresses and PostgreSQL credentials did not match the running services. The app now uses `postgres:5432` and `redis:6379`, and the existing database role password was updated to match `.env` without deleting the volume.
- Both app instances first reported `app-01`. Their `INSTANCE_ID` values are now `app-01` and `app-02`.
- NGINX first mapped host port `8080` to container port `81` even though it listened on `80`. The mapping now uses `8080:80`.
- NGINX then returned `502` because the apps listened on `127.0.0.1`. Binding them to `0.0.0.0` lets NGINX reach both services through the frontend network.
- PostgreSQL and Redis were previously exposed and the service network was not isolated. Only NGINX is now public; the apps use both networks and the data services use the internal backend network.
- NGINX originally had no container health check. `/nginx-health` and a Docker health check were added.

The investigation journal, failed attempts, retests, and local evidence files are in
[troubleshooting.md](troubleshooting.md). The design choices are in
[decisions.md](decisions.md), and the security observations are in
[security_review.md](security_review.md).

## Required questions and answers

### What failed first? What proved the cause? Which failed attempt taught you something?

The first observed problem was the Docker health check for `/healthz`. Direct tests
showed `/health` returned `200` and `/healthz` returned `404`, while the Compose file
requested `/healthz` and the Flask app defined `/health`. This proved a path mismatch.

The first validation attempt sent only 10 `/instance` requests and saw `app-01`
only. That was not enough to prove that both backends were absent because NGINX had
many workers. Increasing the sample to 40 requests found both identities. A first CI
run also taught us that `/ready` could be successful before Docker marked every
health check as healthy, so the workflow now waits for both conditions.

### What patterns did the logs reveal? How did you avoid double-counting requests?

The logs contain 720 distinct client requests. Final statuses were 615 responses
with `200`, 10 with `404`, 40 with `502`, 47 with `503`, and 8 with `504`. The 5xx
rate was `95/720 = 13.19%`, using distinct client request IDs as the denominator.

The main patterns were 59 connection-refused events, 31 Redis `TimeoutError` events,
16 PostgreSQL `InvalidPassword` events, and 8 upstream timeout events. Nineteen
requests retried through another upstream and succeeded.

The analysis script reads all three logs, ignores malformed lines, removes exact
duplicate lines, and stores each valid access record by `request_id`. This prevents
duplicate log lines and upstream retry attempts from being counted as extra client
requests.

### How do requests flow? Why these ports, networks and readiness checks?

The client calls NGINX on host port `8080`. NGINX listens on container port `80` and
proxies to `app-01:8080` or `app-02:8080` using Compose service names. The apps call
PostgreSQL at `postgres:5432` and Redis at `redis:6379` on the backend network.

NGINX and the apps share `frontend`. The apps and the two data services share the
internal `backend` network. NGINX is not connected to `backend`, so it cannot directly
reach PostgreSQL or Redis. The standard internal ports avoid publishing data services
to the host.

`/health` checks that the Flask process is alive. `/ready` checks both PostgreSQL and
Redis, so a process can be alive while the application is still not ready to serve
data requests.

### Why these timeouts, retries, restart settings and resource limits?

The health checks and scripts use short bounded timeouts so a broken service does not
make the test wait forever. NGINX uses a 2-second connection timeout and a 3-second
read timeout. Compose health checks retry a few times to allow normal startup.

The scripts wait up to 30 seconds for readiness or recovery. `restart: unless-stopped`
allows an unexpected service exit to recover while still respecting a manual stop used
by the failure test. The limits are small lab values: apps use 256 MB and 0.50 CPU,
PostgreSQL uses 512 MB and 1 CPU, and Redis and NGINX use 128 MB and 0.50 CPU. They
stop one container from using all available machine resources, but they were not chosen
from production load testing.

### When should validation fail? What does green CI prove, or not prove?

Validation should fail when an endpoint has the wrong status, a dependency operation
fails, one backend is not observed, a container is not healthy, an unwanted host port
is published, or a service is on the wrong network. The scripts print the failed check
and return a non-zero exit code.

Green CI proves that syntax checks, unit tests, Compose validation, image build,
startup/readiness, health checks, and `validate.py` passed in that CI run. It does not
prove production security, high availability, host-level persistence, or the final
recorded challenge state.

### Which single points of failure remain? How would you fix them in production?

This Compose setup still has one NGINX entry point and one Docker host. A failure of
NGINX can stop public traffic. A local named volume also cannot protect data if the
machine or Docker storage is lost.

For production, I would run more than one proxy behind a load balancer, use managed or
replicated data storage, keep backups on another system, and add centralized logs and
alerts.

### What would you improve? How did you verify AI-assisted work?

I would update the image and Python dependencies to address the Trivy findings, move
secrets to a production secret manager, test backups regularly, and add stronger
monitoring. I would also measure real resource use before changing the limits.

AI helped with small implementation and command-writing tasks. I verified the work by
reviewing the changed files, running the unit tests, starting the Compose services,
checking real HTTP/PostgreSQL/Redis behavior, running validation and failure tests,
checking container networks and volumes, and reviewing the CI result. The AI usage
details are recorded in [AI_USAGE.md](AI_USAGE.md).

## Stop and cleanup

Stop the lab without deleting its named volumes:

```bash
docker compose -p barq-assessment down
```

Do not use `--volumes` when the PostgreSQL or Redis data must remain. Do not use
global Docker prune commands.

## Main implementation commits

The work was committed progressively, including investigation, fixes, validation,
persistence, backup/restore, CI, and the report-only image scan. The commit messages
include `fix-the-initial-investigation`, `fix-nginx-upstream`,
`docker-networking-nginx`, `validate-and-failure-tests`, `persistence-proof`,
`backup-restore`, and `bonus-image-security-scan`.
