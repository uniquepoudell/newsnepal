# News Nepal Crypto

Help Nepalese get on the forefront of digital economy.

Hourly-updated headlines about digital currency, blockchain and finance, with a Nepal focus.
Built for **newsnepal.crypto** and any regular domain you add later.

- `config.json` holds the news sources, the keyword filter, and the money settings (ads, sponsor, affiliate links, donation addresses).
- `scripts/build.py` fetches the feeds, keeps only matching stories, and writes the static site to `public/`. Python standard library only.
- `.github/workflows/build.yml` rebuilds every hour and publishes to GitHub Pages, and can pin a snapshot to IPFS.
- `tests/test_build.py` checks the build offline with sample feeds.

Setup, hosting, the .crypto domain and income ideas are in **[GUIDE.md](GUIDE.md)**.

## Build on your own computer

```bash
python scripts/build.py          # writes ./public
SHOW_AD_PLACEHOLDERS=1 python scripts/build.py   # also shows where ads and sponsor spots go
python -m http.server -d public 8000             # open http://localhost:8000
python tests/test_build.py       # offline test
```

## Add or remove a source

Add an entry to `feeds` in `config.json`. Set `"filter": true` for general sources so only stories that match the
keywords are kept, or `false` for sources that are already all on topic. Set `"enabled": false` to pause one.
