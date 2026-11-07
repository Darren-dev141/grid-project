# Grid Project — AWS + Docker Deployment Status (2026-11-06)

Task: Beat the Grid — AWS deployment + Docker pipeline container ("deploy now", Darren, Nov 6, 2026).
Plan of record: PLAN.md decision 6 (AWS) + Oct 29 S5 stack note (Docker) + Workstream B.

## Lane/model
- Lane: keep_current (direct execution).
- Model: reflection/beam-1.0-501b-a23b:free (nous).

## STEP 1 — AWS credentials: BLOCKED (no usable credentials)
- `aws --version` → aws-cli/2.39.3 (on PATH via C:\Users\ajbig\AppData\Local\Programs\AWSCLIV2\...).
- `aws sts get-caller-identity` → `NoCredentials: Unable to locate credentials` (exit 253). No Account ID obtainable.
- `aws login --region us-east-1` was run. CLI printed "Attempting to open your default browser" and an authorize URL:
  `https://us-east-1.signin.aws.amazon.com/v1/authorize?response_type=code&client_id=arn:aws:signin:::devtools/same-device&...&redirect_uri=http://127.0.0.1:<port>/oauth/callback`
  The process then waited for the OAuth callback on localhost and **timed out after 180s** without completing. No credentials persisted: `~/.aws/login` (token cache) does not exist; `~/.aws/cli/cache/session.db` has a partial row but no usable profile. `~/.aws/config` has region us-east-1 only.
- Stopped at: **AWS sign-in authorization page in the default browser** — interactive sign-in/MFA/consent that only Darren can approve. No account ID, root MFA, budgets, or bucket could be checked/created.
- Account ID: NOT OBTAINED. Bucket name: NOT CREATED (template only: `grid-raw-lake-<12-digit-account-id>`).

### Unblock (exact action for Darren)
In a fresh terminal on this PC:
```
aws login --region us-east-1
```
Complete the browser flow until the CLI prints `Updated profile default to use arn:aws:sts::<12-digit-account-id>:assumed-role/...`, signing in to the AWS account (12-digit account ID), not only a Builder ID. Then verify with `aws sts get-caller-identity` (must return AccountId + Arn) before re-running Step 3. If the browser callback does not land, check firewall/consent blocking `aws.exe` localhost callback; do not paste credentials.

## STEP 2 — Docker pipeline container: BLOCKED on daemon (Dockerfile delivered)
- `docker --version` → Docker version 29.8.2, build 7fc2dff (CLI installed at C:\Program Files\Docker\...).
- Docker daemon NOT running: Docker Desktop service `com.docker.service` is STOPPED; `net start` → "Access is denied" (no admin). WSL Ubuntu has no `dockerd` binary and no `/var/run/docker.sock`. No podman/nerdctl available. Docker Desktop cannot be started from this session and will not be installed per bounds.
- Therefore image build and in-container run could NOT be executed. No paid/installed software added.
- Dockerfile written: `C:\Users\ajbig\Documents\grid-project\Dockerfile` (image name/tag target: `grid-pipeline:dev`), packaging Python 3.11 + project deps + dbt + source. Build command (for when daemon is up): `docker build -t grid-pipeline:dev .`
- Host-side baseline cycle (same commands the container would run) executed for evidence, against a copy of the local warehouse:
  - Warehouse: copy of `data/s1-live/grid.duckdb` (12,070,912 bytes) → scratch hostcycle/grid.duckdb.
  - dbt build (target local, `--vars '{bge_pnode_id: 999}'`): 85 data tests + 12 views, 1 warning (demand_quality_not_ok: 131 rows, configured warn), 0 errors, TOTAL 98, 5.37s.
  - Brief render: `grid_pipeline.brief` → target 2026-11-06, **no call (stale_load)**. Wrote index.html + comment.md.
  - Output hashes: index.html `1a704cca...7ce696`, comment.md `700cd6fe...74ba5dab`.
  - Key number surfaced: peak 2026-11-04: missing.
- Comparison container vs host: NOT PERFORMED (no container run). The host cycle is recorded as the baseline the container run must match once the daemon is available.

### Unblock (exact action for Darren)
Start Docker Desktop (double-click / Start menu) so `com.docker.service` runs, or run an elevated terminal: `net start com.docker.service`. Then re-run `docker build -t grid-pipeline:dev .` and the in-container cycle. No install needed (Docker Desktop is already installed).

## STEP 3 — AWS deployment: NOT PERFORMED (gated on Step 1)
Step 1 produced no credentials, so Step 3 is skipped per task rules. No AWS resources created, no budgets, no bucket, no Athena/Lambda/EventBridge, no S3 brief page. Free-tier-only and no-credentials-in-repo bounds honored.

### What would run once credentials exist (unchanged plan)
- Budget guard: check `aws budgets describe-budgets`; create ~$1 and ~$5 monthly alerts if missing (authorization for creation still pending confirmation; Nov 5 report treated as not authorized → report only).
- Private bucket `grid-raw-lake-<12-digit-account-id>` in us-east-1, all Block Public Access on, SSE-S3, versioning, no objects.
- Backfill EIA demand / NWS forecasts / NCEI BWI history as parquet/CSV mirroring local raw/cleaned layout.
- Athena external tables + core SQL vs DuckDB comparison (same numbers = pass).
- Lambda + EventBridge daily ingestion if it fits Lambda limits; otherwise stop with evidence.
- Brief page to S3 public (page only).
- Gate: one full daily cycle on AWS with outputs matching local.

## Gate verdict
- AWS gate: NOT EVALUATED (no credentials).
- Docker gate: NOT EVALUATED (no daemon).
- Local host cycle: PASS (dbt build 0 errors, brief rendered no-call stale_load).

## Notes on repo changes made during this run
- Recovered 28 base64-encoded project files (pyproject.toml, dbt config/models/tests, brief.py, md_geo.py, test_brief.py, site/*, scripts/load_raw_to_postgres.py, vercel.json) to plain text so the pipeline and tests run. This was required for dbt/brief to execute. No PLAN.md edits. No git push. No credentials stored in repo.
- Added `Dockerfile` (grid-pipeline:dev target).
- Did not touch the LinkedIn draft.

## ROUND 2 — executed 2026-11-06

### Step 0 hard gate: PASS
- `aws sts get-caller-identity` → Account 282760521446, Arn root, region us-east-1.
- `docker info` → Server Version 29.8.2 (daemon responding).

### 1. Docker image + in-container cycle
- Image: grid-pipeline:dev, digest sha256:1d2630bca51d50d81411980868503e1712892ada413e0993fecf9a405b7af9c9, size 950821643 bytes.
- In-container dbt build: PASS=97 WARN=1 ERROR=0 TOTAL=98 (matches host).
- In-container brief: target 2026-11-06, no call (stale_load) (matches host).
- Comparison: dbt results identical; brief target/level identical. Rendered footer differs only in last-load-hour display (host 06:00 UTC vs container 02:00 UTC) due to OS-local TZ interpretation of a naive timestamp in `_fmt_time`; underlying max(hour_utc) identical in both warehouses (2026-10-29 02:00). Generated timestamp also differs. Numbers match; environment-dependent display differs.

### 2. AWS resources
- Budgets: grid-monthly-1usd and grid-monthly-5usd created, with 80%/100% ACTUAL notifications to SNS topic arn:aws:sns:us-east-1:282760521446:grid-budget-alerts. (Email subscription to the topic still needs Darren's confirmation.)
- S3 bucket: grid-raw-lake-282760521446 created, Block Public Access all on, versioning enabled, SSE-S3 (AES256). Raw backfill uploaded: raw/eia (17 files), raw/nws (2 files), raw/ncei (2 files). Cleaned parquet uploaded: cleaned/eia_pjm_hourly_demand/, cleaned/mart_day_history/.
- Athena: database grid; external tables grid.eia_demand (68594 rows) and grid.mart_day_history (2859 rows). Comparison vs DuckDB: count 68594 = 68594, sum demand_mwh 10436341869.0 = 10436341869.0; mart rows 2859 = 2859. PASS.
- Lambda + EventBridge: NOT DEPLOYED. Reason: pipeline image is 951 MB and the scheduled run needs dbt + DuckDB + a persistent file-backed warehouse; the plan's designated runner is GitHub Actions (PLAN decision 2). Lambda packaging not pursued.
- S3-hosted brief page: http://grid-brief-282760521446.s3-website-us-east-1.amazonaws.com/ (bucket grid-brief-282760521446, public read via bucket policy; lake bucket remains private). HTTP 200 verified.

### 3. GATE VERDICT: NO
No full daily cycle ran on AWS (no AWS-side ingestion). Athena-vs-DuckDB numbers match and the brief page is live, but ingestion and brief generation on AWS did not occur, so the gate is not satisfied.
