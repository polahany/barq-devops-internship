<img src="assets/barq-logo.svg" alt="BARQ Systems" width="180">

# DevOps Internship Task - Starter v2

**Due date:** ____________________

**Time window:** 4 calendar days from the invitation email date/time.

Read [the task](assessment/TASK.md), then [the API contract](assessment/APPLICATION.md).
Everyone receives this same release. The environment is intentionally broken.
Hidden issue types and count are not disclosed. Investigate this project; do not replace it.

## Included

- Flask API, PostgreSQL, Redis, Docker and NGINX starter files.
- Three historical logs, a question template and documentation templates.
- App-only tests and a recorded challenge script.
- Validation, failure-test, backup, and restore scripts for Part 3.

Use synthetic lab accounts/data only. Supplied values are for this disposable exercise,
never for real services. Keep the lab on your local machine; do not expose it publicly.

## Before you start

- Linux or WSL2, Python 3.12, Git and Docker with Compose.
- Docker Desktop must use Linux containers. Run shell scripts in Linux/WSL.
- Suggested capacity: 2 CPU cores, 4 GB free RAM and 3 GB free disk, plus Docker overhead.
- Internet for first downloads and GitHub. No cloud account or paid registry required.
- Use a machine where container names app-01, app-02, nginx, postgres and redis are unused.
  Do not delete someone else's containers to free those names.
- Intended public port: 8080 before the video, 8090 after the live change.
  If either is occupied, ask the organizer for a documented workstation exception.

## Start

Clone the supplied Git bundle/repository. Keep both release commits and the v2 baseline tag.
Set your own Git name/email before making changes.

From the repository root:

```bash
git status
git log -2 --oneline
cp .env.example .env
docker version
docker compose version
docker compose -p barq-assessment up --build -d
docker compose -p barq-assessment ps -a
docker compose -p barq-assessment logs --no-color
```

The initial environment is not expected to pass. Record what actually happens.
The intended URL is http://127.0.0.1:8080; do not assume the starter configuration is correct.

App-only checks use fake dependencies, not real SQL/Redis or Docker networking:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Persistence proof

This test proves that a PostgreSQL record survives container recreation because the database uses a named volume. Run these commands in the same PowerShell window so `$marker` and the container IDs remain available.

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
docker compose -p barq-assessment ps
```

Expected proof: the PostgreSQL container ID changes, the named volume is mounted at `/var/lib/postgresql/data`, readiness returns `200`, and the record with the same timestamped title is found afterward. Do not run `docker compose down -v` during this test because it deletes the volume.

## Backup and restore proof

Run the shell scripts from WSL or Git Bash while the Compose services are healthy. The backup is a PostgreSQL custom-format dump. The restore script uses a separate `barq_restore_test` database, so it does not overwrite the working database.

```bash
MARKER="backup-$(date -u +%Y%m%d-%H%M%S)"
curl -fsS -X POST http://127.0.0.1:8080/records -H 'Content-Type: application/json' -d "{\"title\":\"$MARKER\"}"
./backup.sh
DUMP=$(ls -t backups/*.dump | head -n1)
./restore.sh "$DUMP" "$MARKER"
```

Expected output includes `PASS: backup created` and `PASS: backup restored`. Backup files stay under `backups/` and must not be committed.

## Your work

- Complete [assessment/TASK.md](assessment/TASK.md).
- Complete validate.py, failure_test.py, backup.sh and restore.sh, or documented equivalents.
- Create .github/workflows/ci.yml yourself.
- Complete the root report templates and docs/EVIDENCE_INDEX.md.
- Add architecture.png or architecture.pdf.
- Replace this README with copyable setup/build/run/test/failure/backup/restore/cleanup commands.
- Commit as you work. Do not commit real secrets, backups, virtual environments or challenge state.

## Recorded challenge

Use the supplied video_challenge.sh unchanged. Read its code if needed; do not run it early.
After repairing the environment, run it once, for the first time in the video working copy,
during the continuous 12-18 minute recording. The script requires healthy services, both
initial instances and the target network layout. Preflight failures make no runtime changes.

```bash
./video_challenge.sh
```

If you deliberately changed the project name, pass --project YOUR_PROJECT.
An organizer-approved alternate local URL can be passed with --url http://127.0.0.1:PORT.
The script touches only matching Compose-owned lab containers/networks.
Keep the receipt in .assessment/challenge.json for the evidence index. Do not delete the
one-run marker to retry. A local marker is not tamper-proof; ownership is judged from evidence.
Do not use docker compose down to reset the runtime challenge.

## Stop safely

Outside the recorded challenge, docker compose -p barq-assessment down stops this lab.
Do not use --volumes during persistence tests. Avoid global Docker prune/cleanup commands.
Back up anything you need before removing containers; investigate whether data actually persists.
