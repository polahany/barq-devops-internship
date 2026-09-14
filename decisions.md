# Technical decisions

These are the main decisions I made during Parts 1 and 2. They describe why I chose each solution, what other option I considered, and the current limits of the solution.

## 1. Use `/health` as the application liveness endpoint

- Choice: I changed the Docker health check from `/healthz` to `/health`.
- Why: The Flask application already had a `/health` endpoint that returned HTTP 200. There was no `/healthz` endpoint, so Docker received HTTP 404 and marked both app containers unhealthy.
- Alternative: I could add a new `/healthz` route to the application.
- Trade-off: Updating Compose was the smallest fix and avoided adding two routes with the same purpose. A system already expecting `/healthz` would need its configuration changed.
- Assumption: `/health` is the intended liveness endpoint because it already exists in the application and is required by the task, also the endpoints are mentioned in part 2.
- Limit: `/health` only proves that the Flask process is responding. It does not prove that PostgreSQL or Redis is working.
- Evidence / commit: `c380bd1 fix-the-initial-investigation` and `evidence/local/fix-1-app-probes.txt`.
- Production improvement: Keep liveness and readiness as separate checks and document what each endpoint tests.

## 2. Use the normal container ports for PostgreSQL and Redis

- Choice: The app connects to PostgreSQL on `postgres:5432` and Redis on `redis:6379`.
- Why: These are the ports used by the services inside the Compose networks. The original app configuration used ports that were not listening.
- Alternative: I could change the database and Redis services to listen on the incorrect ports or publish host ports and connect through the host.
- Trade-off: Using the standard internal ports is simpler, but the app depends on Compose DNS resolving the service names.
- Assumption: All services run in the same Compose project and can resolve each other by service name.
- Limit: The current addresses are designed for this Compose environment and would need different values in another platform.
- Evidence / commit: `c380bd1 fix-the-initial-investigation` and `evidence/local/fix-1-app-probes.txt`.
- Production improvement: Supply the connection addresses through a deployment secret or configuration system for each environment.

## 3. Bind Flask to all container interfaces

- Choice: I changed `APP_HOST` from `127.0.0.1` to `0.0.0.0`.
- Why: Binding to `127.0.0.1` only allowed requests from inside the same app container. NGINX is in a different container and needs to reach the app through the frontend network.
- Alternative: NGINX and the app could run in the same container, but that would mix two services and would not match the required architecture.
- Trade-off: The app listens on every interface inside its container, so network access must be controlled with Compose networks. Its port is not published to the host.
- Assumption: Only containers connected to the same Docker network should be able to reach the app port.
- Limit: Docker network separation is useful isolation, but it is not a replacement for authentication or firewall rules in production.
- Evidence / commit: `1d21669 fix-nginx-upstream` and `evidence/local/fix-nginx-upstream-http-health.txt`.
- Production improvement: Add application authentication and platform network policies when deploying outside this lab.

## 4. Publish only NGINX and separate frontend and backend traffic

- Choice: NGINX, `app-01`, and `app-02` use the `frontend` network. The apps, PostgreSQL, and Redis use the internal `backend` network. Only NGINX publishes host port `8080`.
- Why: Users should enter through NGINX, while PostgreSQL and Redis should not be directly reachable from the host or from NGINX.
- Alternative: Put every container on one network and publish all ports to the host.
- Trade-off: Two networks give better isolation, but make the Compose file slightly more detailed.
- Assumption: The apps are the only services that need access to both the public request path and the dependencies.
- Limit: NGINX is still a single point of failure in this Compose setup.
- Evidence / commit: `60d482f docker-networking-nginx`; Docker inspection showed NGINX only on frontend and the dependencies only on backend.
- Production improvement: Run more than one proxy instance behind a managed load balancer.

## 5. Keep secrets in a local ignored `.env` file

- Choice: Compose reads local secret values from `.env`. The repository contains a safe `.env.example`, and `.env` and `config/app.env` are ignored. The app startup log reports only whether configuration exists.
- Why: The original files included a database password in tracked configuration and copied the configuration into the image.
- Alternative: Keep the values in Compose, bake the file into the image, or use Docker secrets.
- Trade-off: A local `.env` file is simple for this assignment, but every developer must create and protect their own copy.
- Assumption: The real `.env` file stays outside Git and is not included in submitted evidence.
- Limit: `.env` is not a complete production secret-management solution, and environment variables may still be visible to users who can inspect the container.
- Evidence / commit: `60d482f docker-networking-nginx`; Git no longer tracks `config/app.env`, and `/srv/app.env` is absent from the app image.
- Production improvement: Use a secret manager or Docker/Kubernetes secrets with controlled access and secret rotation.

## 6. Persist PostgreSQL and Redis data with named volumes

- Choice: PostgreSQL stores data in `postgres-data` at `/var/lib/postgresql/data`. Redis uses append-only persistence and stores its data in `redis-data` at `/data`.
- Why: Container files disappear when containers are recreated. Named volumes allow records and counter data to survive container recreation.
- Alternative: Keep PostgreSQL on `tmpfs` and run Redis without persistence.
- Trade-off: Persistence uses disk space and requires backup and cleanup plans, but it prevents normal container recreation from deleting the data.
- Assumption: Docker volumes remain available on the same machine during the assignment.
- Limit: A local named volume does not protect data if the machine or Docker storage is lost.
- Evidence / commit: `60d482f docker-networking-nginx`; Docker inspection showed both named volumes mounted at the correct data paths.
- Production improvement: Add automated backups, tested restores, storage monitoring, and off-machine backup copies.

## 7. Add restart policies and small resource limits

- Choice: All services use `restart: unless-stopped`. The apps use `0.50` CPU and `256 MB`, PostgreSQL uses `1.0` CPU and `512 MB`, and Redis and NGINX use `0.50` CPU and `128 MB`.
- Why: The restart policy helps services recover after an unexpected exit. Resource limits stop one container from using all resources on the machine.
- Alternative: Use no restart policy or resource limits, or use `restart: always`.
- Trade-off: `unless-stopped` respects a manual stop, but it can keep restarting a service with a permanent configuration error. The selected limits are suitable for the lab but were not chosen from load testing.
- Assumption: The assignment workload is small and fits inside these limits.
- Limit: These values do not prove how the system will behave under real production traffic.
- Evidence / commit: `60d482f docker-networking-nginx`; Docker inspection confirmed the memory and CPU limits.
- Production improvement: Measure real CPU and memory usage, then set requests, limits, and alerts using those measurements.

## 8. Analyze the supplied logs with a small Python script

- Choice: I used `scripts/analyze_logs.py` to read all three supplied logs, calculate the requested counts, connect events by request ID, and print the incident timeline.
- Why: A script makes the results repeatable and reduces mistakes from counting records manually. The original log files remain unchanged.
- Alternative: Use several `rg`, PowerShell, or Bash commands, or count the events by hand.
- Trade-off: The Python script is easier to rerun, but its parsing is written for the supplied log formats and may need changes for other logs.
- Assumption: The supplied logs are test data with a consistent format and timestamps.
- Limit: The results describe this test dataset only. They do not prove how a live production system behaves.
- Evidence / commit: `24da9a3 log-analysis`, `scripts/analyze_logs.py`, and `log_analysis.md`.
- Production improvement: Use centralized structured logging, dashboards, and alerts instead of analyzing separate files manually.
