# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts

script: `scripts/analyze_logs.py`

commands : `python scripts/analyze_logs.py`

## Results

Q1: What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
  access.log: 2026-08-20T11:00:00.015Z to 2026-08-20T11:29:57.578Z; total=726, valid=725, malformed=1, duplicate extra lines=5
  error.log: 2026-08-20T11:05:02.000Z to 2026-08-20T11:30:00.000Z; total=68, valid=68, malformed=0, duplicate extra lines=0
  application.log: 2026-08-20T11:00:00.015Z to 2026-08-20T11:29:57.578Z; total=730, valid=729, malformed=1, duplicate extra lines=2
  Valid includes parseable duplicate lines; duplicate extras are removed

Q2: How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
  Distinct request_id values in access.log: 720
  Exact duplicate access lines removed: 5;
  Using dictionary that only counts the valid request_id only once

Q3: What are the final client status counts and error rate? State your denominator.
  200: 615
  404: 10
  502: 40
  503: 47
  504: 8
  5xx error rate: 95/720 = 13.19% (denominator: distinct client requests).

Q4: Which paths, time windows and backends account for the failures?
  Paths:
  /: 10
  /counter: 26
  /health: 10
  /ready: 23
  /records: 26
  UTC minutes:
  2026-08-20T11:05Z: 8
  2026-08-20T11:06Z: 8
  2026-08-20T11:07Z: 8
  2026-08-20T11:08Z: 8
  2026-08-20T11:09Z: 8
  2026-08-20T11:12Z: 8
  2026-08-20T11:13Z: 7
  2026-08-20T11:14Z: 8
  2026-08-20T11:15Z: 8
  2026-08-20T11:20Z: 8
  2026-08-20T11:21Z: 8
  2026-08-20T11:25Z: 4
  2026-08-20T11:26Z: 4
  Final upstream backends:
  172.23.0.11:8080: 27
  172.23.0.12:8080: 68

Q5: What are the median and p95 client latencies? State the percentile method and units
  Median: 0.054 seconds (54.0 ms)
  p95: 2.001 seconds (2001.0 ms)
  Method: median of 720 sorted request_time values; p95 is  latencies_seconds[ceil(0.95 * n)] .

Q6: Which requests retried upstream? How many succeeded after retrying?
  lab-000124 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000130 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000136 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000142 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000148 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000154 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000160 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000166 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000172 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000178 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000184 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000190 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000196 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000202 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000208 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000214 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000220 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000226 /instance: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  lab-000232 /ready: 172.23.0.12:8080 -> 502; 172.23.0.11:8080 -> 200; final client status=200
  Retried requests: 19; succeeded after retry: 19.

## Timeline and correlated examples

Q7: Build an incident timeline using evidence from access, error AND application logs.
  2026-08-20T11:00:00.015Z - access.log begins with lab-000001 status 404
  2026-08-20T11:05:02.000Z - error.log connection refused: 59 events through 2026-08-20T11:09:57.000Z
  2026-08-20T11:05:02.503Z - access.log first 5xx: lab-000122 /health status 502
  2026-08-20T11:12:09.524Z - application.log redis TimeoutError: 31 events through 2026-08-20T11:15:52.024Z
  2026-08-20T11:20:07.540Z - application.log postgres InvalidPassword: 16 events through 2026-08-20T11:21:45.040Z
  2026-08-20T11:25:14.000Z - error.log upstream timeout: 8 events through 2026-08-20T11:26:47.000Z
  2026-08-20T11:26:47.001Z - access.log last 5xx: lab-000643 /records status 504
  2026-08-20T11:29:57.578Z - access.log ends with lab-000720 status 200
  2026-08-20T11:30:00.000Z - error.log notice: 1 events through 2026-08-20T11:30:00.000Z

Q8: Show one correlated failed request and one successful request. Include IDs and timestamps.
  Failed lab-000122: access.log 2026-08-20T11:05:02.503Z /health status=502 upstream=172.23.0.12:8080 upstream_status=502.
  error.log 2026-08-20T11:05:02.000Z: connection refused to http://172.23.0.12:8080/health.
  application.log: no matching http_request; the app did not handle it.
  Successful lab-000002: access.log 2026-08-20T11:00:02.532Z /health status=200 upstream=172.23.0.12:8080; application.log 2026-08-20T11:00:02.532Z app-02 status=200; no matching error.log entry.

Q9: Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
  Proxy/connectivity: 67 request IDs appear in NGINX error records; 48 ended as 5xx, 19 recovered, and 40 have no matching application http_request.
  Proof: error.log reports connection refusals or upstream timeouts.
  Dependency/application: 47 request IDs have dependency_error events; 47 ended as client 5xx.
  Dependency event types:
  postgres InvalidPassword: 16
  redis TimeoutError: 31
  Proof: application.log names the dependency and error type for the same request_id found in access.log.

## Conclusions and limits

### Conclusions

The logs contain 720 distinct client requests. NGINX returned 95 server errors: 40 responses were HTTP 502, 47 were HTTP 503, and 8 were HTTP 504. Using all distinct client requests as the denominator, the server-error rate was 13.19%.

The first major failure occurred at approximately 11:05 UTC. NGINX reported connection refusals to `172.23.0.12:8080`, which produced HTTP 502 responses. 19 requests retried through another upstream and eventually succeeded. 40 failed requests have no matching application request.

The evidence shows three separate failure types: upstream connection failures, dependency failures inside the application, and upstream response timeouts.

### Limits

Q10: What do the logs not prove? What would you check next in a running environment?

- Whether the upstream service was stopped, listening on the wrong address, or affected by another network problem.
- The current state of any container.
- The contents of PostgreSQL or Redis.
- Whether a missing application log means the request never arrived or was not logged.
- Whether the same errors would happen in another test run.

If I were checking the environment while it was running, I would use these commands:

```powershell
docker compose ps -a
docker compose logs --no-color nginx app-01 app-02 postgres redis
docker exec nginx wget -qO- http://app-01:8080/health
docker exec nginx wget -qO- http://app-02:8080/health
docker network ls
docker inspect nginx app-01 app-02 postgres redis
```
