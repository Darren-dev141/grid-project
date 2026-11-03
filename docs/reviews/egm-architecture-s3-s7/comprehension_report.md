# Stage 6: Comprehension Test (egm-comprehension)

Target: `docs/architecture-s3-s7.md`, FeatureRange 1-151, DetailedRange 152-170.
No standard (by design). Reviewer status: completed. 0 Blockers, 8 Majors, 5 Nits.

## What this proposes

A single `grid` entry point. `grid daily` does the following:

- fetches PJM demand (EIA-930), the NWS forecast and BWI observed temperatures (NCEI);
- runs dbt and checks freshness;
- forecasts tomorrow's PJM-wide peak MW, peak hour and a four-step stress level, using a versioned TOML definition (a degree-hinge regression on BWI history, percentile cuts, analog days and an alert bump);
- writes an immutable, content-addressed JSON receipt under `ledger/`;
- scores settled days;
- renders a brief to `site/` and posts it to a pinned GitHub issue.

`grid weekly` builds a scorecard for each forecaster. `ledger verify` in CI and in a pre-commit hook, plus branch protection, enforces append-only receipts. dbt cleans the data, pure Python models, and A's single entry point is reused.

## How the existing system works, per this document

- A Python package (`cli`, `fetch`, `nws`, `ncei`) lands raw responses through a content-addressed `storage` module into DuckDB.
- dbt cleans them into `eia_*`, `nws_*` and `ncei_bwi_daily_temps`.
- `freshness` checks load, weather, price and renewables.
- A v1 price and publish path is being retired.
- S3a (NCEI) is already built.

The document does not say what v1 produced, who used it, or why the direction changed.

## Findings

Majors:

1. **The goal and the ledger's purpose are never stated** (lines 1-16, 39, 96, 138, 162). The text relies on "cherry-pick", "on the record" and "resume gate" without defining them. S3-S7 are only defined by the build table.
2. **The timestamp proof is vague** (89, 92, 138, 168). `issued_at` is self-reported. The doc never says how the push time is captured or compared. A PC push also creates a push event.
3. **Version numbering contradicts itself** (63, 74, 128, 139-143). "v0" is undefined, a "v1 amendment" clashes with v1 being the first file, and "v1" also names the retired product.
4. **The candidate comparison relies on absent material** (7-16, 113, 119, 122). "A's own critique" and "a seven-line shell script" are neither included nor linked.
5. **Stress day and the scoring targets are underspecified** (56-57, 69, 72, 83-85). The doc never says:
   - which level counts as a stress day;
   - what the percentiles are taken over;
   - what "peak-hour tolerance" means.
6. **The notification prerequisites are missing** (35-37, 169). A token and an existing pinned issue are needed. "No new secret anywhere" contradicts that.
7. **Undefined terms** (129, 141): BGE, "display-only trailing color".
8. **The command surface is inconsistent** (18-25, 101, 113). The doc says there are three commands, but `replay` also exists. `grid-temps` and the other console scripts have no stated fate.

Nits:

9. `Report`, `Violation` and `call` are undefined. `Features`, `DayHistory` and `Actual` have no field lists.
10. `history_digest`, `weather_issuance_id` and the "actuals digest" are unexplained.
11. It is unclear which NWS view `features.load` reads.
12. Terms are used before they are defined or never defined: settled days, `pjm-demand`, "Darren", "lawful feed", the night-start low convention.
13. Line 170 does not link the plan. Who runs `grid weekly` is not stated.

The reviewer's overall verdict: findings 1 and 2 matter most, because the rest of the doc's reasoning depends on them.
