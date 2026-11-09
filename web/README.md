# Beat the Grid Astryx UI

The public pages are static React 19 server renders using Astryx components and the neutral theme. `styles.source.mjs` is compiled with the StyleX Babel plugin; its generated atomic stylesheet and Astryx's distributed CSS are served from `site/`. Vercel continues to serve committed `site/` with no build command. Do not commit `node_modules/` or `.build/`.

## Regenerate a brief

Run from the repository root, with the existing built DuckDB warehouse supplied as `WAREHOUSE` below. This renders the existing Python brief into a staging directory and does not write into `site/` until the Astryx build. Do not render the Python brief directly into `site/`: it would overwrite the Astryx home page.

    .venv/Scripts/python.exe -m grid_pipeline.brief --database "$WAREHOUSE" --ledger ledger --out web/.build/brief
    cd web
    npm ci --ignore-scripts
    node test-build.mjs .build/brief/index.html ../docs/s3c
    node render.mjs .build/brief/index.html ../docs/s3c ../site
    cd ..

The build consumes the staged Python-rendered brief for the call, peak, thresholds, weather, freshness, dates, map geometry and map script. It consumes the ten most recent `docs/s3c/S3C-FIRST-ISSUANCE-*.json` files directly for the dashboard issuance table, converting issue times to America/New_York. Missing or malformed essential brief fields and malformed receipts fail the build. With no receipt files, the dashboard explicitly says no issuance records are available. A no-call brief does not recommend scheduling as normal. For non-calm calls the page directs readers to the brief; it does not yet generate a specific action recommendation.

The November 9 provenance note is preserved verbatim only when that brief and those no-call receipts match its conditions; otherwise a neutral provenance note is used. The five-5CP and founding-audit wording is the existing charge-page copy. The GitHub line is the only CTA. The retained social image and favicon are `site/og.png` and `site/favicon.ico`.

Review all three output pages, the source facts, receipt outcomes, map, OG metadata and changes with `git diff` before publishing. Commit the intended source and built `site/` changes, push under the authorized workflow, then compare all live routes and assets with the committed blobs. This is a documented manual regeneration step, not an automated scheduler. `brief.py` and its calculations are not changed by this UI build.
