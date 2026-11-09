import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Heading } from "@astryxdesign/core/Heading";
import { Card } from "@astryxdesign/core/Card";
import { Text } from "@astryxdesign/core/Text";
import * as stylex from "@stylexjs/stylex";
import { load } from "cheerio";
import { transformSync } from "@babel/core";
import plugin from "@stylexjs/babel-plugin";
import {
  readFileSync as read,
  writeFileSync as write,
  mkdirSync as mkdir,
  copyFileSync as copy,
  readdirSync,
} from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { rejectUnverifiedSiteOutput } from "./publication-guard.mjs";
const here = dirname(fileURLToPath(import.meta.url));
const [source, receiptDir, dest] = process.argv.slice(2);
if (!source || !receiptDir || !dest)
  throw Error(
    "Usage: node render.mjs LEGACY_BRIEF_HTML RECEIPTS_DIR OUTPUT_DIR",
  );
rejectUnverifiedSiteOutput(dest);
if (resolve(source) === resolve(dest, "index.html"))
  throw Error("Stage brief separately from output");
const compiled = transformSync(
  read(resolve(here, "styles.source.mjs"), "utf8"),
  {
    filename: resolve(here, "styles.source.mjs"),
    plugins: [[plugin, { dev: false, runtimeInjection: false }]],
  },
);
mkdir(resolve(here, ".build"), { recursive: true });
const stylesPath = resolve(here, ".build/styles.mjs");
write(stylesPath, compiled.code);
const { styles } = await import(
  pathToFileURL(stylesPath).href + "?v=" + Date.now()
);
const atomic = compiled.metadata.stylex
  .sort((a, b) => a[2] - b[2])
  .map((v) => v[1].ltr)
  .join("\n");
const e = React.createElement,
  S = (k) => stylex.props(styles[k]),
  norm = (v) => v.replace(/\s+/g, " ").trim(),
  esc = (v) =>
    v
      .replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;")
      .replaceAll("<", "&lt;");
const $ = load(read(source, "utf8")),
  text = (s) => norm($(s).first().text());
const heading = text("h1"),
  call = text(".level"),
  context = text(".hud .meta"),
  footer = text("footer"),
  target = (heading.match(/\d{4}-\d{2}-\d{2}/) || [])[0];
const stats = $(".stat-value")
    .toArray()
    .map((n) => norm($(n).text())),
  thresholds = text(".thresholds");
const sectionItems = (title) =>
  $("section.panel")
    .filter((_, n) => norm($(n).find("h2").first().text()).startsWith(title))
    .find("li")
    .toArray()
    .map((n) => norm($(n).text()));
const fresh = sectionItems("Freshness"),
  alerts = sectionItems("Alerts"),
  caption = text(".map-caption");
const mapScript = $("script")
  .toArray()
  .map((n) => $(n).html() || "")
  .find((v) => v.includes("var renderer = L.svg()"));
const noCall = call.startsWith("No call");
if (
  !target ||
  !call ||
  !context ||
  !footer ||
  !fresh.length ||
  !caption ||
  !mapScript ||
  (!noCall && (!stats.length || !thresholds))
)
  throw Error("Legacy brief missing required fields or map");
const peak = stats.find((v) => v.startsWith("Peak demand:")) || "",
  hour = stats.find((v) => v.startsWith("Peak hour ending:")) || "",
  hourNum = (hour.match(/ending:\s*(\d+)/) || [])[1],
  watch = (thresholds.match(/watch\s+([\d,.]+ MW)/) || [])[1],
  asof = (footer.match(/Data as of:\s*([\d-]+)/) || [])[1] || "unavailable";
if (!noCall && (!peak || !hourNum || !watch))
  throw Error("Missing peak, peak hour, or watch threshold");
const peakNumber = Number(
  peak.replace("Peak demand:", "").replace(" MW", "").replaceAll(",", ""),
);
const watchNumber = Number((watch || "").replace(" MW", "").replaceAll(",", ""));
if (!noCall && (!Number.isFinite(peakNumber) || !Number.isFinite(watchNumber)))
  throw Error("Peak or watch threshold is not numeric");
if (call === "Stress level: calm" && peakNumber >= watchNumber)
  throw Error("Calm peak is not below the watch threshold");
const files = readdirSync(receiptDir)
  .filter((v) => /^S3C-FIRST-ISSUANCE-\d{4}-\d{2}-\d{2}\.json$/.test(v))
  .sort()
  .reverse()
  .slice(0, 10);
const receipts = files.map((name) => {
  const r = JSON.parse(read(resolve(receiptDir, name), "utf8"));
  if (
    !r.target_date ||
    !r.issued_at ||
    !r.latest_completed_peak_date ||
    !r.forecast ||
    r.forecast.target_date !== r.target_date
  )
    throw Error("Invalid receipt " + name);
  const dt = new Date(r.issued_at);
  if (Number.isNaN(dt.valueOf())) throw Error("Invalid timestamp " + name);
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/New_York",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(dt)
      .filter((x) => x.type !== "literal")
      .map((x) => [x.type, x.value]),
  );
  const reason = r.forecast.no_call_reason;
  return [
    r.target_date,
    `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`,
    r.latest_completed_peak_date,
    reason
      ? "No call — " + reason.replaceAll("_", " ")
      : r.forecast.level
        ? "Stress level: " + r.forecast.level
        : "No outcome recorded",
  ];
});
const historic =
  "These issuance records are stored in docs/s3c, not the forecasts ledger. Their warehouse feed stopped after 2026-10-28, so every record below no-called on stale load. Times are shown to the minute: the November 2–9 records were written seconds after 07:00 ET, not at the cutoff. The brief above is a separate retrospective reconstruction from the full warehouse (1,409 history days, through 2026-11-08), not a prospective issuance.";
const same =
  target === "2026-11-09" &&
  asof === "2026-11-08" &&
  fresh.includes("History days loaded: 1409 (last: 2026-11-08)") &&
  receipts.length === 10 &&
  receipts[0][0] === "2026-11-09" &&
  receipts[9][0] === "2026-10-31" &&
  receipts.every((r) => r[3] === "No call — stale load");
const note = same
  ? historic
  : "These issuance records are stored in docs/s3c, not the forecasts ledger. The brief above is a separate retrospective reconstruction, not a prospective issuance. Times are shown to the minute.";
const audit =
  "Next year's capacity charge is set by your load during last summer's five coincident-peak (5CP) hours — already decided, already on the record. The founding-pilot audit reconstructs a site's demand in those five hours and prices the exposure before the bill does: one paid document per site, founding terms $499 with a $100 deposit.";
const links = [
  ["/", "Brief"],
  ["/charge-now", "Charge now"],
  ["/dashboard", "Dashboard"],
];
function Section({ title, children }) {
  return e("section", S("section"), e(Heading, { level: 2 }, title), children);
}
function List({ items }) {
  return e("ul", null, ...items.map((v, i) => e("li", { key: i }, v)));
}
function Table() {
  return e(
    Section,
    { title: "Recent issuance record" },
    e("p", null, note),
    receipts.length
      ? e(
          "div",
          {
            ...S("tablewrap"),
            role: "region",
            "aria-label": "Recent issuance record",
            tabIndex: 0,
          },
          e(
            "table",
            null,
            e(
              "thead",
              null,
              e(
                "tr",
                null,
                ...[
                  "Target date",
                  "Issued (ET)",
                  "Latest completed peak",
                  "Issuance outcome",
                ].map((v) => e("th", { key: v, scope: "col" }, v)),
              ),
            ),
            e(
              "tbody",
              null,
              ...receipts.map((r, i) =>
                e("tr", { key: i }, ...r.map((v, j) => e("td", { key: j }, v))),
              ),
            ),
          ),
        )
      : e("p", null, "No issuance records available."),
  );
}
function Page({ route }) {
  const label =
    route === "/"
      ? "Grid brief"
      : route === "/charge-now"
        ? "Charge now"
        : "Dashboard";
  const action = noCall
    ? "No recommendation is available because the brief has no call."
    : call === "Stress level: calm"
      ? `No peak-avoidance action is called for today. The day's peak demand — ${peak.replace("Peak demand:", "").trim()}, expected in the hour ending ${hourNum.padStart(2, "0")}:00 local — sits below the watch threshold (${watch}). Charge, run, and schedule as normal.`
      : "Refer to the current brief for the stress level and peak hour.";
  return e(
    "div",
    S("shell"),
    e(
      "header",
      S("header"),
      e("a", { href: "/", ...S("brand") }, "Beat the Grid"),
      e(
        "nav",
        { "aria-label": "Site navigation", ...S("nav") },
        ...links.map(([href, name]) =>
          e(
            "a",
            {
              href,
              key: href,
              ...S("navlink"),
              "aria-current": href === route ? "page" : undefined,
            },
            name,
          ),
        ),
      ),
    ),
    e(
      "main",
      null,
      e("p", S("context"), context),
      e(Heading, { level: 1 }, label + " — " + target),
      e("div", S("call"), e(Text, null, call)),
      noCall && e("p", null, text(".noclaim")),
      route !== "/dashboard" &&
        e("p", null, "The brief above is a separate retrospective reconstruction, not a prospective issuance."),
      route === "/" &&
        e(
          "section",
          { "aria-label": "Maryland service territory" },
          e("div", { id: "map", ...S("map") }),
          e("p", null, caption),
        ),
      !noCall &&
        e(
          Card,
          { variant: "muted" },
          e(
            "div",
            S("metrics"),
            ...stats.map((v, i) => e("div", { key: i }, v)),
          ),
          e("p", null, thresholds),
        ),
      alerts.length > 0 &&
        e(
          Section,
          { title: "Alerts (annotation only)" },
          e(List, { items: alerts }),
        ),
      route === "/charge-now" &&
        e(Section, { title: "Today's call" }, e("p", null, action)),
      route !== "/charge-now" &&
        e(Section, { title: "Freshness" }, e(List, { items: fresh })),
      route === "/dashboard" && e(Table),
      route === "/charge-now" &&
        e(Section, { title: "The paid audit" }, e("p", null, audit)),
      e(
        "footer",
        S("footer"),
        e("p", null, footer),
        e(
          "p",
          null,
          "Code, receipts ledger, and method: ",
          e(
            "a",
            { href: "https://github.com/Darren-dev141/grid-project" },
            "open on GitHub",
          ),
          ".",
        ),
      ),
    ),
  );
}
mkdir(dest, { recursive: true });
for (const [name, pkg] of [
  ["reset.css", "@astryxdesign/core/reset.css"],
  ["astryx.css", "@astryxdesign/core/astryx.css"],
  ["theme.css", "@astryxdesign/theme-neutral/theme.css"],
])
  copy(fileURLToPath(import.meta.resolve(pkg)), resolve(dest, name));
for (const name of ["robots.txt", "llms.txt", "sitemap.xml"])
  copy(resolve(here, "public", name), resolve(dest, name));
write(resolve(dest, "grid-stylex.css"), atomic + "\n");
write(
  resolve(dest, "grid.css"),
  "body{margin:0;background:#f6f8f7;color:#13251e;font-family:system-ui,sans-serif;line-height:1.55}a{color:#075d48}a[aria-current=page]{font-weight:700;text-decoration-thickness:3px}main p,main li{max-width:75ch}table{min-width:620px;width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{border-bottom:1px solid #c6d4cc;text-align:left;padding:12px}.leaflet-container{font-family:system-ui,sans-serif}\n",
);
for (const route of ["/", "/charge-now", "/dashboard"]) {
  const title = "Beat the Grid — " + target,
    description = noCall
      ? `${call}. Data as of ${asof}.`
      : `${call}. ${peak}, hour ending ${hourNum.padStart(2, "0")}:00 local. Data as of ${asof}.`;
  const og = `<meta name="description" content="${esc(description)}"><meta property="og:type" content="website"><meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(description)}"><meta property="og:url" content="https://beat-the-grid.vercel.app${route}"><meta property="og:image" content="https://beat-the-grid.vercel.app/og.png"><meta property="og:image:alt" content="Beat the Grid. PJM-wide call, Maryland weather."><link rel="icon" href="/favicon.ico">`;
  const mh =
      route === "/"
        ? '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">'
        : "",
    mt =
      route === "/"
        ? '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>' +
          mapScript +
          "</script>"
        : "";
  const canonical = `https://beat-the-grid.vercel.app${route}`;
  const structured = route === "/"
    ? { "@context": "https://schema.org", "@graph": [
        { "@type": "Organization", "@id": `${canonical}#organization`, name: "Beat the Grid", url: canonical },
        { "@type": "WebSite", "@id": `${canonical}#website`, name: "Beat the Grid", url: canonical },
      ] }
    : { "@context": "https://schema.org", "@type": "WebPage", name: route === "/dashboard" ? "Dashboard" : "Charge now", url: canonical };
  const seo = `<link rel="canonical" href="${canonical}"><script type="application/ld+json">${JSON.stringify(structured).replaceAll("<", "\\u003c")}</script>`;
  const html = `<!doctype html><html lang="en" data-astryx-theme="neutral"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title>${og}${seo}<link rel="stylesheet" href="/reset.css"><link rel="stylesheet" href="/astryx.css"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/grid-stylex.css"><link rel="stylesheet" href="/grid.css">${mh}</head><body>${renderToStaticMarkup(e(Page, { route }))}${mt}</body></html>`;
  const path =
    route === "/"
      ? resolve(dest, "index.html")
      : resolve(dest, route.slice(1), "index.html");
  mkdir(dirname(path), { recursive: true });
  write(path, html);
  console.log(
    "built",
    route,
    "target",
    target,
    "receipt rows",
    receipts.length,
  );
}
