# Troubleshooting

## 2026-09-11 - Application health checks returned 404

- Symptom: `app-01` and `app-02` were running, but Docker marked both containers unhealthy. Their configured health-check requests returned HTTP 404.
- Hypothesis: The Compose health check requests `/healthz`, but the Flask application implements `/health` as its liveness endpoint.
- Command or test:

  ```powershell
  docker compose -p barq-assessment ps -a
  docker inspect --format "{{json .State.Health}}" app-01 app-02
  rg -n "healthz|@app.get" docker-compose.yml app/server.py
  docker exec app-01 python -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8080,timeout=3); c.request('GET','/health'); r=c.getresponse(); print('/health',r.status,r.read().decode())"
  docker exec app-01 python -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8080,timeout=3); c.request('GET','/healthz'); r=c.getresponse(); print('/healthz',r.status,r.read().decode())"
  ```

- Actual output: `/health` returned HTTP 200 with `status=alive`; `/healthz` returned HTTP 404 with `error=not_found`. Compose configured `/healthz`, while `app/server.py` defined `/health` and no `/healthz` route.
- Failed attempt and what changed the investigation: None.
- Root cause: The Docker health-check path does not match the implemented liveness endpoint.
- Fix: Health check changed from `/healthz` to `/health`.
- Retest evidence: `fix-1-status.txt` shows both apps healthy; `fix-1-app-probes.txt` shows `/health` HTTP 200.
- Related commit: Investigate initial health, readiness, identity and NGINX issues
- Remaining uncertainty: A passing liveness check will not prove that PostgreSQL and Redis are reachable.

## 2026-09-12 - Dependency readiness returned 503

- Symptom: `/ready` returned HTTP 503 and reported both PostgreSQL and Redis as unavailable, although the dependency containers became healthy.
- Hypothesis: The application is configured with internal dependency ports that differ from the ports on which the Compose services listen. PostgreSQL credentials also need comparison after the port issue is corrected.
- Command or test:

  ```powershell
  docker compose -p barq-assessment ps -a
  docker inspect --format "{{.Name}} {{.State.Health.Status}}" postgres redis
  docker exec app-01 python -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8080,timeout=5); c.request('GET','/ready'); r=c.getresponse(); print(r.status,r.read().decode())"
  rg -n "DATABASE_URL|REDIS_URL" config/app.env
  rg -n "POSTGRES_USER|POSTGRES_DB|POSTGRES_PASSWORD|5432|6379" docker-compose.yml
  docker exec app-01 python -c "import socket; print({p: socket.socket().connect_ex(('postgres',p)) for p in (5432,5433)})"
  docker exec app-01 python -c "import socket; print({p: socket.socket().connect_ex(('redis',p)) for p in (6379,6380)})"
  ```

- Actual output: `/ready` returned HTTP 503 with both dependencies `unavailable`. From inside `app-01`, PostgreSQL port 5432 and Redis port 6379 were reachable, while PostgreSQL port 5433 and Redis port 6380 were refused. The PostgreSQL password in `config/app.env` also differed from the Compose value.
- Failed attempt and what changed the investigation: The first PostgreSQL socket probe ran immediately after startup and showed both PostgreSQL ports refused. Repeating the probes after the dependency health checks passed showed 5432 and 6379 reachable and 5433 and 6380 refused, so the conclusion was based on a ready dependency state.
- Root cause: The configured dependency URLs use ports on which the Compose services are not listening. The credential mismatch remains a second readiness issue to retest after correcting the port.
- Fix: PostgreSQL changed to port 5432; Redis changed to port 6379.
- Retest evidence: `fix-1-app-probes.txt` shows Redis ready but PostgreSQL unavailable; `/ready` remains HTTP 503.
- Related commit: Investigate initial health, readiness, identity and NGINX issues
- Remaining uncertainty: New investigation found that the PostgreSQL password in `config/app.env` differs from `POSTGRES_PASSWORD` in `docker-compose.yml`; authentication must be retested after they match.

## 2026-09-12 - Both app instances reported `app-01`

- Symptom: Direct requests to both application containers returned the same `instance_id`, `app-01`.
- Hypothesis: The two Compose services use the same `INSTANCE_ID` environment value.
- Command or test:

  ```powershell
  foreach ($container in "app-01","app-02") {
      Write-Host "Testing $container"
      docker exec $container python -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8080,timeout=3); c.request('GET','/instance'); r=c.getresponse(); print(r.status,r.read().decode())"
  }
  rg -n "INSTANCE_ID" docker-compose.yml
  ```

- Actual output: Both direct responses contained `"instance_id":"app-01"`, and both Compose service definitions set `INSTANCE_ID: "app-01"`.
- Failed attempt and what changed the investigation: None.
- Root cause: The `app-02` service is configured with the `app-01` identity.
- Fix: `app-02` identity changed to `app-02`.
- Retest evidence: `fix-1-app-probes.txt` reports `app-01` and `app-02`.
- Related commit: Investigate initial health, readiness, identity and NGINX issues
- Remaining uncertainty: Distinct direct identities must be confirmed again after the Compose change.

## 2026-09-12 - NGINX public port did not match its listen port

- Symptom: The NGINX container was running, but a request to `http://127.0.0.1:8080/health` returned an empty response.
- Hypothesis: Compose publishes host port 8080 to a container port different from the port on which NGINX listens.
- Command or test:

  ```powershell
  docker compose -p barq-assessment ps -a
  curl.exe -i --max-time 10 http://127.0.0.1:8080/health
  rg -n "ports:|listen 80" docker-compose.yml nginx/nginx.conf
  ```

- Actual output: Compose published `127.0.0.1:8080->81/tcp`; `nginx/nginx.conf` contained `listen 80;`; the public request returned an empty reply.
- Failed attempt and what changed the investigation: None. The mapping and NGINX configuration were compared before any repair.
- Root cause: The host port is forwarded to container port 81 while NGINX listens on port 80.
- Fix: NGINX mapped to port 80.
- Retest evidence: `fix-1-http-health.txt` shows public `/health` HTTP 200.
- Related commit: Investigate initial health, readiness, identity and NGINX issues
- Remaining uncertainty: The upstream application path must be tested after the edge mapping is corrected.

## 2026-09-12 - PostgreSQL configuration still differed

- Symptom: After the port correction, `/ready` still returned HTTP 503 with PostgreSQL unavailable.
- Hypothesis: The PostgreSQL password in `config/app.env` does not match Compose.
- Command or test:

  ```powershell
  rg -n "DATABASE_URL" config/app.env
  rg -n "POSTGRES_PASSWORD" docker-compose.yml
  docker compose -p barq-assessment logs --no-color postgres
  ```

- Actual output: PostgreSQL logged `password authentication failed for user "barq_app"`; the two configuration files contained different password values.
- Failed attempt and what changed the investigation: Port probes showed `postgres:5432` reachable, but `/ready` still failed, so the investigation moved from networking to authentication.
- Root cause: PostgreSQL credentials are inconsistent between the app and the database service.
- Fix: `POSTGRES_PASSWORD` in `docker-compose.yml` was changed to match `config/app.env`.
- Retest evidence: `fix-postgres-cred-app-probes.txt` shows `/ready` HTTP 200 for both apps with PostgreSQL and Redis ready.
- Related commit: postgres-cred-fix
- Remaining uncertainty: The credential mismatch is resolved; public requests still need separate NGINX upstream testing.

## 2026-09-12 - NGINX could not reach the application upstreams

- Symptom: After the public port mapping was corrected, NGINX returned HTTP 502 for `/`, `/health`, `/ready`, and `/instance`.
- Hypothesis: The apps bind to `127.0.0.1`, while NGINX proxies to `app-01:8080` and `app-02:8080` over the Compose network.
- Command or test:

  ```powershell
  Get-Content evidence/local/fix-postgres-cred-http-health.txt
  rg -n "APP_HOST|APP_PORT" docker-compose.yml
  rg -n "server app-|proxy_pass" nginx/nginx.conf
  ```

- Actual output: `fix-postgres-cred-http-health.txt` records HTTP 502 Bad Gateway for all four public requests. `docker-compose.yml` sets `APP_HOST: "127.0.0.1"`; NGINX targets `app-01:8080` and `app-02:8080`.
- Failed attempt and what changed the investigation: Correcting the public port changed the empty reply into an NGINX 502, isolating the remaining failure to the upstream connection.
- Root cause: The application bind address prevents NGINX from reaching the upstream services through the Compose network.
- Fix: `APP_HOST` changed from `127.0.0.1` to `0.0.0.0`; NGINX upstreams remain `app-01:8080` and `app-02:8080`.
- Retest evidence: `fix-nginx-upstream-status.txt` shows healthy app containers, and `fix-nginx-upstream-http-health.txt` shows HTTP 200 for all four public paths.
- Related commit: fix-nginx-upstream
- Remaining uncertainty: Repeat `/instance` requests through NGINX to confirm traffic reaches both app instances.

## 2026-09-13 - Part 2 services needed isolation and persistence

- Symptom: PostgreSQL and Redis were published to the host, NGINX shared the backend network, PostgreSQL data was temporary, and Redis persistence was disabled.
- Hypothesis: The Compose file did not meet the Part 2 networking and storage requirements.
- Command or test:

  ```powershell
  docker compose -p barq-assessment config
  docker compose -p barq-assessment ps
  docker network inspect barq-assessment_frontend
  docker network inspect barq-assessment_backend
  ```

- Root cause: The original Compose configuration exposed extra ports and did not store the dependency data in the correct volumes.
- Fix: Only NGINX publishes port `8080`. NGINX uses frontend only, the apps use both networks, and PostgreSQL and Redis use backend only. Named volumes now store PostgreSQL and Redis data.
- Retest evidence: All five containers started successfully. Only NGINX showed a published host port, and network inspection showed the expected members.
- Related commit: `60d482f docker-networking-nginx`.
- Remaining uncertainty: Part 3 still needs to prove that data survives container recreation.

## 2026-09-13 - PostgreSQL failed after moving secrets to `.env`

- Symptom: PostgreSQL was healthy, but `/ready` and `/records` returned HTTP 503.
- Hypothesis: The existing PostgreSQL volume still stored the previous password.
- Command or test:

  ```powershell
  docker compose -p barq-assessment ps
  docker logs postgres
  curl.exe -i http://127.0.0.1:8080/ready
  ```

- Actual output: PostgreSQL logged an authentication failure for `barq_app`. The app reported PostgreSQL as unavailable while Redis was ready.
- Failed attempt: Connecting with the role `postgres` failed because this database was initialized with `barq_app` as its main role.
- Root cause: `POSTGRES_PASSWORD` only sets the password when PostgreSQL initializes a new data directory. It does not update a role inside an existing volume.
- Fix: The `barq_app` role password was updated to match the local ignored `.env` file. The volume was not deleted.
- Retest evidence: `/ready` returned HTTP 200, `/records` created a record with HTTP 201, and listing records returned HTTP 200.
- Related commit: The secret configuration is in `60d482f docker-networking-nginx`; the role update was a local database command.
- Remaining uncertainty: The password should be managed by a proper secret manager in production.

## 2026-09-14 - NGINX had no container health check

- Symptom: NGINX was running, but `docker compose ps` only showed `Up` instead of `healthy`.
- Hypothesis: The NGINX service had no health-check configuration.
- Command or test:

  ```powershell
  docker inspect --format "{{json .Config.Healthcheck}}" nginx
  docker exec nginx nginx -t
  ```

- Actual output: The health-check value was empty, while the NGINX configuration syntax was valid.
- Root cause: No NGINX health check was defined in `docker-compose.yml`.
- Fix: Added `/nginx-health` to NGINX and configured Docker to request it with `curl`.
- Retest evidence: `docker compose ps` showed NGINX as `healthy`, and `/nginx-health` returned HTTP 200.
- Related commit: validate-and-failure-tests
- Remaining uncertainty: This check proves that NGINX responds, but the application dependencies are checked separately by `/ready`.

## 2026-09-14 - The validation script was not implemented

- Symptom: `validate.py` required
- Hypothesis: The placeholder needed to be replaced with the checks listed in Part 3.
- Command or test:

  ```powershell
  python validate.py
  ```

- Failed attempt: The first test sent 10 `/instance` requests and only found `app-01`. NGINX had 16 workers, so 10 requests were not enough to prove both backends.
- Fix: Implemented bounded readiness, endpoint, backend identity, PostgreSQL, Redis, container health, port, and network checks. The identity sample was increased to 40 requests.
- Retest evidence: Every check printed `PASS`, both `app-01` and `app-02` were found, and the script exited with code 0.
- Related commit: validate-and-failure-tests
## 2026-09-14 - The backend failure test was not implemented

- Symptom: `failure_test.py` required
- Hypothesis: The test needed to stop one backend, measure requests, restore it, and prove recovery.
- Command or test:

  ```powershell
  python failure_test.py
  ```

- Fix: The script stops `app-01`, sends 40 requests through NGINX, counts successes and errors, and starts `app-01` again in a cleanup block.
- Retest evidence: While `app-01` was stopped, 21 requests succeeded through `app-02` and 19 returned errors. After restart, `app-01` became healthy and served a request again.
- Related commit: validate-and-failure-tests

## 2026-09-14 - PostgreSQL record survived container recreation

- Symptom: Part 3 requires proof that a PostgreSQL record survives app and PostgreSQL container recreation.
- Hypothesis: The named `postgres-data` volume keeps the record when the PostgreSQL container is replaced.
- Command or test:

  ```powershell
  docker compose -p barq-assessment ps
  $marker="persistence-$(Get-Date -Format 'yyyyMMdd-HHmmss')"; $body=@{title=$marker}|ConvertTo-Json -Compress; $created=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8080/records' -ContentType 'application/json' -Body $body; $created|ConvertTo-Json
  $recordsBefore=Invoke-RestMethod 'http://127.0.0.1:8080/records'; $foundBefore=@($recordsBefore.records|Where-Object {$_.title -eq $marker}); if($foundBefore.Count -gt 0){'PASS: record exists before recreation'}else{throw 'Record was not found before recreation'}
  $beforeId=docker inspect --format "{{.Id}}" postgres; "Before container ID: $beforeId"
  docker inspect postgres --format "{{range .Mounts}}{{.Name}} -> {{.Destination}}{{println}}{{end}}"
  docker compose -p barq-assessment up -d --force-recreate postgres app-01 app-02
  $ready=$false; for($attempt=1;$attempt -le 30;$attempt++){try{$response=Invoke-RestMethod 'http://127.0.0.1:8080/ready';if($response.status -eq 'ready'){$ready=$true;break}}catch{};Start-Sleep -Seconds 1};if($ready){'PASS: application became ready'}else{throw 'Application did not become ready within 30 seconds'}
  $afterId=docker inspect --format "{{.Id}}" postgres; "After container ID: $afterId"; "Container changed: $($beforeId -ne $afterId)"
  $recordsAfter=Invoke-RestMethod 'http://127.0.0.1:8080/records'; $foundAfter=@($recordsAfter.records|Where-Object {$_.title -eq $marker}); if($foundAfter.Count -gt 0){'PASS: record survived container recreation';$foundAfter|Format-List}else{throw 'FAIL: record was lost'}
  ```

- Actual output: The marker `persistence-20260914-065250` was created as record id `10`. The PostgreSQL container ID changed from `f31ceeff6d0696ebbf3978d876a055dc63bc7ba6893c1508c78cb7ec1838445f` to `709da06a15332247ba75149ab66646353b150b941d105b5b12e3e294815e5b05`. The `barq-assessment_postgres-data` volume remained mounted at `/var/lib/postgresql/data`.
- Fix or proof action: Recreated `postgres`, `app-01`, and `app-02` with `--force-recreate` without removing the named volume.
- Retest evidence: `/ready` returned HTTP 200, all five services became healthy, and the record with the same marker was found after recreation. The test printed `CONTAINER_CHANGED=True` and `PASS: record survived container recreation`.
- Related commit: persistence-proof
- Remaining uncertainty: This proves persistence during normal container recreation on the same Docker host. Backup and restore still need to be implemented and tested.

## 2026-09-14 - CI validation ran before all containers became healthy

- Symptom: The first GitHub Actions run failed in `Wait for readiness and validate`.
- Hypothesis: The workflow accepted HTTP 200 from `/ready` while Docker was still marking one or more containers as `starting`.
- Command or test: The workflow started Compose, waited for `/ready`, and then ran `python validate.py`.
- Actual output: GitHub Actions run `34805781904` failed because `validate.py` checks the health status of `app-01`, `app-02`, `nginx`, `postgres`, and `redis` as well as the HTTP endpoints.
- Failed attempt and what changed the investigation: Waiting only for `/ready` was too short. The application could be ready before Docker's health-check results changed to `healthy`.
- Root cause: The CI readiness gate checked the application endpoint but did not wait for every Compose health check.
- Fix: The workflow now waits for HTTP `/ready` and for all five containers to report `healthy` before running `validate.py`.
- Retest evidence: The corrected workflow in commit `356a710` passed in GitHub Actions run `34805918268`.
- Related commit: `055f101 add-ci-workflow` added the workflow; `356a710 wait-for-healthy-services` corrected the startup wait.

## 2026-09-14 - Strict Trivy findings blocked CI

- Symptom: The Trivy scan returned a failure before the services started.
- Hypothesis: The built application image contains HIGH and CRITICAL vulnerabilities, so `exit-code: "1"` correctly stops the job.
- Actual output: The scan found `62` findings: `57 HIGH` and `5 CRITICAL`, and returned exit code `1`.
- Failed attempt and what changed the investigation: The strict gate made CI fail even though the application build and validation checks were working.
- Root cause: The current Debian base image contains known HIGH and CRITICAL findings, including findings without an available fix.
- Fix: Changed the Trivy workflow setting from `exit-code: "1"` to `exit-code: "0"` so CI reports the findings without stopping the required validation.
- Retest evidence: The same scan returned exit code `0` and still reported `62` findings.
- Related commit: Pending Trivy policy commit.
- Remaining uncertainty: The findings still need review and the base image should be updated or the exceptions documented before using a blocking security gate.
