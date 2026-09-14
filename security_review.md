# Security and production-readiness review

These are simple security observations from the changes in this task. The follow-up
items are plans for a real production system.

## 1. Database credentials

- Risk and evidence: A password in tracked configuration could be exposed.
- Impact: Someone with the repository could use the database credentials.
- Implemented fix / commit: The password is read from the local ignored `.env` file, with `.env.example` containing safe placeholder values. `docker-networking-nginx`.
- How to verify: Check that `.env` is ignored and that no real password is committed.

## 2. Host port exposure

- Risk and evidence: Publishing app, PostgreSQL or Redis ports would allow direct access that should go through NGINX.
- Impact: Clients could bypass the proxy and reach internal services.
- Implemented fix / commit: Only NGINX publishes `127.0.0.1:8080:80`. `docker-networking-nginx`.
- Production follow-up: Keep internal services private and add firewall rules.
- How to verify: Run `docker compose -p barq-assessment ps` and check the published ports.

## 3. Network separation

- Risk and evidence: Putting every service on one network would let NGINX reach PostgreSQL and Redis directly.
- Impact: A proxy compromise could expose the data services.
- Implemented fix / commit: NGINX uses `frontend`; the apps use `frontend` and `backend`; PostgreSQL and Redis use `backend`. `docker-networking-nginx`.
- Production follow-up: Add platform network policies.
- How to verify: Run `docker network inspect barq-assessment_frontend` and `docker network inspect barq-assessment_backend`.

## 4. Application bind address

- Risk and evidence: Binding the app to `127.0.0.1` caused NGINX `502` errors because the other container could not reach it.
- Impact: Requests failed even though the app process was running.
- Implemented fix / commit: The apps bind to `0.0.0.0` and their ports are not published to the host. `fix-nginx-upstream`.
- Production follow-up: Keep network access restricted and add authentication where required.
- How to verify: Check `APP_HOST` in Compose and request `/health` through NGINX.

## 5. Running as a non-root user

- Risk and evidence: A root process would have more access inside the container.
- Impact: A process compromise could have greater impact.
- Implemented fix / commit: The image creates the `app` user and runs the Flask process as that user.
- Production follow-up: Review permissions again when the image or mounted files change.
- How to verify: Run `docker compose exec app-01 id` and check the process user.

## 6. Image vulnerabilities

- Risk and evidence: The Trivy scan found `62` findings: `57 HIGH` and `5 CRITICAL`.
- Impact: The base image or installed packages may contain known vulnerabilities.
- Implemented fix / commit: Images are pinned by digest and CI reports HIGH and CRITICAL findings with Trivy. `bonus-image-security-scan`.
- Production follow-up: Update the base image and dependencies, then use a reviewed blocking policy.
- How to verify: Open the Trivy step in the GitHub Actions run and review its report.

## 7. Data persistence and backups

- Risk and evidence: Removing a volume would remove PostgreSQL and Redis data. A local volume alone does not protect against machine loss.
- Impact: Records or counters could be lost.
- Implemented fix / commit: Named volumes, Redis append-only persistence, and PostgreSQL backup/restore scripts were added. `docker-networking-nginx`, `persistence-proof`, and `backup-restore`.
- Production follow-up: Store scheduled backups away from the Docker host and test restores regularly.
- How to verify: Run the timestamped persistence test, `./backup.sh`, and `./restore.sh`.

## 8. Availability and monitoring

- Risk and evidence: NGINX is still one entry point and therefore a single point of failure. Container logs alone are limited monitoring.
- Impact: An NGINX failure can stop public traffic, and problems may not be detected quickly.
- Implemented fix / commit: Health checks, restart policies, resource limits, `validate.py`, and `failure_test.py` were added. `validate-and-failure-tests`.
- Production follow-up: Run multiple proxy instances behind a load balancer and add centralized logs and alerts.
- How to verify: Run `docker compose -p barq-assessment ps`, `python validate.py`, and `python failure_test.py`.
