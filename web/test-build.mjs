import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  rmSync,
} from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { load } from "cheerio";
const root = dirname(fileURLToPath(import.meta.url));
const [source, receipts] = process.argv.slice(2);
if (!source || !receipts)
  throw Error("Pass a staged legacy brief and receipt directory");
const tmp = resolve(root, ".build/test");
rmSync(tmp, { recursive: true, force: true });
mkdirSync(tmp, { recursive: true });
function build(input, records, name) {
  const out = resolve(tmp, name);
  execFileSync(
    process.execPath,
    [resolve(root, "render.mjs"), input, records, out],
    { stdio: "pipe" },
  );
  return out;
}
const out = build(source, receipts, "normal");
const get = (dir, path) => load(readFileSync(resolve(dir, path), "utf8"));
const home = get(out, "index.html"),
  charge = get(out, "charge-now/index.html"),
  dash = get(out, "dashboard/index.html");
for (const page of [home, charge, dash]) {
  assert.ok(page(".astryx-heading").length);
  assert.equal(page("nav a").length, 3);
  assert.ok(page('meta[property="og:image"]').length);
  assert.equal(
    page('a[href="https://github.com/Darren-dev141/grid-project"]').length,
    1,
  );
  assert.ok(page("footer").text().includes("Data as of:"));
}
assert.ok(home("#map").length);
assert.ok(
  home("script")
    .toArray()
    .some((n) => home(n).html()?.includes("L.geoJSON")),
);
assert.ok(charge("body").text().includes("$499"));
assert.ok(charge("body").text().includes("$100"));
const original = JSON.parse(
  readFileSync(resolve(receipts, "S3C-FIRST-ISSUANCE-2026-11-09.json"), "utf8"),
);
assert.equal(
  dash("tbody tr").first().find("td").first().text(),
  original.target_date,
);
const copyDir = resolve(tmp, "receipts");
mkdirSync(copyDir);
const changed = structuredClone(original);
changed.forecast.no_call_reason = "stale_weather";
writeFileSync(
  resolve(copyDir, "S3C-FIRST-ISSUANCE-2026-11-09.json"),
  JSON.stringify(changed),
);
const changedPage = get(
  build(source, copyDir, "changed"),
  "dashboard/index.html",
);
assert.ok(changedPage("tbody").text().includes("No call — stale weather"));
assert.ok(
  !changedPage("body")
    .text()
    .includes("every record below no-called on stale load"),
);
const sourceHtml = load(readFileSync(source, "utf8"));
sourceHtml(".level").text("No call — stale_load");
sourceHtml(".stats,.bar-wrap").remove();
sourceHtml(".hero").append(
  '<p class="noclaim">No peak demand, peak hour, or stress level is claimed for this date.</p>',
);
const noCallPath = resolve(tmp, "no-call.html");
writeFileSync(noCallPath, sourceHtml.html());
const noCall = get(
  build(noCallPath, copyDir, "no-call"),
  "charge-now/index.html",
);
assert.ok(noCall("body").text().includes("No recommendation is available"));
assert.ok(
  !noCall("body").text().includes("Charge, run, and schedule as normal"),
);
const empty = resolve(tmp, "empty");
mkdirSync(empty);
const emptyPage = get(
  build(source, empty, "empty-out"),
  "dashboard/index.html",
);
assert.ok(emptyPage("body").text().includes("No issuance records available."));
console.log(
  "PASS: nav, metadata, map, offer, receipt input, changed outcome, no-call and empty receipts",
);
