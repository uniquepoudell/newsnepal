"""Offline test: builds the site from local fixture feeds. Run: python tests/test_build.py"""
import json, os, sys, tempfile, types
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
cfg["visa"]["feeds"] = [
    {"name": "VisaEN", "url": (fx / "visa.xml").as_uri(), "category": "visa", "filter": True, "_google": True},
]
cfg["visa"]["featured_agents"] = [{"name": "Test Agent", "marn": "1234567", "city": "Sydney"}]
cfg["monetization"]["donations"]["addresses"][0]["address"] = "0x1234567890abcdef1234567890abcdef12345678"
cfg["monetization"]["support"]["stripe_payment_link"] = "https://buy.stripe.com/test_123"
cfg["monetization"]["support"]["nepal_qr_image"] = "support-qr.png"
os.environ["NO_OG_LOOKUPS"] = "1"   # tests run offline
os.environ["NO_FOREX"] = "1"

# Google-style parsing is keyed on the URL; patch the parser to treat the fixture as Google News.
orig = build.parse_feed
build.parse_feed = lambda data, feed: orig(data, dict(feed, url="https://news.google.com/x") if feed.get("_google") else feed)


# Fake Claude API so the translation path runs offline.
class _Resp:
    def __init__(self, payload):
        n = len(payload)
        self.stop_reason = "end_turn"
        self.content = [types.SimpleNamespace(type="text", text=json.dumps({"items": [
            {"id": i, "title_ne": "नेपाली शीर्षक " + str(i), "summary_ne": "सारांश"} for i in range(n)]}))]
        self.usage = types.SimpleNamespace(input_tokens=1, output_tokens=1)

CALLS = []
def _create(**kw):
    CALLS.append(kw)
    payload = json.loads(kw["messages"][0]["content"].split("<items>")[1].split("</items>")[0])
    return _Resp(payload)

fake = types.ModuleType("anthropic")
fake.Anthropic = lambda **kw: types.SimpleNamespace(
    messages=types.SimpleNamespace(create=_create),
    beta=types.SimpleNamespace(messages=types.SimpleNamespace(create=_create)))
sys.modules["anthropic"] = fake
os.environ["ANTHROPIC_API_KEY"] = "test"

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
    assert btc["image"] == "https://img.example.com/btc.jpg", btc.get("image")
    eth = next(i for i in res["items"] if i["link"] == "https://example.com/eth")
    assert eth["image"] == "https://img.example.com/eth.png", "http image not upgraded to https"
    cbdc = next(i for i in res["items"] if i["link"] == "https://example.org/cbdc")
    assert cbdc["image"] == "https://img.example.org/cbdc.png", cbdc.get("image")
    nrb = next(i for i in res["items"] if i["title"].startswith("NRB keeps"))
    assert nrb["image"] == ""
    page = (tmp / "out" / "index.html").read_text()
    assert "https://img.example.com/btc.jpg" in page and "Image: CryptoFeed" in page
    assert "img/ph-nepal.svg" in page, "placeholder not used for imageless story"
    assert 'class="story hero"' in page
    assert "buy.stripe.com/test_123" in page and "support-qr.png" in page and "Support News Nepal" in page
    assert 'id="q"' in page and 'id="theme-toggle"' in page and "wa.me" in page and 'data-coin="bitcoin"' in page
    support = (tmp / "out" / "support.html").read_text()
    assert "0x1234567890abcdef" in support and "buy.stripe.com/test_123" in support
    support_ne = (tmp / "out" / "support.ne.html").read_text()
    assert "न्युज नेपाललाई सहयोग" in support_ne and "buy.stripe.com/test_123" in support_ne
    assert "img/ph-visa.svg" in (tmp / "out" / "visa.html").read_text()
    assert "illegal in Nepal" in page
    # visa section: needs a visa word AND Australia; Nepali words match inside longer words
    vt = [i["title"] for i in res["visa_items"]]
    print(vt)
    assert "Australia tightens student visa rules for Nepal applicants" in vt
    assert "अस्ट्रेलियामा विद्यार्थी भिसाका नियम अझ कडा" in vt
    assert not any("UK" in t or "cricket" in t for t in vt), vt
    # translation: English stories get Nepali text, Nepali stories are not sent
    assert CALLS and CALLS[0]["model"] == cfg["translation"]["model"]
    sent = [x["title"] for c in CALLS for x in json.loads(c["messages"][0]["content"].split("<items>")[1].split("</items>")[0])]
    assert "अस्ट्रेलियामा विद्यार्थी भिसाका नियम अझ कडा" not in sent
    assert all(i.get("title_ne") for i in res["items"] + res["visa_items"])
    ne_page = (tmp / "out" / "index.ne.html").read_text()
    assert '<html lang="ne">' in ne_page and "नेपाली शीर्षक" in ne_page and 'href="index.html"' in ne_page
    visa_ne = (tmp / "out" / "visa.ne.html").read_text()
    assert "अस्ट्रेलिया भिसा" in visa_ne and "MARN 1234567" in visa_ne and "migration advice" not in visa_ne
    check = (tmp / "out" / "check-agent.html").read_text()
    assert 'id="flags"' in check and "portal.mara.gov.au" in check and "not migration advice" in check
    for f in ("index.ne.html", "about.ne.html", "visa.html", "check-agent.ne.html", "visa-changes-2026.html",
              "visa-changes-2026.ne.html", "visa-scams.html", "visa-scams.ne.html", "visa-items.json"):
        assert (tmp / "out" / f).exists(), f
    for f in ("about.html", "support.html", "feed.xml", "items.json", "style.css", "app.js", "favicon.svg",
              "logo.svg", "logo-mark.svg", "img/ph-nepal.svg", "img/ph-crypto.svg", "img/ph-visa.svg"):
        assert (tmp / "out" / f).exists(), f
    import xml.etree.ElementTree as ET; ET.parse(tmp / "out" / "feed.xml")
    # second build keeps history from items.json even when feeds are empty of new items
    n_calls = len(CALLS)
    res2 = build.build(tmp / "config.json", tmp / "out")
    assert len(res2["items"]) == len(res["items"])
    assert all(a.get("image") == b.get("image") for a, b in zip(res["items"], res2["items"])), "images lost on rebuild"
    assert len(CALLS) == n_calls, "stories were translated twice"
    assert all(i.get("title_ne") for i in res2["items"]), "translations lost between builds"
print("OK: all checks passed")
