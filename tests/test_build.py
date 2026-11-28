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

# Fake image generator so tests never call a real API.
import illustrate  # noqa: E402
GEN_CALLS = []
def _fake_generate(it, cfg):
    GEN_CALLS.append(illustrate.make_prompt(it))
    return b"\xff\xd8\xff" + b"0" * 5000
illustrate.generate = _fake_generate
os.environ["CLOUDFLARE_ACCOUNT_ID"], os.environ["CLOUDFLARE_AI_TOKEN"] = "test", "test"

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
    # stories without a publisher picture get one AI illustration each, credited to News Nepal
    assert nrb.get("gen", "").startswith("gen/") and (tmp / "out" / nrb["gen"]).exists(), nrb
    assert all(not i.get("gen") for i in res["items"] if i.get("image")), "illustrated a story that has a picture"
    assert any("NRB keeps policy rate" in c and "no text at all" in c for c in GEN_CALLS), GEN_CALLS[:1]
    page = (tmp / "out" / "index.html").read_text()
    assert "https://img.example.com/btc.jpg" in page and "Image: CryptoFeed" in page
    assert "Illustration: News Nepal (AI)" in page and nrb["gen"] in page
    assert 'class="carousel"' in page and 'class="slide"' in page and 'class="rail"' in page and 'data-pick="crypto"' in page
    assert 'class="to-top"' in page and 'class="quick"' in page and page.count('class="story"') == len(res["items"])
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
    # rates page exists in both languages and is in the nav, even when rates are off (offline)
    rates_off = (tmp / "out" / "rates.html").read_text()
    assert "AUD to NPR today" in rates_off and "nrb.org.np/forex" in rates_off and "could not be read" in rates_off
    assert 'href="rates.html"' in page and (tmp / "out" / "rates.ne.html").exists()
    assert "uniquepoudell.github.io/gorkhapay" in rates_off, "GorkhaPay compare link missing"
    assert (tmp / "out" / "rates-archive.html").exists() and (tmp / "out" / "rates-archive.ne.html").exists()
    assert json.loads((tmp / "out" / "rates-history.json").read_text())["days"] == []
    for _f in ("sar-to-npr.html", "sar-to-npr.ne.html", "aud-to-npr.html", "krw-to-npr.ne.html"):
        assert (tmp / "out" / _f).exists(), _f
    if (tmp / "out" / "sitemap.xml").exists():
        assert "sar-to-npr.html" in (tmp / "out" / "sitemap.xml").read_text()
    # second build keeps history from items.json even when feeds are empty of new items
    n_calls = len(CALLS)
    n_gen = len(GEN_CALLS)
    res2 = build.build(tmp / "config.json", tmp / "out")
    assert len(res2["items"]) == len(res["items"])
    assert all(a.get("image") == b.get("image") for a, b in zip(res["items"], res2["items"])), "images lost on rebuild"
    assert len(CALLS) == n_calls, "stories were translated twice"
    assert len(GEN_CALLS) == n_gen, "illustrations were made twice"
    assert all(i.get("gen") for i in res2["items"] if not i.get("image")), "illustrations lost between builds"
    assert all(i.get("title_ne") for i in res2["items"]), "translations lost between builds"
print("OK: all checks passed")

# Forex fallback: when NRB is unreachable, market rates are converted to rupees per unit.
_orig_fetch, _orig_nrb = build.fetch, build._nrb_rates
build.fetch = lambda url, timeout=25: json.dumps({"rates": {"USD": 1, "NPR": 134.0, "AUD": 1.5, "INR": 84.0}}).encode()
build._nrb_rates = lambda wanted: (_ for _ in ()).throw(ConnectionError("closed"))
os.environ.pop("NO_FOREX", None)
fx_rates = {r["code"]: r for r in build.fetch_forex({"ticker": {"forex": ["USD", "AUD", "INR"]}})}
assert round(fx_rates["USD"]["sell"], 2) == 134.0 and round(fx_rates["AUD"]["sell"], 2) == 89.33, fx_rates
assert fx_rates["INR"]["unit"] == 100 and round(fx_rates["INR"]["sell"], 2) == 159.52 and fx_rates["USD"]["src"] == "market"
assert "market rate" in build.render_ticker({"ticker": {"coins": []}}, list(fx_rates.values()), "en")
build.fetch, build._nrb_rates = _orig_fetch, _orig_nrb
print("OK: forex fallback")

# Rates page: AUD to NPR today and the full NRB table, from NRB data, in both languages.
NRB = [{"code": "USD", "unit": 1, "buy": 134.5, "sell": 135.1, "date": "2026-11-26", "src": "nrb"},
       {"code": "AUD", "unit": 1, "buy": 88.0, "sell": 88.4, "date": "2026-11-26", "src": "nrb"},
       {"code": "JPY", "unit": 10, "buy": 9.0, "sell": 9.05, "date": "2026-11-26", "src": "nrb"},
       {"code": "INR", "unit": 100, "buy": 160.0, "sell": 160.15, "date": "2026-11-26", "src": "nrb"}]
from datetime import datetime, timezone
when = datetime(2026, 11, 26, 6, 0, tzinfo=timezone.utc)
en = build.render_rates(cfg, NRB, when, "en", NRB[:2])
assert "1 Australian dollar =" in en and "Rs 88.00" in en and "Selling Rs 88.40" in en, en[:400]
assert "<td>1,000</td><td>Rs 88,000.00</td>" in en, "AUD amount table wrong"
assert 'data-rate="0.900000"' in en, "JPY per-unit rate wrong"
assert "Japanese yen" in en and "<td>100</td><td>160.00</td>" in en and "2026-11-26" in en
assert "Nepal Rastra Bank" in en and "not financial advice" in en and "2026-11-26 11:45 (NPT)" in en
assert 'id="fx-calc" hidden' in en and 'class="ticker"' in en and 'href="rates.html"' in en
ne = build.render_rates(cfg, NRB, when, "ne")
assert '<html lang="ne">' in ne and "अस्ट्रेलियन डलर" in ne and "जापानी येन" in ne and 'href="rates.html"' in ne
mkt = build.render_rates(cfg, [dict(r, src="market", date="", sell=r["buy"]) for r in NRB], when, "en")
assert "market mid rates" in mkt and "Mid rate" in mkt and "Selling Rs" not in mkt
# Rate history: change arrows on rates.html, one fixed page per NRB day, archive, merge with saved history.
HIST = [{"date": "2026-11-26", "rates": NRB},
        {"date": "2026-11-25", "rates": [dict(r, buy=r["buy"] - (0.5 if r["code"] == "AUD" else -0.25) if r["code"] != "JPY" else r["buy"],
                                              date="2026-11-25") for r in NRB]},
        {"date": "2026-11-24", "rates": [dict(r, date="2026-11-24") for r in NRB[:2]]}]
en = build.render_rates(cfg, NRB, when, "en", NRB[:2], HIST)
assert '<td class="chg up"><span aria-hidden="true">▲</span> +0.50</td>' in en, "AUD rise arrow missing"
assert '<td class="chg down"><span aria-hidden="true">▼</span> −0.25</td>' in en, "USD fall arrow missing"
assert '<td class="chg same">0.00</td>' in en and "previous published day (2026-11-25)" in en
assert 'href="rates-2026-11-25.html"' in en and 'href="rates-2026-11-26.html"' not in en and 'href="rates-archive.html"' in en
assert "<th>Change</th>" not in build.render_rates(cfg, NRB, when, "en"), "change column without history"
mid = build.render_rates_day(cfg, HIST, 1, "en")
assert "NRB exchange rate on 2026-11-25" in mid and "Rs 87.50" in mid
assert 'href="rates-2026-11-24.html" rel="prev"' in mid and 'href="rates-2026-11-26.html" rel="next"' in mid
assert "previous published day (2026-11-24)" in mid, "day page compares with the wrong day"
assert 'aria-current="page">Rates<' in mid and "uniquepoudell.github.io/gorkhapay" in mid and "not financial advice" in mid
last = build.render_rates_day(cfg, HIST, 2, "ne")
assert 'rel="prev"' not in last and '<html lang="ne">' in last and 'href="rates-2026-11-25.ne.html" rel="next"' in last
assert "<th>फरक</th>" not in last, "oldest day has no previous day to compare"
arch = build.render_rates_archive(cfg, HIST, "en")
assert "<h2>2026-11</h2>" in arch and arch.index("2026-11-26") < arch.index("2026-11-24") and "AUD Rs 88.00" in arch
assert "could not be read" in build.render_rates_archive(cfg, [], "en")
merged = build.merge_rate_history([{"date": "2026-11-26", "rates": ["new"]}],
                                  [{"date": "2026-11-26", "rates": ["old"]}, {"date": "2025-01-01", "rates": ["x"]},
                                   {"date": "../evil", "rates": ["x"]}, {"date": "2026-11-20", "rates": []}], keep_days=5)
assert merged == [{"date": "2026-11-26", "rates": ["new"]}, {"date": "2025-01-01", "rates": ["x"]}], merged
assert len(build.merge_rate_history([{"date": f"2026-01-{d:02d}", "rates": [1]} for d in range(1, 21)], [], 7)) == 7
# NRB history parsing (network stubbed): pages followed, days keyed by date, newest first.
_orig_payload = build._nrb_payload
def _fake_payload(start, end, per_page=100, max_pages=5):
    return [{"date": "2026-11-25", "rates": [{"currency": {"iso3": "AUD", "unit": 1}, "buy": "87.50", "sell": "87.9"}]},
            {"date": "2026-11-26", "rates": [{"currency": {"iso3": "aud", "unit": 1}, "buy": "88", "sell": "88.4"},
                                             {"currency": {"iso3": "JPY", "unit": 10}, "buy": "9", "sell": "9.05"}]},
            {"date": "2026-11-23", "rates": []}]
build._nrb_payload = _fake_payload
hist = build.nrb_history(["AUD", "JPY"])
assert [d["date"] for d in hist] == ["2026-11-26", "2026-11-25"], hist
assert hist[0]["rates"][1] == {"code": "JPY", "unit": 10, "buy": 9.0, "sell": 9.05, "date": "2026-11-26", "src": "nrb"}
build._nrb_payload = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("closed"))
assert build.nrb_history(["AUD"]) == []
build._nrb_payload = _orig_payload
# NRB retry: a dropped request is retried, and gives up after the last try.
import io, datetime as _dt  # noqa: E402
_orig_open, _tries = build.urllib.request.urlopen, []
def _flaky(req, timeout=None):
    _tries.append(1)
    if len(_tries) < 3:
        raise TimeoutError("The read operation timed out")
    return io.BytesIO(b'{"data": {"payload": []}}')
build.urllib.request.urlopen = _flaky
assert build._nrb_get("https://x", tries=3, wait=0) == {"data": {"payload": []}} and len(_tries) == 3
_tries.clear()
try:
    build._nrb_get("https://x", tries=2, wait=0)
    raise AssertionError("should give up after the last try")
except TimeoutError:
    assert len(_tries) == 2
build.urllib.request.urlopen = _orig_open
# When NRB can't be read, a recent NRB day saved by an earlier build is used before market rates.
_today = _dt.date(2026, 11, 27)
_saved = [{"date": "2026-11-26", "rates": [dict(r, date="2026-11-26") for r in NRB]}]
assert build.saved_nrb_day(_saved, _today) == _saved[0]["rates"]
assert build.saved_nrb_day(_saved, _dt.date(2026, 12, 5)) == [], "too old to call today's rate"
assert build.saved_nrb_day([], _today) == [] and build.saved_nrb_day([{"date": "bad", "rates": NRB}], _today) == []
assert build.saved_nrb_day([{"date": "2026-11-26", "rates": [dict(NRB[0], src="market")]}], _today) == []
# Per-currency landing pages (SAR to NPR today ...): rate, amounts, recent days, honest send box.
_c = {c["code"]: c for c in build.corridors(cfg)}
assert {"AUD", "SAR", "QAR", "AED", "MYR", "KRW", "USD"} <= set(_c), _c
assert build.corridor_page("SAR") == "sar-to-npr"
_rates = NRB + [{"code": "SAR", "unit": 1, "buy": 35.8, "sell": 36.0, "date": "2026-11-26", "src": "nrb"},
                {"code": "KRW", "unit": 100, "buy": 9.6, "sell": 9.65, "date": "2026-11-26", "src": "nrb"}]
_h = [{"date": "2026-11-26", "rates": _rates}, {"date": "2026-11-25", "rates": [dict(_rates[-2], buy=35.5, date="2026-11-25")]}]
sar = build.render_corridor(cfg, _c["SAR"], _rates, when, "en", _h)
assert "Saudi riyal (SAR) to Nepali rupee today" in sar and "1 SAR =" in sar and "Rs 35.80" in sar, sar[:3000]
assert "<td>1,000</td><td>Rs 35,800.00</td>" in sar and 'href="rates-2026-11-25.html"' in sar and "+0.30" in sar
assert "Saudi Arabia" in sar and 'aria-current="page"' in sar and 'href="aud-to-npr.html"' in sar
assert "gorkhapay" not in sar.split("<main")[1], "GorkhaPay only compares AUD; no link on other corridors"
assert 'href="sar-to-npr.html"' not in sar.split("<main")[1].split("Other currencies")[1]
krw = build.render_corridor(cfg, _c["KRW"], _rates, when, "ne", _h)
assert '<html lang="ne">' in krw and "100 KRW =" in krw and "Rs 9.60" in krw and "दक्षिण कोरियाली वोन" in krw
assert "<td>1,000,000</td><td>Rs 96,000.00</td>" in krw
aud = build.render_corridor(cfg, _c["AUD"], _rates, when, "en", _h)
assert "uniquepoudell.github.io/gorkhapay" in aud
assert "could not be read" in build.render_corridor(cfg, _c["QAR"], [], when, "en", [])
assert 'href="sar-to-npr.html"' in build.render_rates(cfg, NRB, when, "en")
assert 'href="sar-to-npr.ne.html"' in build.render_rates(cfg, NRB, when, "ne")
print("OK: rates page")
# Our checklists box: on visa pages and the AUD page only, links to the GorkhaPay sales page (never Stripe).
_vis_en = build.visa_sidebar(cfg, "en")
assert "Our checklists" in _vis_en and "gorkhapay/products/arriving-australia-checklist.html" in _vis_en, _vis_en
assert "A$5" in _vis_en and "buy.stripe.com" not in build.product_box(cfg, "en")
assert "not visa or tax advice" in _vis_en
_vis_ne = build.visa_sidebar(cfg, "ne")
assert "हाम्रा चेकलिस्ट" in _vis_ne and "अस्ट्रेलिया आउँदा" in _vis_ne and "Our checklists" not in _vis_ne
assert "Our checklists" in aud and "Our checklists" not in sar
assert build.product_box(dict(cfg, products={"items": []}), "en") == ""
for _x in cfg["products"]["items"]:
    assert _x["url"].startswith("https://uniquepoudell.github.io/gorkhapay/products/"), _x
print("OK: product box")
