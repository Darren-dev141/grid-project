# Grid Issuance Ledger + Data-Freshness Specification

**Status:** specification + formal model, built Nov 3, 2026 on Darren's go
(his Nov 2 ruling: Lean YES for grid cadence/issuance-ledger + freshness
spec; Bend NO). **This document changes nothing in the running system.**
Implementation bridge: [CONFORMANCE.md](CONFORMANCE.md). Formalization:
[lean/GridLedger.lean](lean/GridLedger.lean) (core Lean 4.35.0, no Mathlib),
build record: [lean/BUILD-LOG.txt](lean/BUILD-LOG.txt).

## Grounding — what system this specifies

The S3c daily issuance cadence as it actually ran Nov 1–3, 2026:

- One issuance obligation per local day (the 07:00 America/New_York slot;
  intraday retries — the Nov 3 repair continuation, the 19:00Z window —
  are *attempts* at the day's slot, and a cadence-side three-miss guard
  throttles attempts; neither creates extra obligations).
- Each day resolves to exactly one artifact in `docs/s3c/*.json` (PC repo)
  plus one row in `docs/s3c/CADENCE-TRACKER.md`: a scored call, a no-call
  receipt with a reason, or a miss.
- Two counters are tracked separately (Darren's two-ledger ruling,
  Nov 1): the **issuance streak** (every day that produced a receipt) and
  the **scored cadence** (the 14 of the S7 gate; no-calls do not advance
  it; it stood at 0 after three receipted/missed days).

Sources: `~/workspace/grid-project/PLAN.md` v3 (plan of record);
`~/workspace/grid-project/S3C-RULINGS-2026-10-30.md` (the seven ruled
definition rules); the Nov 1–3, 2026 failure and repair record
(`ISSUANCE-REPAIR-2026-11-03.md` and the daily logs). **Scope note on
grounding:** the cadence code and receipts live in the PC repo
(`C:\Users\ajbig\Documents\grid-project`); they are not present on this
VM, so code-level claims below rest on the repair record's own sys.path /
file evidence and the pulled receipt fields, not on a fresh source read.
Where that distinction matters, the invariant's status says so.

**Explicit non-scope:** PLAN.md's S4 ledger machinery (content-addressed
receipts under `ledger/forecasts/`, hash-in-filename, exclusive-create,
`ledger verify`) is **not** formalized here, because the running cadence
does not use it yet — the Nov 1 issuance artifact is a `docs/s3c` JSON,
explicitly not a hash-chain ledger receipt (S4 checker record). Those
invariants become in-scope if/when the S4 ledger becomes the issuance
path.

## The model in one paragraph

The ledger is a list of day-records appended in slot order. A record has:
`day`, `outcome` (`scored` / `noCall reason` / `missed`), `artifactHash`
(hash of the issuance artifact that executed), `envId` (the environment
it ran in), `defHash` (stress-definition hash frozen at issue time),
`inputStamp` (latest input day used), `issuedAt` (true issue time),
`availVerified`. A single `Config` — canonical artifact hash, pinned
environment id, freshness bound, first slot day — is stated once for the
whole ledger. Steps only append records satisfying the step rules
(`StepOK`); no step edits an existing record, and no step changes the
Config. Lateness is *derived* (`issuedAt > scheduled(day)`), never
asserted. Full definitions in the Lean file header.

## Invariants

Status labels: **DESCRIBES** = the running system already behaves this
way per the record · **MIXED** = holds of the current (post-repair) state
but is not asserted at runtime · **REQUIREMENT** = the system should meet
it; today it does not, or enforces it only by convention. Runtime-check
summaries point to CONFORMANCE.md for the exact bridge.

### I1 — Freshness and no-lookahead for scored days

A day may be recorded **scored** only if the inputs it used were
(a) no older than the freshness bound relative to the target day — the
recorded "D-2 ceiling": latest input day ≥ target − 2; (b) strictly
before the target day (no lookahead); and (c) availability-verified —
the pipeline's own determination that the inputs were actually available
as of the slot cutoff, not merely that an index page carried a recent
timestamp.

- **Source:** Nov 1 issuance (inputs' latest date Oct 28 vs D-2 ceiling
  Oct 30 for target Nov 1 → `stale_load` no-call); Nov 2 issuance
  (latest completed Oct 31, `input_availability_verified: false` →
  `stale_load` no-call); PLAN.md freshness step ("stale inputs never
  skip silently: they write a no-call receipt with a reason"); S3c
  Ruling 6 (fitting pool for day D = days strictly before D, values as
  first recorded).
- **Runtime check (summary):** gate in the issuance path immediately
  before a scored receipt is written; failure writes a no-call receipt
  instead. See CONFORMANCE §I1.
- **Status:** DESCRIBES — the fail-closed behaviour is exactly what both
  days did. Caveat: *how* availability becomes verified is not
  established in the record (both days carry `false`; the Nov 1 record
  states input availability was explicitly unverified, index time ≠
  availability). The invariant constrains scoring, not the availability
  mechanism (assumption A5).
- **Lean:** `scored_fresh` (from `record_props`). The Nov configurations
  cannot be scored records in the model — see the refusal example.

### I2 — No stale copy

A receipt (scored or no-call) may be produced only by the **canonical
artifact**: the artifact that executes must hash-match the canonical
artifact hash stated in the Config. A run of anything else can end the
day only as `missed`, never as a receipt.

- **Source:** Nov 1, 2026 — the 07:00 slot executed a stale copy of the
  issuance script (`AppData\Local\hermes\scripts\issue_stress.py`,
  modified Oct 31 14:21) instead of the repo copy (Oct 31 17:39),
  outside the package context; it died at imports and wrote nothing.
- **Runtime check (summary):** launcher hashes the resolved artifact
  before executing and compares to a repo-pinned canonical hash; the
  receipt records the artifact hash. See CONFORMANCE §I2.
- **Status:** REQUIREMENT in hash form. Today's enforcement is *path
  discipline* (repo launcher `grid_s3c_repo_launcher.py`, repo workdir,
  stale job `f15a` disabled, no other job pointing at the stale copy) —
  nothing at runtime compares hashes, and receipts do not record which
  artifact ran. The model formalizes the hash form because path
  discipline is what failed on Nov 1 (a path was followed, faithfully,
  to the wrong file).
- **Lean:** `receipt_hash_env` (artifact-hash half).

### I3 — Receipt-gated scoring; two separate ledgers

The scored cadence is a **count over records**, not a number a run
reports: it advances by exactly one when a scored record is appended,
and does not move on a no-call or a missed record. The issuance streak
counts receipts (scored + no-call) and likewise does not move on a
missed record. Scored cadence ≤ issuance streak, always. A day counts
as scored only through the record found at the destination (the tracker
/ receipt store) — never on a producer's report.

- **Source:** Darren's two-ledger ruling, Nov 1, 2026 ("ISSUANCE STREAK
  — every on-schedule receipt counts (Nov 1 = day 1)"; "SCORED CADENCE —
  the 14 of the S7 gate; starts at the first scored issuance; no-calls
  do NOT advance it; no-call counts + reasons reported separately");
  observed state Nov 3: streak 2, scored cadence 0 after two no-call
  receipts and one missed day. Also Alder's Nov 1 verification failure
  (checking his own surfaces instead of the destination) — the reason
  "destination-verified" is in the invariant, not just "receipt
  exists somewhere."
- **Runtime check (summary):** both counters recomputed from the
  receipt store on every read; never incremented from run reports.
  See CONFORMANCE §I3.
- **Status:** DESCRIBES as the tracker's counting rule (it was applied
  exactly this way Nov 1–3). The mechanized destination-verification
  half (a `ledger verify`-style check) is S4/S5 work — REQUIREMENT
  there; for S3c today the destination check is the tracker discipline
  itself.
- **Lean:** `countWith_step`, `scored_advances_both`,
  `noCall_keeps_cadence`, `missed_keeps_both`,
  `scoredCadence_le_receiptStreak`, `lookupDay_spec`,
  `lookupDay_complete` (a day's record is what lookup at the
  destination finds). One recorded subtlety: the S7 gate says "14
  **consecutive**" — the model also defines the trailing scored run
  (`scoredRun`, `scoredRun_step`: a non-scored append resets it to 0).
  The tracker rule Darren stated is about the **count** ("do not
  advance"); whether a no-call also *resets* the S7 streak is not
  settled by the record, so the model proves both quantities and
  asserts neither reading over the other.

### I4 — Environment integrity: one environment, stated once

Every receipt is produced in the **one pinned environment**: the
interpreter that runs the cadence is the environment the dependencies
are pinned into. In the model this is structural: `Config.envId` is a
single parameter of the whole ledger, and every receipt must carry it.

- **Source:** Nov 3, 2026 root cause, proven in the repair record —
  pinned `duckdb==1.4.4` was installed in repo-root `.venv-cadence/`
  while every cadence script imports from `autopilot/.venv` (sys.path
  evidence in the record); the 07:00 run died on
  `OSError: libduckdb.so missing`. (The VM-wipe hypothesis was checked
  and refuted in the same record.)
- **Runtime check (summary):** launch-time probe from the cadence
  interpreter itself: pinned deps import and version-match the pin
  file — the exact probe the Nov 3 repair ran by hand. See
  CONFORMANCE §I4.
- **Status:** MIXED — the post-repair state satisfies it (pin copied
  into the interpreter's environment, import + query probe green), but
  nothing asserts it at launch; a future version skew that still
  imports (cf. the system dist-packages duckdb 1.1.3, unreachable only
  by sys.path luck) would not be caught by today's setup.
- **Lean:** `receipt_hash_env` (env-id half).

### I5 — Slot monotonicity: a missed slot is recorded missed, never backfilled

Days enter the ledger in slot order, exactly one record per day, and an
appended record never changes: any extension of the ledger has the
original as a prefix, day lookup returns the same record forever, and a
day recorded `missed` can never acquire a different record later — in
particular it can never become scored retroactively. A late issuance
for a day is stamped with its TRUE issue time (its lateness is
derivable from the record, per I8), and rulings about a day live in the
tracker as notes — the receipt itself is never edited post-hoc.

- **Source:** Nov 1, 2026 — Darren's ruling "mark it as day 1 with a
  special note" was recorded **in the tracker**; "the receipt JSON
  itself was NOT edited." The standing rule from the same day: stop
  rather than emit a false receipt; the late receipt carries its true
  timestamp (2026-11-01T11:15:49-05:00) and `issued_late: true`.
  PLAN.md: "predictions are committed as files before outcomes exist
  and never back-edited."
- **Runtime check (summary):** append-only tracker writes; one row per
  target date, existence-checked before writing; never overwrite. See
  CONFORMANCE §I5.
- **Status:** DESCRIBES the ruling discipline (it was followed Nov 1).
  The one-record-per-day completeness half is shared with I7 and was
  violated on Nov 1 morning (no record existed until forensics) — see
  I7's status.
- **Lean:** `day_bounds`, `day_surjective`, `pairwise_days`,
  `day_unique`, `extends_prefix`, `lookupDay_persistent`,
  `no_backfill`.

### I6 — Definition freeze

Each record carries the hash of the stress definition in force when it
was issued (`defHash`), and that field — like the whole record — can
never change afterwards. Amendments create new definition versions;
history is never rescored under a new definition. In the model this is
deliberately structural: the Config has **no** "current definition"
field, so there is nothing in the state that could retroactively
relabel a record; freeze reduces to whole-record persistence.

- **Source:** PLAN.md (receipts carry the definition's sha256 +
  thresholds **frozen at issue time**; "the versioned, frozen
  definitions S3 ruled"; amendments never rescore history — a receipt
  joins to the definition version in force at its issue time);
  S3C-RULINGS-2026-10-30 (the seven ruled rules are the definition's
  content).
- **Runtime check (summary):** receipt writer includes the definition
  hash; scoring joins on the receipt's own hash. See CONFORMANCE §I6.
- **Status:** DESCRIBES at plan level. For the live S3c receipts, the
  pulled record does not confirm a definition-hash field in the JSON
  itself (the definition-freeze facts above are plan/rulings-level);
  treat live-receipt conformance as unchecked until the PC receipts are
  read with this field in mind.
- **Lean:** `lookupDay_persistent` + `no_backfill` (whole-record
  persistence — the `defHash` a record was issued with is the one it
  keeps, because the record is the thing that persists).

### I7 — No silent slot

Every day-slot terminates in exactly one record at the destination —
scored, no-call, or missed. A crash is a `missed` record, not an absent
one; "the slot produced nothing anywhere" is not a legal end state.
(The companion duty — that a human is *alerted* on failure/no-call —
is a delivery property, not a ledger property; it is carried in
CONFORMANCE §I7 and deliberately not in the Lean model.)

- **Source:** Nov 1, 2026 — the 07:00 failure wrote no issuance file,
  and the incident record's delivery was **"suppressed"**: nobody was
  alerted; Alder's 08:39 check framed it as "no sign of a firing."
  Standing fixes from the same day: failures AND unscored no-calls
  route to Darren's Telegram DM (synthetic failure test verified
  delivered). PLAN.md: "a failed scheduled run is a failed check —
  freshness that complains, out loud."
- **Runtime check (summary):** every exit path of a run writes its
  tracker row; an absence check (slot passed, no row) is itself the
  alarm condition. See CONFORMANCE §I7.
- **Status:** REQUIREMENT. Nov 1 violated it on both halves (no record,
  suppressed alert); the fixes aim at it, and Nov 2–3 behaved better
  (receipt written Nov 2; Nov 3's failure was found and repaired same-
  morning, and the guard-throttled continuation was itself logged
  'skipped' with an attempt id). The model's half — a record exists
  for every slot in range — is `day_surjective`.
- **Lean:** `day_surjective`, `lookupDay_complete` (model half only).

### I8 — True timestamps; no backdating

A record's issue time is never earlier than its slot, and lateness is
computed from the record's own fields (`issuedAt > scheduled(day)`),
not asserted by the producer.

- **Source:** the Nov 1 late receipt stamped with its TRUE time
  (11:15:49-05:00) and `issued_late: true`; the repo launcher refuses
  pre-07:00 issuance (standing fix, Nov 1).
- **Runtime check (summary):** launcher refusal (exists) + receipt
  `issued_at` taken from the clock at write time; late recomputed by
  any reader. See CONFORMANCE §I8.
- **Status:** DESCRIBES.
- **Lean:** `never_early`; `IsLate` is a derived definition, and the
  Nov 1 example checks `IsLate nov1` by computation.

## Assumptions (the model's named hypotheses)

The Lean theorems are unconditional over `Reachable` ledgers; the
assumptions below are the model↔reality mapping — each is a place where
the formal statement is only as good as the correspondence.

- **A1 — Hash equality is abstract.** Hashes/ids are natural numbers in
  the model; equality means equality. Collision resistance of the real
  SHA-256 is assumed, not proved.
- **A2 — Time is abstract.** Days/minutes are naturals from a fixed
  epoch; `scheduled(d) = d·1440 + 420` encodes the 07:00 local slot.
  Scheduler timezone/DST behaviour is outside the model (the Nov 1
  record leaves a gateway cached-timezone reload unverified — a
  scheduler property, not a ledger property).
- **A3 — Slot = day.** Intraday structure (07:00 run, 19:00Z window,
  directed late runs, the three-miss guard) is attempts at the day's
  single slot; the day's record is written when the day resolves.
- **A4 — Single writer, atomic appends.** The step relation assumes
  the cadence invokes it once per slot and appends atomically.
  (PLAN.md's "the `ledger` module is the sole reader/writer" is the
  S4 form of the same discipline.)
- **A5 — Availability is an input to the model.** `availVerified`
  records the pipeline's availability determination; the model
  requires it for scoring but does not model how it is established.
- **A6 — Definition hashes are opaque.** The model proves records
  carrying a `defHash` never change — not that the definition content
  behind a hash is correct.
- **A7 — Parameters.** `freshBound = 2` and the 07:00 slot are the
  recorded values (D-2 ceiling; 07:00 America/New_York). Theorems are
  proved for a general `Config`; the values are instantiations.

## Checked example: Nov 1–3, 2026

The three days are encoded in the Lean file (`cfg0`, `nov1`–`nov3`,
epoch day 0 = 2026-10-25, so Nov 1 = day 7; input stamps Oct 28 = day 3,
Oct 31 = day 6; hashes/ids are abstract stand-ins). Proved by
computation in the build:

- the three records form a **reachable** ledger under the step rules;
- `receiptStreak = 2`, `scoredCadence = 0`, `scoredRun = 0` — the
  two-ledger ruling, as arithmetic;
- `IsLate nov1` holds (derived, not asserted);
- **refusal:** a scored record wearing Nov 2's numbers transposed to
  day 9 (stamp day 6, outside the D-2 bound) is **not** a legal step —
  even with the canonical hash, the pinned env, and availability marked
  verified. Freshness is arithmetic, not assertion.

## Axiom audit

`#print axioms` for every theorem, from the final clean build
(invocation and exit status in lean/BUILD-LOG.txt). **No `sorry`
anywhere; `sorryAx` appears in no theorem's axiom set.**

| Theorem | Axioms |
|---|---|
| lookupDay_append, lookupDay_persistent | **none** |
| record_props, receipt_hash_env, scored_fresh, never_early, day_unique, lookupDay_spec, lookup_of_mem_unique, extends_prefix, countWith_step, noCall_keeps_cadence, missed_keeps_both, scored_advances_both, scoredRun_step | propext |
| day_surjective, scoredCadence_le_receiptStreak | propext, Quot.sound |
| day_bounds, pairwise_days, lookupDay_complete, no_backfill | propext, Classical.choice, Quot.sound |

(`Classical.choice`/`Quot.sound` enter through `omega` in the order
arguments; the core ledger facts are choice-free.)

## Requirements-vs-model gaps (collected)

1. **I2 (hash-form no-stale-copy)** — REQUIREMENT. Model assumes a
   canonical-hash comparison; the running system enforces path
   discipline only, and receipts don't record the executing artifact.
2. **I4 launch assertion** — MIXED. Holds post-repair; nothing asserts
   it at launch.
3. **I7 (no silent slot)** — REQUIREMENT. The model's record-existence
   half is proved; the alerting half is process, carried in
   CONFORMANCE, and was the actual Nov 1 failure.
4. **I3 mechanized destination verification** — the counting rule
   DESCRIBES; a `ledger verify`-style mechanization is S4/S5 scope.
5. **I6 live-receipt field** — plan-level DESCRIBES; presence of a
   definition hash in the live S3c receipt JSON is unchecked against
   the PC files.
6. **I1 availability mechanism** — the gate DESCRIBES; how availability
   is established is unrecorded (A5).
