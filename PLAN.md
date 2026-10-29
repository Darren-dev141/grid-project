# Grid Project — Plan of Record (v2)

**v1 committed by Darren, Oct 27, 2026** ("commit it") — a BGE charging-window advisor.
**v2 committed by Darren, Oct 28, 2026** ("Approve the shift plan with these changes") — the charging design is superseded by the grid-stress brief below, incorporating the Oct 28 review corrections in full (failure row F-20261028-03).

## What this is

A Maryland grid-stress early-warning and daily conditions brief, built on public data, that **keeps receipts on every forecaster — including PJM and itself**. Core question: *is tomorrow a high-stress day for the grid, and when the day lands, who called it right?*

- **Public good is the framing.** Peak days are when the dirtiest peaker plants run and when outages hurt the most vulnerable people hardest. Nothing in this project has anything to do with EV charging; the money framing is gone (price survives only as a secondary line where it happens to be relevant).
- **Audience of one**: Darren's household. A public page is a byproduct. No accounts, no actuation, no user-hunting.

## Purpose horizons

- **Tier 1 (now):** Energy Data Analyst / BI evidence — grid-conditions analysis on public PJM + EIA + NWS data.
- **Tier 2:** Junior Data Engineer / ETL evidence — the pipeline itself: multiple public APIs, incremental/idempotent loads, dbt models + tests, a forecast-scoring warehouse, freshness checks that complain instead of lying.
- **Tier 3 (later, honestly):** no longer gated on "real users" (v1's weakest clause). A running public-good system with a public, checkable track record.

## Data & keys — the whole list

- **EIA API — one free personal key (REQUIRED).** The PC build ran on the rate-limited demo key; deep history pulls for the seasonal index need the personal key. Email signup; Alder's agent email can carry it (directed as part of the Oct 28 approval).
- **NWS (api.weather.gov) — no key, no registration.** Identifying User-Agent header only.
- **PJM direct — NO ROUTE. Do not re-attempt.** Registration is company-only (Darren's ruling), and current `gridstatus` code requires `PJM_API_KEY` — it does not fetch any public web-app key (verified in source, Oct 28; correction in `pjm-route-research-2026-10-28.md`). Building our own grab of PJM's web-app key is a terms-of-use gray area and is not done without reading PJM's terms. Separately, `*.pjm.com` DNS times out from Darren's PC through ProtonVPN — moot unless a lawful direct route ever exists.
- **PJM's official forecast as a scored forecaster — only via a lawful route.** Candidate: the gridstatus.io **hosted** API free tier (their key; derived scoring aggregates with attribution, per its terms). That needs a free gridstatus.io account — an open sub-decision for Darren. If declined, the ledger launches scoring ours-vs-actual and PJM joins when a route exists. The build does not block on this.
- **Hosting:** GitHub Pages on the existing repo (`github.com/Darren-dev141/grid-project`). No key.

## Build order

- **S0 — preconditions.** (a) Git Credential Manager repair + commit the working tree + push `feat/energy-ingestion` — **executing** under Darren's Oct 28 "do 1" via PC Hermes. (b) Fix ProtonVPN DNS for `*.pjm.com` on the PC (only gates a hypothetical future direct route; logged here so it isn't rediscovered).
- **S1 — Forecast data foundation.** EIA-930 ingestion as built (PJM respondent demand + fuel mix), re-pointed: deep history pull on the personal key for seasonal distributions; PJM actual load for prompt scoring. Known lags, designed-in: PJM actuals ~1h old; **BGE local demand ~47h old** — BGE is trailing color, labeled as such, never blended silently with RTO-level scoring.
- **S2 — NWS ingestion.** Forecast for the Reisterstown-area gridpoint (daily highs/lows, heat and cold advisories). Second independent public source.
- **S3 — Stress index + our forecaster (dbt).** Our forecast is built from **NWS weather + EIA history**: forecasted peak vs. the seasonal demand distribution, fused with temperature → a level (calm / watch / strained / severe) + expected peak hour. Season-aware — cold snaps peak PJM too. The index definition is **versioned and published**; changes are amendments, never silent retunes (retuning after seeing outcomes would void the receipts).
- **S4 — Forecast ledger (the spin).** Every forecast is written to **a file that is never modified and committed to the public repo — git history is the timestamp proof** (DuckDB alone cannot enforce append-only). Ledger tables are derived views over those files. A scoring job joins actuals as they land. Forecasters: **ours** (S3) from day one; **PJM official** only via the lawful route above.
- **S5 — Daily brief.** Fixed template: tomorrow's call + top drivers; one household-action line; yesterday's receipts (how the most recent scored calls did). Output: a message to Darren + a static public page. Freshness checks retargeted to load, forecast, and weather (they previously checked price/renewables — price is retired).
- **S6 — Weekly scorecard.** Ours (and PJM, when present) vs. actual: peak-hour hit rate, peak-MW error (MAE), stress-day precision/recall. Published with the brief archive.
- **S7 — Docs + résumé gate.** Layer design docs rewritten for the new design; README updated. The résumé line earns only after the system has actually run: **14 consecutive daily briefs + 2 weekly scorecards**, all receipts in the ledger.

## Retired with v1 (do not resurrect)

Charging-window logic · LMP price ingestion (route research stands corrected in `pjm-route-research-2026-10-28.md`) · the "charge now or wait" page · the money-savings scorecard · smart-home/Tesla actuation talk · the Kanban Layer 2 charging cards (closed as superseded).

## Rules (unchanged unless noted)

- $0 spend: free keys, local/free hosting only.
- Each layer earns its résumé line only when built and verified — no claiming ahead.
- Design doc per layer, written as interview material, filed in this folder.
- Stack: Python + dbt + DuckDB (pipeline); the brief is static output, no app framework needed.
- **New:** predictions are committed as files before outcomes exist and never back-edited; the stress index is a published, versioned definition.
- Parallel weekly tracks from v1 stand: open-source PRs into tools the build uses; algorithm practice (NeetCode 150 structure).

## Status

- Oct 27, 2026: v1 committed. Oct 28: Layer 1 EIA build largely completed in T3 on the PC (43 tests passing at last report); PJM API ruled company-only; route research corrected (F-20261028-03); pivot drafted, reviewed and corrected, and **approved with changes by Darren ~23:01 ET**. S0(a) executing. $0 spent.
