#!/bin/bash
# Run scraper and upload to GitHub releases
set -e

echo "=== Running MCMC Scraper ==="
docker compose run --rm scraper python scraper.py

echo ""
echo "=== Uploading to GitHub Releases ==="
COUNT=$(python3 -c "import json; d=json.load(open('data/callsigns.json')); print(len(d['assignments']))")
DATE=$(date +%Y-%m-%d)

# Create dated release (historical)
gh release create "v$DATE" data/callsigns.json \
    --title "MCMC Callsigns - $DATE" \
    --notes "**Total records:** $COUNT" || true

# Update latest release
gh release delete latest --yes 2>/dev/null || true
gh release create latest data/callsigns.json \
    --title "Latest MCMC Callsigns" \
    --notes "**Total records:** $COUNT
**Updated:** $DATE"

echo ""
echo "=== Done! ==="
echo "Records: $COUNT"
echo "Release: https://github.com/bizkut/callsignscrapper/releases/tag/latest"
