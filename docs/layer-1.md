# Layer 1 architecture and evidence

Status: ingestion storage foundation; no live provider integration verified.

Use Python and DuckDB locally to keep infrastructure cost at $0. DuckDB supports
SQL analytics and dbt without a database service. One ingestion writer runs at a
time. Postgres becomes a candidate if concurrent service writes are needed.

Raw responses live under `data/raw/{source}/{sha256}.json`, byte for byte.
The DuckDB `raw.batches` table records source, dataset, content digest, path and
load time. `raw.records` indexes each response record as JSON with its batch and
row number. Replaying identical bytes in the same dataset is a no-op. Changed
responses are retained as separate revisions. JSON indexing is derived data;
the landed file is the original evidence. Never save authenticated request URLs,
headers, or API keys alongside response data.

Planned cleaned tables:

- `cleaned.pjm_bge_hourly_price`: UTC hour + verified BGE pricing-node ID;
  real-time LMP in USD/MWh. Negative prices are valid. Verify the BGE node against
  provider metadata before selecting it; BGE service territory is not every MD node.
- `cleaned.eia_pjm_hourly_generation`: UTC hour + respondent + fuel type;
  generation in MWh. Retain revisions and choose the latest fetched observation
  at this business key. Validate units and flag negative generation for review
  rather than silently dropping it.
- `serving.grid_hourly`: BGE prices plus PJM-wide generation mix. Label the
  geography of each measure. PJM fuel mix is a regional proxy, not measured BGE
  carbon intensity or marginal emissions. Renewable share excludes nuclear;
  any low-carbon share must be separately defined. Missing data stays missing.

Incremental API ingestion is the next milestone: bounded UTC time intervals,
provider-specific pagination, retries with backoff for throttling/server errors,
overlap to pick up revisions, and a durable watermark advanced only after all
pages commit. Raw page deduplication alone is not incremental business-key loading.
Do not describe this foundation as a completed incremental pipeline.

dbt will cast and deduplicate raw records into cleaned tables, then build serving
views with uniqueness, null, unit, range and freshness checks. DST conversion to
America/New_York belongs in presentation; primary keys remain UTC. Published load
forecasts alone cannot identify tomorrow's cleanest hours. The later product must
verify available forecast variables before presenting clean-window predictions.

Power BI Desktop can consume exported serving CSVs for local reporting. A public
Power BI service deployment is not assumed free. Live ingestion, dbt models,
dashboard verification and operational evidence are still required before the
Tier 2 résumé claim is earned.
