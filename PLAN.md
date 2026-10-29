# Grid Project — Plan of Record

**Committed by Darren, Oct 27, 2026** ("commit it"), adopting the merged Alder + Claude plan.
Origin: data-analytics project #1 (energy market dashboard), upgraded Oct 27 first to close the Tier 2 gap (pipeline form), then per Claude's take (relayed by Darren) to a product arc aimed at Tier 3 (Software Engineer I).

## Purpose

One build that serves three horizons:
- **Now (Tier 1):** Energy Data Analyst / BI evidence — a real energy dashboard on public PJM + EIA data.
- **Tier 2:** Junior Data Engineer / ETL / Python Developer (automation) — the pipeline itself: API ingestion, incremental loads, dbt models + tests, local warehouse.
- **Tier 3 (later, honestly):** Software Engineer I — only once the web app has real users. The résumé headline may lead with Software Engineering only then (Claude's rule, adopted).

Working description (no brand name chosen): a Mid-Atlantic / BGE-territory tool that tells people when the grid is cleanest to charge an EV or run a heavy appliance, and alerts them when that window arrives. Differentiator vs WattTime / Electricity Maps: local and specific. Darren personally owns the use case (Model Y, garage charging).

## Build order (Claude's order, adopted)

1. **Layer 1 — the pipeline.** Python ingestion from PJM Data Miner + EIA APIs (free keys), incremental/idempotent loads, raw landed untouched; dbt SQL models + tests (null/range/duplicate checks) over DuckDB or Postgres ($0, local); Power BI dashboard on top (MD price trends, peak hours, renewable share). → Earns the Tier 2 résumé line when built + verified.
2. **Thin web app MVP.** One public page answering "charge now or wait" for the BGE zone, served from the pipeline data (FastAPI backend; React + TypeScript frontend — TypeScript is the named skills gap this closes). NO accounts/auth until a second user needs something that requires it. PJM's own published forecast supplies "tomorrow's windows" before any ML of ours.
3. **Alerts + forecasting.** Email alerts when a clean window is coming; forecasting later, honestly labeled, baseline-first.
4. **Parallel weekly tracks (throughout):** open-source PRs into tools the build uses (dbt, FastAPI, a Python library — docs/small bugs first), and algorithm practice (NeetCode 150 structure) — projects get the SWE interview, algorithms pass it.

## Rules

- $0 spend: free API keys, local/free hosting only. No new paid services (standing cash rule).
- Each layer earns its résumé line only when built and verified — no claiming ahead (claim-evidence discipline).
- Design doc per layer: short architecture note with the tradeoffs, written as interview material (Claude's point), filed in this folder.
- Stack: Python + dbt + DuckDB/Postgres (Layer 1); FastAPI + React/TypeScript (Layer 2).
- First concrete steps for Layer 1: register for PJM Data Miner API key + EIA API key (free, email signups — Alder's agent email can carry them), scope the table layout (raw → cleaned → serving), then build ingestion.

## Status

- Oct 27, 2026: plan committed. Nothing built yet, $0 spent, no keys registered yet.
# Grid Project — Plan of Record

**Committed by Darren, Oct 27, 2026** ("commit it"), adopting the merged Alder + Claude plan.
Origin: data-analytics project #1 (energy market dashboard), upgraded Oct 27 first to close the Tier 2 gap (pipeline form), then per Claude's take (relayed by Darren) to a product arc aimed at Tier 3 (Software Engineer I).

## Purpose

One build that serves three horizons:
- **Now (Tier 1):** Energy Data Analyst / BI evidence — a real energy dashboard on public PJM + EIA data.
- **Tier 2:** Junior Data Engineer / ETL / Python Developer (automation) — the pipeline itself: API ingestion, incremental loads, dbt models + tests, local warehouse.
- **Tier 3 (later, honestly):** Software Engineer I — only once the web app has real users. The résumé headline may lead with Software Engineering only then (Claude's rule, adopted).

Working description (no brand name chosen): a Mid-Atlantic / BGE-territory tool that tells people when the grid is cleanest to charge an EV or run a heavy appliance, and alerts them when that window arrives. Differentiator vs WattTime / Electricity Maps: local and specific. Darren personally owns the use case (Model Y, garage charging).

## Build order (Claude's order, adopted)

1. **Layer 1 — the pipeline.** Python ingestion from PJM Data Miner + EIA APIs (free keys), incremental/idempotent loads, raw landed untouched; dbt SQL models + tests (null/range/duplicate checks) over DuckDB or Postgres ($0, local); Power BI dashboard on top (MD price trends, peak hours, renewable share). → Earns the Tier 2 résumé line when built + verified.
2. **Thin web app MVP.** One public page answering "charge now or wait" for the BGE zone, served from the pipeline data (FastAPI backend; React + TypeScript frontend — TypeScript is the named skills gap this closes). NO accounts/auth until a second user needs something that requires it. PJM's own published forecast supplies "tomorrow's windows" before any ML of ours.
3. **Alerts + forecasting.** Email alerts when a clean window is coming; forecasting later, honestly labeled, baseline-first.
4. **Parallel weekly tracks (throughout):** open-source PRs into tools the build uses (dbt, FastAPI, a Python library — docs/small bugs first), and algorithm practice (NeetCode 150 structure) — projects get the SWE interview, algorithms pass it.

## Rules

- $0 spend: free API keys, local/free hosting only. No new paid services (standing cash rule).
- Each layer earns its résumé line only when built and verified — no claiming ahead (claim-evidence discipline).
- Design doc per layer: short architecture note with the tradeoffs, written as interview material (Claude's point), filed in this folder.
- Stack: Python + dbt + DuckDB/Postgres (Layer 1); FastAPI + React/TypeScript (Layer 2).
- First concrete steps for Layer 1: register for PJM Data Miner API key + EIA API key (free, email signups — Alder's agent email can carry them), scope the table layout (raw → cleaned → serving), then build ingestion.

## Status

- Oct 27, 2026: plan committed. Nothing built yet, $0 spent, no keys registered yet.
