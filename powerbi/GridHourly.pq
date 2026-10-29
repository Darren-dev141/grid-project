// Create a text parameter ExportRoot containing the absolute data/powerbi path.
// Name this query GridHourly. It reads exactly one published snapshot per refresh.
let
    Pointer = Json.Document(File.Contents(ExportRoot & "\current.json")),
    SnapshotRoot = ExportRoot & "\snapshots\" & Pointer[snapshot_id],
    Manifest = Json.Document(File.Contents(SnapshotRoot & "\manifest.json")),
    Source = Csv.Document(File.Contents(SnapshotRoot & "\grid_hourly.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    BlankToNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(BlankToNull, {
        {"hour_utc", type datetimezone}, {"hour_local", type datetimezone},
        {"local_date", type date}, {"local_hour", Int64.Type},
        {"utc_offset_minutes", Int64.Type}, {"pnode_id", Int64.Type},
        {"price_usd_per_mwh", type number}, {"reported_generation_mwh", type number},
        {"renewable_share", type number}, {"fuel_count", Int64.Type},
        {"mix_complete", type logical}, {"price_loaded_at", type datetimezone},
        {"generation_loaded_at", type datetimezone}
    }, "en-US"),
    WithKind = Table.AddColumn(Typed, "data_kind", each Manifest[data_kind], type text),
    WithSnapshot = Table.AddColumn(WithKind, "snapshot_id", each Manifest[snapshot_id], type text),
    WithPurpose = Table.AddColumn(WithSnapshot, "purpose", each Manifest[purpose], type text)
in
    WithPurpose
