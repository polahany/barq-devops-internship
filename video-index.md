# Part 5 video index

I will fill in the timestamps after recording. Each timestamp should point to the
start of the matching demonstration in the continuous 12–18 minute video.

## Video details

- Video URL: 
- Video duration: 
- Repository URL: https://github.com/polahany/barq-devops-internship
- Starting video commit: 
- Final commit: 
- Green CI run: 
- Challenge receipt ID: 

## Demonstration index

| Time    | Point to show | What I show or explain | Expected result |
|---------|---|---|---|
| `01:40` | Clean start and challenge readiness | Show `git status --short`, recent log, stopped Compose project, and the missing `.assessment/challenge.lock` | Git is clean, no containers run, and the challenge has not been attempted. |
| `02:30` | Build, health, and initial API | Build/start the stack, show `ps -a`, the `8080:80` mapping, `/health` versus `/ready`, then request `/`, `/health`, `/ready`, `/records`, and `/counter` | NGINX, app-01, app-02, PostgreSQL, and Redis are healthy; required endpoints return 200. |
| `03:20` | Load balancing | Send repeated `/instance` requests through NGINX | Both `app-01` and `app-02` appear. |
| `04:10` | Failure and recovery | Stop app-01, send repeated requests, start it again, wait for healthy, and repeat requests | Some requests still reach app-02, gateway errors show the failure, and app-01 serves traffic after recovery. |
| `05:20` | Persistence and automated checks | Create a timestamped record, show the named volume, recreate PostgreSQL/apps, query the marker, then run `validate.py`, `failure_test.py`, and one log-analysis finding | The container ID changes but the record survives; validators pass and log counting avoids duplicates/retries. |
| `11:20` | Challenge run, diagnosis, repair, and retest | Run `./video_challenge.sh` once, show the receipt, inspect state/networks and requests, apply the matching targeted repair, and rerun validation | One runtime fault is identified and repaired without `docker compose down`; readiness and validation pass. |
| `15:00` | Change the public port | Edit tracked defaults and validation URLs from 8080 to 8090 by hand, recreate NGINX, test 8090 and the old port | Port 8090 works, port 8080 is closed, and `.env` remains local. |
| `19:50` | Add and prove app-03 | Add app-03, its identity/networks, the NGINX upstream/dependency, and validator/CI expectations; send repeated requests on 8090 | app-01, app-02, and app-03 appear; all six containers are healthy. |

## What I will say about the challenge

- I ran the supplied challenge for the first and only time in this video copy.
- It changes runtime state only and does not change the source files.
- I diagnosed the fault from container state, network membership, readiness, and request results.
- I repaired only the fault that the evidence identified.
- I did not delete `.assessment/challenge.lock` and did not run `docker compose down` after applying the challenge.

## Final evidence to fill in

- Starting commit shown at: `__:__`
- Challenge receipt shown at: `__:__`
- Challenge repair shown at: `__:__`
- Port 8090 shown at: `__:__`
- app-03 shown at: `__:__`
- Final green validation shown at: `__:__`
- Final commit and push shown at: `__:__`

Backup and restore are covered by the Part 3 files and written evidence. The required
live storage demonstration in this video is the PostgreSQL container recreation proof.
