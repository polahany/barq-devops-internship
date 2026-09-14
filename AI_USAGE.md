# AI usage disclosure


- Tool/model: OpenAI Codex (GPT-5)
- Purpose: Document the initial application findings before any fixes and record the commands used to test the environment.
- Files or decisions affected: `troubleshooting.md`.
- What was changed or rejected: changed the `troubleshoot.md` to exactly match my investigation
- How it was independently verified: investigating the `intial-app-probes.txt` file and the `docker-compose.yml`
- Related commit: Investigate initial health, readiness, identity and NGINX issues

- Tool/model: OpenAI Codex (GPT-5)
- Purpose: used AI to help implement the parsing functions in the analysis script , also to make the final printed output more professional
- Files or decisions affected: `analyze_logs.py` , `log_analysis.md`
- What was changed or rejected: changed the format of the output , rejected overengineered parsing algorithm
- How it was independently verified: reviewed the code
- Related commit: log-analysis

- Tool/model: OpenAI Codex (GPT-5)
- Purpose: used AI to help implement `validate.py` and `failure_test.py` with the given scenarios in the report
- Files or decisions affected: `validate.py` and `failure_test.py`
- What was changed or rejected: N/A
- How it was independently verified: reviewed the code and the inspected the output
- Related commit: validate-and-failure-tests

- Tool/model: OpenAI Codex (GPT-5)
- Purpose: used AI to write simple PowerShell commands for creating a new persistance record
- Files or decisions affected: N/A
- What was changed or rejected: added a timestamped record marker
- How it was independently verified: reviewed the commands against the Compose named volume and `/records` endpoint, then ran the test. The PostgreSQL container ID changed, readiness returned HTTP 200, and the timestamped record was found after recreation.
- Related commit: persistence-proof

You may use AI and external resources. You must understand and demonstrate the work.
