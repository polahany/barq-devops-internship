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
- Fix: Deferred to the second fixing iteration.
- Retest evidence: `fix-1-http-health.txt` shows `/ready` HTTP 503; `fix-1-runtime-logs.txt` contains the authentication failure.
- Related commit: fix-the-initial-investigation
- Remaining uncertainty: `/ready` must return HTTP 200 after the credentials match.
