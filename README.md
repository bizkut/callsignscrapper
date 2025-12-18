# MCMC Amateur Radio Callsign Scraper

Scrapes Malaysian amateur radio callsigns from MCMC and provides a JavaScript API.

## Quick Start

```bash
# Run scraper and upload to GitHub releases
./run.sh
```

Or manually:

```bash
docker compose build
docker compose run --rm scraper python scraper.py
```

## Setup

1. Clone repo and install Docker
2. Run `./run.sh` to scrape + upload
3. Enable GitHub Pages (Settings → Pages → `main`, `/docs`)

## JavaScript API

Include the API in your page:

```html
<script src="https://bizkut.github.io/callsignscrapper/api.js"></script>
```

Usage:

```javascript
// Search by callsign, name, or assignment number
const results = await CallsignAPI.search('9M2');

// Get by exact callsign
const holder = await CallsignAPI.getByCallsign('9M2ABC');

// Get by prefix
const all9M2 = await CallsignAPI.getByPrefix('9M2');

// Get all data
const all = await CallsignAPI.getAll();
```

## Files

| File | Description |
|------|-------------|
| `data/callsigns.json` | All callsign assignments |
| `docs/index.html` | Search UI (GitHub Pages) |
| `docs/api.js` | JavaScript API |
| `run.sh` | Scrape + upload to releases |

## Features

- Auto-resume if interrupted
- Anti-detection delays
- Incremental updates (only adds new records)
- JavaScript API for web apps
