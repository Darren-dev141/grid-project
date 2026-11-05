"""Read-only snapshot of the NCEI archive state."""
import sys, json, duckdb
root = sys.argv[1]
with duckdb.connect(root + '/grid.duckdb', read_only=True) as c:
    b = c.execute("select count(*), sum(committed::int), max(loaded_at), max(observed_at) from raw.batches where source='ncei'").fetchone()
    r = c.execute("""select count(*), count(distinct payload->>'DATE'), min(try_cast(payload->>'DATE' as date)), max(try_cast(payload->>'DATE' as date))
                     from raw.records r join raw.batches b using (source,dataset,digest)
                     where r.source='ncei' and b.committed""").fetchone()
print(json.dumps({'ncei_batches': b[0], 'committed': b[1], 'latest_loaded_at': str(b[2]), 'latest_observed_at': str(b[3]),
                  'records_in_committed_batches': r[0], 'distinct_dates': r[1], 'first_date': str(r[2]), 'latest_date': str(r[3])}, indent=1))
