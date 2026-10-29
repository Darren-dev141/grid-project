# Layer 1 architecture and evidence

Status: ingestion and dbt verified on synthetic responses and a two-day live EIA
PJM generation sample. PJM prices, serving output with both live sources, and
Power BI report verification remain incomplete.

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

Implemented cleaned and serving views (provisional provider contracts):

- `cleaned.pjm_bge_hourly_price`: UTC hour + verified BGE pricing-node ID;
  real-time LMP in USD/MWh. Negative prices are valid. Verify the BGE node against
  provider metadata before selecting it; BGE service territory is not every MD node.
- `cleaned.eia_pjm_hourly_generation`: UTC hour + respondent + fuel type;
  generation in MWh. Retain revisions and choose the latest successfully observed batch
  at this business key. Validate units and flag negative generation for review
  rather than silently dropping it.
- `serving.grid_hourly`: BGE prices plus PJM-wide generation mix. Label the
  geography of each measure. PJM fuel mix is a regional proxy, not measured BGE
  carbon intensity or marginal emissions. Renewable share excludes nuclear;
  any low-carbon share must be separately defined. Missing data stays missing.

Incremental API ingestion is implemented against mocked provider contracts:
bounded UTC intervals, provider-specific pagination, retry/backoff for throttling
and server errors, revision overlap and durable watermarks advanced only after
all pages validate and index. Live compatibility and operational verification are
still required. Do not describe this foundation as a completed live pipeline.

dbt casts and deduplicates raw records into cleaned tables, then builds serving
views with uniqueness, null, unit, finite-value and range checks. `grid-freshness`
checks the current publication: each source's last usable hour (price, complete fuel
mix) must end within `--max-lag-hours` (default 36, provisional) and not after now.
EIA-930 PJM fuel mix lagged about 22 hours in one live sample (October 29, 01:47
UTC: latest hour 03:00 UTC October 28), so it cannot drive a real-time "charge now"
answer alone. PJM price lag is not yet observed. DST conversion to
America/New_York belongs in presentation; primary keys remain UTC. Published load
forecasts alone cannot identify tomorrow's cleanest hours. The later product must
verify available forecast variables before presenting clean-window predictions.

Power BI Desktop can consume exported serving CSVs for local reporting. A public
Power BI service deployment is not assumed free. Live ingestion, live dbt validation,
dashboard verification and operational evidence are still required before the
Tier 2 résumé claim is earned.

## Transformation decisions and limitations

All hourly keys are UTC timestamps; the dbt connection fixes its timezone to UTC.
`bge_pnode_id` is required and must be a positive integer. No production node ID
has been guessed. The tests use node 999 only as a synthetic example.

The generation completeness rule requires one row for each configured fuel code
(COL, NG, NUC, OIL, OTH, SUN, WAT, WND), valid MWh units and finite nonnegative
values. Renewable share counts SUN, WAT and WND only. OTH is not assumed renewable;
nuclear is not renewable. Unknown/missing fuel categories, nulls and negative
generation prevent a share. Zero total generation also gives a null share.
This is a conservative contract, to be checked against real EIA responses; the
eight-code list is not proof that the provider supplied all expected data.

The serving view retains price-only and generation-only hours via a full join.
`reported_generation_mwh` is a sum of available records, not a completeness claim;
consumers must inspect `mix_complete`. The view does not recommend charging.

Revision precedence uses the latest successful fetch observation timestamp,
falling back to first load time for offline/legacy batches, then digest and row
number as deterministic tie breakers. A freshly fetched response can restore a
previous value even when its bytes were seen before. Offline replay does not
promote an older response. Fetch observation time is not an upstream revision
timestamp. Conflicting rows within one page select the last row; provider-specific
duplicate and publication-time rules remain a gate.

## Incremental ingestion behavior

`ops.checkpoints` stores initial start and completed exclusive end per dataset and
geography. One DuckDB connection remains open throughout each run to exclude other
process writers. Use one job per process as well. Checkpoint reads explicitly use
UTC; integration tests caught and fixed the local-time conversion hazard.

The fetcher converts exclusive hourly ends to the provider's assumed inclusive
last hour. It requests stable time/fuel ordering for EIA and time ordering for a
single PJM node. It checks positive consistent totals, row counts, page repetition,
hour alignment, interval membership and respondent/node membership. It rejects
redirects and never follows links supplied by a response. A 30-second HTTP timeout,
four-attempt limit, 10,000-page ceiling and maximum 31-day interval bound each run.
Long or date-form Retry-After headers stop the run for a later retry.

Validated HTTP 200 bytes are landed unchanged before page parsing, except a body
containing the supplied API key is refused entirely. HTTP error bodies and request
URLs/headers are not logged. Pages are indexed only after the full download has
passed validation. New fetched batches start with `committed=false`, so cleaned
models exclude them. A crash during indexing can leave staged batches indexed;
the checkpoint and visible observations remain unchanged. After indexing completes,
one transaction marks all fetched batches committed, records their observation
time, and advances the checkpoint. A retry reuses staged rows. This transaction
publishes one source stream, not a synchronized snapshot across PJM and EIA.
Run dbt and exports after ingestion and retain the last export on failure.

Schema upgrades occur on the next replay/load. Existing batches receive
`committed=true` and no observation timestamp, preserving earlier behavior and
first-load ordering. Fresh offline replay batches are committed immediately;
replaying an existing batch leaves its metadata unchanged. This supports manual
imports but cannot establish that their content is a current provider observation.

Offset pagination is not a source snapshot: equal-total upstream edits during a
scan can still shift page boundaries. Revision overlap reduces this risk but does
not prove completeness. Live data coverage, lateness, upstream revision semantics,
and source-update timestamps remain required before operational sign-off.
