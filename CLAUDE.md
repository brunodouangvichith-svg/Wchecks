# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

There is no test suite, linter, or build step configured in this project — verification is
done by running the module in question directly against its real source (see below).

```bash
# Setup
python -m venv .venv
.venv/Scripts/activate            # source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
cp .env.example .env              # then fill in DATABASE_URL, EIA_API_KEY, AISSTREAM_API_KEY

# Apply/update the DB schema (source of truth: db/schema.sql) against Neon
python -c "import config, psycopg; psycopg.connect(config.DATABASE_URL).cursor().execute(open('db/schema.sql').read())"

# Run a single collector in isolation (each is a standalone script with __main__)
python -m collectors.collect_debt
python -m collectors.collect_spr

# Consult collected data / trigger the on-demand-only collector
python cli.py --latest brent_prices
python cli.py --history 10 energy_conflicts
python cli.py --minerals-refresh

# Run the background scheduler (all jobs fire once immediately, then on their interval)
python scheduler.py

# Regenerate the interactive map
python -m viz.build_map
```

## Architecture

Three-layer pipeline, one direction only: `clients/` → `collectors/` → `neon_client` (Postgres).

- **`clients/*_client.py`**: raw access to one external source (HTTP/WebSocket/file parsing).
  No business logic, no persistence. Each is independently testable/runnable
  (`python -m clients.eia_client` style probing was used throughout development).
- **`collectors/collect_*.py`**: one per data dimension. Calls a client, reshapes rows into the
  exact column set of one `db/schema.sql` table, calls `neon_client.upsert_generic(table, rows)`.
  Every collector exposes a bare `run() -> int` plus a `__main__` block — this is what both
  `scheduler.py` and `cli.py --minerals-refresh` call into.
- **`clients/neon_client.py`**: the only module that talks to Postgres. `TABLE_COLUMNS`,
  `TABLE_CONFLICT_KEYS` and `ORDER_FIELD` are per-table declarations that `upsert_generic()` /
  `get_latest()` / `get_history()` use to build `INSERT ... ON CONFLICT (...) DO UPDATE` and
  `ORDER BY <natural date/period column> DESC` queries generically. Adding a table means adding
  entries to all three dicts *and* to `db/schema.sql`.

### Storage backend history (matters if you see stray references)

The project went **Supabase → Firebase/Firestore → Neon** over the course of development, each
swap driven by a concrete constraint hit while running real backfills, not a plan revision:
Firestore's Spark plan hard-caps at ~20k writes/day, which a full historical backfill across 16
tables exceeds in a single run; Neon (Postgres) has no such per-operation quota. If you find a
docstring or comment mentioning Firestore/Supabase, it's a leftover — `neon_client.py` is current.

### `mapping/country_mapping.py` is built incrementally, on purpose

`COUNTRY_NAME_TO_ISO3` / `COUNTRY_CENTROIDS` are not meant to be "complete" — they're extended
every time a new source's country-naming quirks show up in the logs (GDELT dateline names, SIPRI
supplier/recipient names, USGS "Country or locality" column, the world-borders GeoJSON's `name`
property all spell some countries differently: "Turkiye" vs "Turkey", "Congo (Kinshasa)" vs
"Democratic Republic of Congo", etc.). `resolve_country()` and the raw `COUNTRY_NAME_TO_ISO3.get()`
calls log-and-skip on a miss rather than raising — check `grep -i "non reconnu"` in a collector's
output before assuming a country is unmappable; it may just need a new alias added to `_ALIASES`.

### Tolerant parsing is the norm for the static-file sources, not an afterthought

`sipri_client.py` and `usgs_client.py` both parse real-world files whose structure doesn't match
what the schema originally assumed:
- SIPRI's freely-downloadable CSVs are aggregated per supplier/recipient *country* per *year*
  (TIV totals across all partners/weapon types) — there is no bilateral or per-weapon-type detail
  in the free export, so `arms_transfers` is keyed on `(pays_code, annee, direction)`, not the
  bilateral schema you might expect from the table name.
- USGS "Minerals Yearbook" Excel sheets stack multiple tables in one sheet (a "—Continued"
  section further down reuses the same columns for different commodities under a new header).
  `usgs_client.py` deliberately stops at the first section-end marker (`_is_section_end_marker`)
  rather than trying to re-detect subsequent headers — some commodities (lithium, uranium) live
  in a later section and are silently not collected from the files currently in `data/usgs/`.

Both clients log unmatched/unparseable rows and keep going. When extending either, preserve that
behavior — do not tighten either parser into raising on unexpected input.

### `scheduler.py` gotchas that have already bitten once

- `next_run_time` for "fire immediately on startup" must be `datetime.now(timezone.utc)`, not
  naive `datetime.now()` — the scheduler is constructed with `timezone="UTC"`, and a naive
  local-time value gets interpreted as if it already were UTC, silently delaying the first run by
  the local/UTC offset.
- The executor thread pool is sized explicitly (`max(20, len(JOBS) * 2)`) and `misfire_grace_time`
  is set generously (3600s) in `job_defaults`. APScheduler's default 10-worker pool plus a 1s
  misfire grace time will silently *drop* (not delay) any job beyond the 10th that all fire at
  the same `next_run_time` — this happened to `official_statements` in the 11-job configuration.
  If you add jobs, keep the pool sized above `len(JOBS)`.
- `rss_client.py` fetches feeds via `requests` (explicit timeout) and hands raw bytes to
  `feedparser.parse()` — never call `feedparser.parse(url)` directly with a URL, it performs its
  own network fetch with no timeout and can hang a scheduler thread indefinitely on a slow feed.

### GDELT rate-limiting is expected and handled, not a bug to fix

`gdelt_client.py` retries 429s with backoff and gives up after 3 attempts, returning an empty
list rather than raising. Shared-IP sandboxes hit this frequently; it clears up from a normal
residential/cloud IP (Render's included). Do not "fix" this by removing the retry/backoff or by
treating an empty result as an error condition upstream.

### Score of risk and the map are both intentionally simple aggregations

`scoring/risk_score.py` takes the latest known value per country for a handful of World Bank
indicators plus a raw GDELT event *count* per country, min-max normalizes each dimension
independently, and averages whatever dimensions a country has data for (equal weights, no
calibration). This means countries with heavy English-language press coverage score higher on
the GDELT-derived dimensions regardless of actual risk — a media-coverage bias, not a modeling
bug, and it's meant to stay legible/inspectable via `details_json` rather than get more "accurate"
by adding opacity. `viz/build_map.py` follows the same spirit: one `folium.Choropleth` layer per
metric, toggled via `LayerControl`, reading directly from Neon at render time (no cached/derived
intermediate state to keep in sync).
