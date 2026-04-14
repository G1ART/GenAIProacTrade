# Phase 47d — Shell map (before → after)

## Top navigation

| Before (47b/47c) | After (47d) |
|------------------|-------------|
| Brief | **Home** (feed: Today, Watchlist, Research activity, Alerts preview, Journal preview, Ask AI brief, **Replay preview**, portfolio stub) |
| This object | **Research** (same cohort tabs: Brief → Advanced) |
| Alerts | *(preview on Home; full manager)* → **Advanced** |
| History | **Journal** (decision cards + form; no raw JSON as default) |
| Replay | **Replay** (unchanged sub-modes) |
| Ask AI | **Ask AI** (brief strip + contract shortcuts + input) |
| — | **Watchlist** (expanded watchlist + what changed) |
| — | **Advanced** (alerts filters, ack/resolve/supersede/dismiss, machine-heavy) |

## Landing / hero

| Before | After |
|--------|--------|
| Single “Brief” panel dominated by one bundle object (often reads like a closed fixture pitch) | **Home** grid: attention first (alerts if any, else de-emphasized fixture copy), then tracking, threads, alerts preview, journal preview, copilot brief, **Replay preview** (signature teaser → full Replay) |
| Raw-ish decision log as monospace JSON | **Journal** cards with timestamp, asset, type, note excerpt |

## Closed research fixtures

| Before | After |
|--------|--------|
| First screen feels like the fixture is the product | **Today** explains archive context and points to Watchlist / Research / Alerts; detail remains under **Research** |

## API additions

- **`GET /api/home/feed`** — server-composed blocks for the Home shell and for tests.
