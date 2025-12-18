# MCMC Amateur Radio Callsign Scraper

Scrapes Malaysian amateur radio callsigns from MCMC and provides a JavaScript API.

## Quick Start (Local)

```bash
docker compose build
docker compose run --rm scraper python scraper.py
```

## GitHub Actions (Automated Weekly)

Runs every Sunday at 2 AM UTC, uploads to GitHub Releases.

1. Push to GitHub
2. Enable Actions write permissions in Settings
3. Enable GitHub Pages from `docs/` folder

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

// Get total count
const count = await CallsignAPI.getCount();
```

## Files

| File | Description |
|------|-------------|
| `data/callsigns.json` | All callsign assignments |
| `docs/index.html` | Search UI (GitHub Pages) |
| `docs/api.js` | JavaScript API |

## Features

- Auto-resume if interrupted
- Anti-detection delays
- Duplicate detection
- Weekly GitHub Actions automation
- JavaScript API for web apps
