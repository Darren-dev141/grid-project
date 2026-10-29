# Local Power BI report

Status: import query and measures supplied; no PBIX report built or visually
verified yet. No Power BI Service account or paid publishing license is required
for the intended local Desktop workflow.

1. After ingestion succeeds, run `grid-publish` from the project root (see main
   README). It rebuilds and tests dbt against an isolated copy of the warehouse.
2. In Power BI Desktop create a Text parameter named `ExportRoot` with the absolute
   path to `data/powerbi`. Create a blank query named `GridHourly`, open Advanced
   Editor, and paste `GridHourly.pq`.
3. Add the measures in `measures.dax` one at a time. Set renewable share and share
   coverage to percentage formats. Use USD/MWh for prices.
4. Add a date slicer on `local_date`, a price trend using `hour_utc`, and an hourly
   profile using `local_hour` and Average BGE LMP. Label the profile "Mean observed
   wholesale LMP by local hour". It is not an electricity tariff or EV cost.
5. Add a regional renewable-share trend, price/share observation-count cards,
   share-coverage card and Data label card. Keep blanks as blanks; never substitute
   zero for missing share or generation.
6. Include this visible note: "BGE-node wholesale price; PJM-wide generation mix.
   Historical observations, not measured BGE emissions or a charging forecast."

`hour_utc` is the unique observation key. `hour_local` includes its UTC offset,
while `local_date` and `local_hour` support local grouping. At the fall DST change,
two observations share local hour 1; both count in hourly averages. Do not use
local wall time alone as a key. Inspect offset in a table when validating DST.

Each publication has a unique immutable directory, manifest, CSV checksum and dbt
validation artifacts. `current.json` switches only after success. A failed build
leaves the previous pointer intact. The import query reads one pointer and follows
it for both CSV and labels; it never globs snapshots or mixes old and new files.
Failed/unpublished snapshot directories remain for diagnosis.

Average PJM renewable share is the unweighted mean of valid hourly shares, not
the renewable fraction of total energy over a selected period. Coverage is the
fraction of observed union hours with a valid share; it is not a guarantee of all
expected calendar hours. A missing day can be absent entirely. Calendar coverage
and live freshness gates are still required before operational use.

Acceptance still pending: import in Desktop without errors, validate the measures
against SQL, inspect each visual and DST behavior, save a PBIX, and repeat with
verified live public data. Synthetic exports must keep their label visible.
