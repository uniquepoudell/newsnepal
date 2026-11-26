"""Offline test: builds the site from local fixture feeds. Run: python tests/test_build.py"""
import json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import build  # noqa: E402

cfg = json.loads((HERE.parent / "config.json").read_text())
fx = HERE / "fixtures"
cfg["feeds"] = [
    {"name": "CryptoFeed", "url": (fx / "crypto.xml").as_uri(), "category": "crypto", "filter": False},
    {"name": "ShareSansar", "url": (fx / "google.xml").as_uri(), "category": "nepal", "filter": True, "_google": True},
    {"name": "AtomFeed", "url": (fx / "atom.xml").as_uri(), "category": "global", "filter": True},
    {"name": "Broken", "url": (fx / "missing.xml").as_uri(), "category": "crypto", "filter": False},
]
cfg["monetization"]["donations"]["addresses"][0]["address"] = "0x1234567890abcdef1234567890abcdef12345678"

# Google-style parsing is keyed on the URL; patch the parser to treat the fixture as Google News.
orig = build.parse_feed
build.parse_feed = lambda data, feed: orig(data, dict(feed, url="https://news.google.com/x") if feed.get("_google") else feed)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / "config.json").write_text(json.dumps(cfg))
    res = build.build(tmp / "config.json", tmp / "out")
    titles = [i["title"] for i in res["items"]]
    print(titles)
    assert "Bitcoin climbs past record as ETF inflows grow" in titles
    assert titles.count("Bitcoin climbs past record as ETF inflows grow") == 1, "duplicate not removed"
    assert "NRB keeps policy rate unchanged in monetary policy review" in titles, "google suffix not stripped"
    assert "Central bank digital currency pilots expand" in titles
    for bad in ("Sponsored: Best casino tokens", "Old story", "Football team wins cup", "Celebrity wedding photos"):
        assert bad not in titles, bad
    btc = next(i for i in res["items"] if i["link"] == "https://example.com/btc")
    assert btc["summary"] == "Bitcoin rose 4% on Tuesday & more.", btc["summary"]
    page = (tmp / "out" / "index.html").read_text()
    assert "0x1234567890abcdef" in page and "Support the site" in page
    assert "illegal in Nepal" in page
    for f in ("about.html", "feed.xml", "items.json", "style.css", "app.js", "favicon.svg"):
        assert (tmp / "out" / f).exists(), f
    import xml.etree.ElementTree as ET; ET.parse(tmp / "out" / "feed.xml")
    # second build keeps history from items.json even when feeds are empty of new items
    res2 = build.build(tmp / "config.json", tmp / "out")
    assert len(res2["items"]) == len(res["items"])
print("OK: all checks passed")
