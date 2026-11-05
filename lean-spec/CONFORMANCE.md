# Conformance Bridge — from SPEC invariants to checks the cadence can run

**Purpose:** for each invariant in [SPEC.md](SPEC.md), the exact check
the **existing** cadence could run — where in the pipeline, what it
compares, what it does on failure. This is a bridge document for a
later implementation. **Nothing in the running system was changed**:
no cadence code, no crons, nothing about today's 2 PM slot.

**Grounding caveat:** the cadence code lives in the PC repo
(`C:\Users\ajbig\Documents\grid-project`); it is not on this VM. The
pipeline points below are the ones established by the Nov 1–3 record:
launcher `grid_s3c_repo_launcher.py` (repo workdir, refuses pre-07:00
issuance) → Hermes job `d977b52c965c` (daily 07:00 America/New_York) →
issuance path (fetch → issue, scripts importing from `autopilot/.venv`)
→ receipt write to `docs/s3c/S3C-FIRST-ISSUANCE-<date>.json` → tracker
update in `docs/s3c/CADENCE-TRACKER.md` → alert routing to Darren's
Telegram DM (failures and unscored no-calls). An implementer should
confirm each point against the PC source before wiring it in.

## Summary table

| Inv. | Check point | Compares | On failure |
|---|---|---|---|
| I1 | Issuance path, immediately before writing a scored receipt | latest input day vs target−2, target; availability flag | Write no-call receipt with the specific reason; no score |
| I2 | Launcher, before exec | SHA-256 of resolved artifact vs repo-pinned canonical hash; resolved path inside repo workdir | Refuse to run; missed-day tracker row + alert |
| I3 | Tracker/scoring read path (every read) | Counters recomputed from `docs/s3c/*.json` vs any claimed count | Destination count wins; discrepancy → alert |
| I4 | Launcher, before exec | Cadence interpreter's `sys.executable`; imported dep versions vs repo pin file | Refuse to run; missed-day tracker row + alert |
| I5 | Tracker writer (issuance run + failure handler) | Existing row for target date (must be none); append-only write | Abort + alert; never overwrite |
| I6 | Receipt writer; scoring join | Receipt's `def_hash` = hash of definition file in force at issue | Refuse to score under a mismatched/absent hash |
| I7 | Run wrapper (all exit paths) + post-slot absence check | Tracker row exists for the date by slot+grace | Absence itself fires the alert |
| I8 | Receipt writer; any reader | `issued_at` from clock at write time; `issued_late` recomputed, not trusted | Mismatch → tracker note + alert |

## I1 — Freshness / no-lookahead gate

- **Point:** in the issuance path, after inputs are loaded and before
  the receipt is composed — the same place the pipeline already decides
  `stale_load` today.
- **Compares:** (a) `latest_completed_input_date ≥ target_date − 2`
  (the D-2 ceiling; Nov 1 failed exactly this: Oct 28 < Oct 30);
  (b) `latest_completed_input_date < target_date` (no lookahead, S3c
  Ruling 6); (c) the availability determination is `true` — the loader's
  own as-of-cutoff availability result (e.g., the input batch's
  availability timestamp ≤ the 07:00 index cutoff, per the loader fix
  "exclude post-cutoff batches"), **not** an index page's mtime.
- **On failure:** write the no-call receipt with the *specific* reason
  and stop — no scored receipt, no partial write. Recommended: give
  availability its own reason value (e.g. `availability_unverified`)
  instead of folding it into `stale_load` as Nov 1–2 did, so the two
  failure modes stay distinguishable in the tracker.
- **Fields needed:** none new — `latest_completed_peak_date` and
  `input_availability_verified` are already in the receipts; the check
  is the gate that must *use* them before any scored write.
- **Model counterpart:** `StepOK`'s scored branch; theorem
  `scored_fresh`.

## I2 — Canonical-artifact check (no stale copy)

- **Point:** `grid_s3c_repo_launcher.py`, after resolving the script
  path and before exec — the launcher is the one place every run
  passes through, including directed late runs.
- **Compares:** SHA-256 of the resolved file vs a canonical hash
  pinned in the repo (suggested: a checked-in
  `docs/s3c/CANONICAL-ARTIFACT.sha256` or a field in the cadence
  config, updated only by a deliberate commit); AND the resolved
  absolute path is inside the repo workdir (the Nov 1 stale copy lived
  under `AppData\Local\hermes\scripts\` — outside the repo).
- **On failure:** refuse to run; write the day's tracker row as missed
  with reason `artifact_mismatch`; alert. **Never** fall back to
  another copy — falling back is the failure mode being prevented.
- **Fields needed:** new receipt field `artifact_hash` (the hash of
  what actually ran) so I3's destination check can verify receipts
  after the fact, not just at launch.
- **Model counterpart:** `Config.canonicalHash`; theorem
  `receipt_hash_env`.

## I3 — Counters derived at the destination

- **Point:** wherever the streak/cadence numbers are read or reported
  (tracker update step today; any future scorecard).
- **Compares:** recompute both counters from the receipt store on
  every read — `receiptStreak = #{receipts in docs/s3c/*.json}`,
  `scoredCadence = #{receipts with a scored status}` — and compare
  against any number a run or report claims. Stored/incremented
  counters are not consulted.
- **On failure (claimed ≠ recomputed):** the recomputed count wins;
  the discrepancy is written to the tracker as a note and alerted. A
  claimed score with no receipt file at the destination is exactly
  the discrepancy case (Nov 1's lesson: a producer's report is not a
  receipt).
- **Fields needed:** none.
- **Model counterpart:** `countWith_step` + the three append
  corollaries; `lookupDay_spec` / `lookupDay_complete`.
- **Open reading (flagged in SPEC I3):** whether a no-call day also
  *resets* the S7 "14 consecutive" run is unsettled by the record;
  `scoredRun` is defined in the model so both numbers can be reported
  until Darren rules.

## I4 — Environment probe (one environment, stated once)

- **Point:** the launcher, before exec — run with the *cadence
  interpreter itself* (the one that will run the scripts), never with
  whatever python is on PATH.
- **Compares:** (a) `sys.executable` resolves to the pinned venv
  (`autopilot/.venv`); (b) for each pinned dependency (duckdb first —
  the Nov 3 failure), import it from that interpreter and compare
  `__version__` to the repo's pin file (the record's pinned value:
  duckdb 1.4.4). This is precisely the probe the Nov 3 repair ran by
  hand (import + trivial query, SHA-256 of the package matched
  pre/post copy) — the check promotes it from a repair step to a
  launch gate.
- **On failure:** refuse to run; missed-day tracker row with reason
  `env_mismatch` (name the dep and the found vs pinned version);
  alert. Do not "fix" it by installing at launch time — a launch that
  mutates its own environment destroys the evidence of the split.
- **Fields needed:** none new in receipts; the pin file already exists
  implicitly in the repair record — it should be a single checked-in
  file the launcher reads (the "stated once" half).
- **Model counterpart:** `Config.envId`; theorem `receipt_hash_env`.

## I5 — Append-only tracker writes

- **Point:** the tracker writer, used by both the issuance run and
  its failure handler.
- **Compares:** before writing, assert **no row exists for the target
  date**; the write is an append of exactly one row. Late/directed
  runs follow the same rule: if the day already has a row, the late
  run appends a *note* (the Nov 1 pattern — ruling in the tracker,
  receipt untouched), never a replacement row and never an edited
  receipt.
- **On failure (row already exists):** abort the write, alert. An
  existing row is evidence, not an obstacle.
- **Fields needed:** none.
- **Model counterpart:** `Reachable` (append-only by construction);
  theorems `day_bounds`, `day_unique`, `extends_prefix`,
  `lookupDay_persistent`, `no_backfill`.

## I6 — Definition hash on every receipt

- **Point:** the receipt writer (stamp the hash of the definition
  file in force at issue time into the receipt); the scoring join
  (read the definition from the receipt's own hash).
- **Compares:** receipt's `def_hash` vs the hash of the definition
  file the run actually used; scoring refuses a receipt whose
  `def_hash` is absent or doesn't resolve to a definition file in the
  repo's (append-only) definition history.
- **On failure:** receipt is written but flagged unscorable; alert.
  Definition files are amended by adding a new version, never by
  editing one an existing receipt references (git history is the
  enforcement of last resort, as in PLAN.md's ledger rules).
- **Fields needed:** `def_hash` in the S3c receipt JSON (unchecked
  whether present today — see SPEC I6 status).
- **Model counterpart:** whole-record persistence
  (`lookupDay_persistent`, `no_backfill`); the model's Config
  deliberately has no current-definition field.

## I7 — No silent slot (record + alert)

- **Point:** two places. (1) The run wrapper: *every* exit path —
  scored, no-call, exception, guard-skip (the Nov 3 three-miss guard
  logged its 'skipped' attempt; that log must also land as the day's
  tracker row or a tracker note pointing at it) — writes exactly one
  tracker row for the date. (2) A post-slot absence check: at
  slot+grace (suggested: 07:30 local, and again after the 19:00Z
  window on days it applies), assert a row exists for the date.
- **Compares:** row-for-date presence at the destination (the tracker
  file), not process exit codes and not the producer's log.
- **On failure:** absence itself is the alert — routed to the same
  Telegram DM path the Nov 1 fixes established for failures and
  unscored no-calls (that routing was verified with a synthetic
  failure test on Nov 1; the gap was that the *issuance* failure's
  incident delivery was suppressed, which is what this check makes
  structurally impossible to miss: silence becomes the loudest
  signal).
- **Fields needed:** none.
- **Model counterpart:** `day_surjective`, `lookupDay_complete`
  (record-existence half only — delivery is process, per SPEC I7).

## I8 — True timestamps

- **Point:** receipt writer (stamp `issued_at` from the system clock
  at write time; no parameter, no override) and any reader
  (recompute `issued_late := issued_at > slot_time` from the fields).
- **Compares:** recomputed lateness vs any asserted flag; the
  launcher's existing refusal of pre-07:00 issuance stays as the
  first half of the check.
- **On failure (asserted ≠ recomputed, or `issued_at` < slot):**
  tracker note + alert; the receipt is not edited to agree — the
  discrepancy is the record.
- **Fields needed:** none (`issued_at`, `issued_late` already exist).
- **Model counterpart:** `never_early`; `IsLate` as a derived
  definition.

## Implementation order (if Darren green-lights it later)

Cheapest first, each independently useful: **I4 probe** (a few lines
in the launcher; would have caught Nov 3 before the slot) → **I2 hash
check** (same place; would have caught Nov 1) → **I1 reason split**
(distinguish availability from staleness in no-call reasons) → **I5/I7
tracker discipline + absence check** → **I3 derived counters** →
**I6 def_hash field** → **I8 recompute**. None of this is authorized
by the spec itself; it is sequenced only so a future go can be
scoped.
