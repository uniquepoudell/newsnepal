#!/usr/bin/env python3
"""Build the News Nepal Crypto site.

Fetches the RSS/Atom feeds listed in config.json, keeps only stories about
digital currency and finance, and writes a static site to ./public:

  index.html   headlines, short summaries, links to the original articles
  about.html   what the site is, plus the legal disclaimer
  items.json   the stories as data (also used to keep history between builds)
  feed.xml     the site's own RSS feed
  robots.txt, ads.txt (when an AdSense id is set), CNAME (when a domain is set)

Only the Python standard library is used, so it runs anywhere with Python 3.9+.

Usage:  python scripts/build.py [--config config.json] [--out public]
"""
from __future__ import annotations

import argparse
import email.utils
import html
import json
import os
import re
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEPAL_TZ = timezone(timedelta(hours=5, minutes=45))
USER_AGENT = "Mozilla/5.0 (compatible; NewsNepalCryptoBot/1.0; +https://newsnepal.crypto)"

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
MEDIA = "{http://search.yahoo.com/mrss/}"
DC = "{http://purl.org/dc/elements/1.1/}"


# --------------------------------------------------------------------------- text helpers

class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "figure", "figcaption"):
            self._skip += 1
        elif tag in ("p", "br", "div", "li"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "figure", "figcaption") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def strip_html(text: str) -> str:
    if not text:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(text)
        parser.close()
        out = "".join(parser.parts)
    except Exception:
        out = re.sub(r"<[^>]+>", " ", text)
    out = html.unescape(out)
    return re.sub(r"\s+", " ", out).strip()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:-–— ")
    return cut + "…"


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _text(el, *paths) -> str:
    for p in paths:
        found = el.find(p)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


# --------------------------------------------------------------------------- fetching and parsing

def fetch(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_feed(data: bytes, feed: dict) -> list[dict]:
    root = ET.fromstring(data)
    items: list[dict] = []
    is_google = "news.google.com" in feed.get("url", "")

    if root.tag == f"{ATOM}feed":
        entries = root.findall(f"{ATOM}entry")
        for e in entries:
            link = ""
            for l in e.findall(f"{ATOM}link"):
                if l.get("rel", "alternate") == "alternate" and l.get("href"):
                    link = l.get("href")
                    break
            items.append({
                "title": _text(e, f"{ATOM}title"),
                "link": link,
                "summary_html": _text(e, f"{ATOM}summary", f"{ATOM}content"),
                "date": _text(e, f"{ATOM}published", f"{ATOM}updated"),
                "source": feed["name"],
            })
    else:
        channel = root.find("channel")
        entries = channel.findall("item") if channel is not None else root.iter("item")
        for e in entries:
            source = feed["name"]
            src_el = e.find("source")
            if is_google and src_el is not None and (src_el.text or "").strip():
                source = src_el.text.strip()
            title = _text(e, "title")
            summary_html = "" if is_google else _text(e, "description", f"{CONTENT}encoded")
            if is_google and source and title.endswith(" - " + source):
                title = title[: -len(" - " + source)]
            items.append({
                "title": title,
                "link": _text(e, "link", "guid"),
                "summary_html": summary_html,
                "date": _text(e, "pubDate", f"{DC}date"),
                "source": source,
            })

    out = []
    for it in items:
        title = strip_html(it["title"])
        link = (it["link"] or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        dt = parse_date(it["date"])
        out.append({
            "title": title,
            "link": link,
            "summary": strip_html(it["summary_html"]),
            "published": dt.isoformat() if dt else None,
            "source": it["source"],
            "feed": feed["name"],
            "category": feed.get("category", "crypto"),
        })
    return out


# --------------------------------------------------------------------------- filtering

def compile_words(words: list[str]) -> re.Pattern | None:
    words = [w.strip() for w in words if w and w.strip()]
    if not words:
        return None
    alts = sorted((re.escape(w).replace(r"\ ", r"[\s-]+") for w in words), key=len, reverse=True)
    return re.compile(r"(?<![\w])(?:" + "|".join(alts) + r")(?![\w])", re.IGNORECASE)


def keep(item: dict, feed: dict, include: re.Pattern | None, exclude: re.Pattern | None) -> bool:
    text = f"{item['title']} {item['summary']}"
    if exclude and exclude.search(text):
        return False
    if feed.get("filter", True) and include is not None:
        return bool(include.search(text))
    return True


def norm_key(item: dict) -> str:
    title = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()
    return title[:90]


# --------------------------------------------------------------------------- rendering

def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def nepal_time(iso: str | None) -> str:
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso).astimezone(NEPAL_TZ)
    return dt.strftime("%d %b %Y, %I:%M %p NPT").lstrip("0")


def adsense_unit(m: dict, slot: str, label: str) -> str:
    client = m.get("adsense_client", "").strip()
    if client and slot:
        return (f'<div class="ad" aria-label="Advertisement"><span class="ad-label">Advertisement</span>'
                f'<ins class="adsbygoogle" style="display:block" data-ad-client="{esc(client)}" '
                f'data-ad-slot="{esc(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
                f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script></div>')
    if os.environ.get("SHOW_AD_PLACEHOLDERS") == "1":
        return f'<div class="ad ad-placeholder"><span class="ad-label">Ad space</span>{esc(label)}</div>'
    return ""


def page_shell(cfg: dict, title: str, body: str, *, description: str, path: str = "") -> str:
    s, m = cfg["site"], cfg["monetization"]
    base = s.get("base_url", "").rstrip("/")
    canonical = f'<link rel="canonical" href="{esc(base + "/" + path)}">' if base else ""
    ads_head = ""
    if m.get("adsense_client", "").strip():
        ads_head = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='
                    f'{esc(m["adsense_client"].strip())}" crossorigin="anonymous"></script>')
    return f"""<!doctype html>
<html lang="{esc(s.get('language', 'en'))}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
{canonical}
<link rel="alternate" type="application/rss+xml" title="{esc(s['title'])}" href="feed.xml">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="style.css">
{ads_head}
</head>
<body>
<header class="masthead">
  <div class="wrap">
    <a class="brand" href="./"><span class="logo" aria-hidden="true">₿</span>{esc(s['title'])}</a>
    <nav><a href="./">Headlines</a><a href="about.html">About</a><a href="feed.xml">RSS</a></nav>
  </div>
</header>
{body}
<footer class="site-footer">
  <div class="wrap">
    <p class="disclaimer"><strong>News and education only.</strong> News Nepal Crypto collects headlines from other
    publishers and links to the original articles. Nothing here is financial advice or an offer to buy, sell or
    trade any asset. Under Nepal Rastra Bank rules, trading and mining cryptocurrency is illegal in Nepal.</p>
    <p>Headlines and summaries belong to their publishers. © {datetime.now(NEPAL_TZ).year} {esc(s['title'])}
    {(' · <a href="mailto:' + esc(m['contact_email']) + '">Contact</a>') if m.get('contact_email') else ''}</p>
  </div>
</footer>
<script src="app.js" defer></script>
</body>
</html>
"""


def render_index(cfg: dict, items: list[dict], built_at: datetime) -> str:
    s, m = cfg["site"], cfg["monetization"]
    cats = {c["id"]: c["label"] for c in cfg["categories"]}

    tabs = ['<button class="tab is-active" data-cat="all" aria-pressed="true">All</button>']
    for c in cfg["categories"]:
        n = sum(1 for i in items if i["category"] == c["id"])
        if n:
            tabs.append(f'<button class="tab" data-cat="{esc(c["id"])}" aria-pressed="false">'
                        f'{esc(c["label"])} <span class="count">{n}</span></button>')

    cards = []
    every = max(int(m.get("ad_every_n_items") or 0), 0)
    for idx, it in enumerate(items, 1):
        summary = f'<p class="summary">{esc(it["summary"])}</p>' if it["summary"] else ""
        when = (f'<time datetime="{esc(it["published"])}">{esc(nepal_time(it["published"]))}</time>'
                if it["published"] else "")
        cards.append(f"""<article class="story" data-cat="{esc(it['category'])}">
  <div class="meta"><span class="pill pill-{esc(it['category'])}">{esc(cats.get(it['category'], it['category']))}</span>
  <span class="source">{esc(it['source'])}</span>{when}</div>
  <h2><a href="{esc(it['link'])}" target="_blank" rel="noopener nofollow">{esc(it['title'])}</a></h2>
  {summary}
  <a class="read" href="{esc(it['link'])}" target="_blank" rel="noopener nofollow">Read at {esc(it['source'])} ↗</a>
</article>""")
        if every and idx % every == 0 and idx != len(items):
            ad = adsense_unit(m, m.get("adsense_slot_feed", ""), "In-feed ad (Google AdSense or a direct sponsor)")
            if ad:
                cards.append(ad)

    if not cards:
        cards.append('<p class="empty">No stories right now. The next update runs within the hour.</p>')

    # Sidebar: sponsor, donations, affiliate links. Each block hides itself when empty.
    side = []
    sp = m.get("sponsor") or {}
    if sp.get("text"):
        link = f'<a href="{esc(sp.get("url"))}" target="_blank" rel="noopener sponsored">{esc(sp["text"])}</a>' \
            if sp.get("url") else esc(sp["text"])
        side.append(f'<section class="box sponsor"><h3>Sponsor</h3><p>{link}</p></section>')
    elif os.environ.get("SHOW_AD_PLACEHOLDERS") == "1":
        side.append('<section class="box sponsor ad-placeholder"><h3>Sponsor</h3><p>Your brand here. Sell this spot to a Nepali business.</p></section>')

    don = m.get("donations") or {}
    addrs = [a for a in don.get("addresses", []) if a.get("address")]
    if addrs:
        rows = "".join(
            f'<li><span class="coin">{esc(a["coin"])}</span><code>{esc(a["address"])}</code>'
            f'<button class="copy" data-copy="{esc(a["address"])}">Copy</button></li>' for a in addrs)
        ud = don.get("unstoppable_domain")
        ud_line = f'<p class="ud">Or send to <strong>{esc(ud)}</strong> from a wallet that supports Unstoppable Domains.</p>' if ud else ""
        side.append(f'<section class="box donate"><h3>Support the site</h3><p>{esc(don.get("message", ""))}</p>'
                    f'<ul class="addresses">{rows}</ul>{ud_line}'
                    f'<p class="fine">Tips from outside Nepal only, where this is legal.</p></section>')
    elif os.environ.get("SHOW_AD_PLACEHOLDERS") == "1":
        side.append('<section class="box donate ad-placeholder"><h3>Support the site</h3><p>Donation addresses appear here once added to config.json.</p></section>')

    affs = [a for a in m.get("affiliate_links", []) if a.get("label") and a.get("url")]
    if affs:
        rows = "".join(
            f'<li><a href="{esc(a["url"])}" target="_blank" rel="noopener sponsored">{esc(a["label"])}</a>'
            f'{(" <span>" + esc(a["note"]) + "</span>") if a.get("note") else ""}</li>' for a in affs)
        side.append(f'<section class="box affiliates"><h3>Recommended</h3><ul>{rows}</ul>'
                    f'<p class="fine">Some links earn us a commission at no cost to you.</p></section>')

    top_ad = adsense_unit(m, m.get("adsense_slot_top", ""), "Top banner ad (Google AdSense or a direct sponsor)")
    counts = f"{len(items)} stories from {len({i['source'] for i in items})} sources"

    body = f"""<main class="wrap layout">
  <div class="feed">
    <div class="intro">
      <h1>{esc(s['tagline'])}</h1>
      <p class="updated">Updated <time datetime="{built_at.isoformat()}" data-relative>{esc(nepal_time(built_at.isoformat()))}</time> · {counts}</p>
    </div>
    {top_ad}
    <div class="tabs" role="toolbar" aria-label="Filter by topic">{''.join(tabs)}</div>
    <div class="stories">
{chr(10).join(cards)}
    </div>
  </div>
  <aside class="side">
    <section class="box notice"><h3>News, not advice</h3><p>We cover digital currency and finance as news and
    education. Crypto trading and mining are illegal in Nepal, so nothing here recommends buying or trading.</p></section>
    {''.join(side)}
  </aside>
</main>"""
    return page_shell(cfg, f"{s['title']} | Digital currency and finance news for Nepal", body,
                      description=s["tagline"])


def render_about(cfg: dict) -> str:
    s = cfg["site"]
    sources = sorted({f["name"] for f in cfg["feeds"]})
    li = "".join(f"<li>{esc(n)}</li>" for n in sources)
    body = f"""<main class="wrap prose">
<h1>About {esc(s['title'])}</h1>
<p>{esc(s['title'])} gathers headlines about digital currencies, blockchain, banking and the economy, with a
focus on Nepal. A script checks the sources below every hour, keeps only stories on those topics, and shows the
headline, a short summary and a link to the full article on the publisher's site.</p>
<h2>Sources we check</h2>
<ul>{li}</ul>
<h2>Disclaimer</h2>
<p>This site is for news and education only. It is not financial, legal or investment advice, and it does not
offer, promote or arrange the purchase, sale, trading or mining of any cryptocurrency. Nepal Rastra Bank has
declared cryptocurrency transactions illegal in Nepal. Readers are responsible for following the laws where they live.</p>
<p>Every headline and summary belongs to its original publisher. If you are a publisher and want your feed removed,
contact us and we will remove it.</p>
</main>"""
    return page_shell(cfg, f"About | {s['title']}", body,
                      description=f"About {s['title']} and its sources", path="about.html")


def render_rss(cfg: dict, items: list[dict], built_at: datetime) -> str:
    s = cfg["site"]
    base = s.get("base_url", "").rstrip("/") or "https://newsnepal.crypto"
    parts = [f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
             f'<title>{esc(s["title"])}</title><link>{esc(base)}/</link>'
             f'<description>{esc(s["tagline"])}</description>'
             f'<lastBuildDate>{email.utils.format_datetime(built_at)}</lastBuildDate>']
    for it in items[:50]:
        pub = (f"<pubDate>{email.utils.format_datetime(datetime.fromisoformat(it['published']))}</pubDate>"
               if it["published"] else "")
        parts.append(f"<item><title>{esc(it['title'])}</title><link>{esc(it['link'])}</link>"
                     f"<guid isPermaLink=\"true\">{esc(it['link'])}</guid>"
                     f"<description>{esc(it['summary'])}</description>"
                     f"<source url=\"{esc(base)}/feed.xml\">{esc(it['source'])}</source>{pub}</item>")
    parts.append("</channel></rss>\n")
    return "".join(parts)


# --------------------------------------------------------------------------- main

def load_previous(cfg: dict, out: Path) -> list[dict]:
    """Earlier stories, so the page keeps history when a feed drops older items."""
    local = out / "items.json"
    if local.exists():
        try:
            return json.loads(local.read_text("utf-8")).get("items", [])
        except Exception:
            pass
    base = cfg["site"].get("base_url", "").rstrip("/")
    if base:
        try:
            return json.loads(fetch(base + "/items.json", timeout=15)).get("items", [])
        except Exception as e:
            print(f"  (no previous items.json at {base}: {e})")
    return []


def build(config_path: Path, out: Path) -> dict:
    cfg = json.loads(config_path.read_text("utf-8"))
    s = cfg["site"]
    if os.environ.get("SITE_BASE_URL"):
        s["base_url"] = os.environ["SITE_BASE_URL"]
    include = compile_words(cfg["keywords"].get("include", []))
    exclude = compile_words(cfg["keywords"].get("exclude", []))
    feeds_by_name = {f["name"]: f for f in cfg["feeds"]}

    fresh: list[dict] = []
    report = []
    for feed in cfg["feeds"]:
        if feed.get("enabled") is False:
            continue
        try:
            raw = parse_feed(fetch(feed["url"]), feed)
            kept = [i for i in raw if keep(i, feed, include, exclude)]
            fresh.extend(kept)
            report.append((feed["name"], len(raw), len(kept), ""))
        except Exception as e:  # one broken feed must not break the site
            report.append((feed["name"], 0, 0, f"{type(e).__name__}: {e}"))

    print("Feed report:")
    for name, total, kept, err in report:
        print(f"  {name:32} {'ERROR ' + err if err else f'{kept:3d} kept of {total:3d}'}")

    previous = [i for i in load_previous(cfg, out)
                if keep(i, feeds_by_name.get(i.get("feed"), {"filter": True}), include, exclude)]

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(s.get("max_age_days", 10)))
    seen_links, seen_titles, merged = set(), set(), []
    for it in fresh + previous:  # fresh first so updated summaries win
        link, tkey = it["link"].split("#")[0], norm_key(it)
        if link in seen_links or tkey in seen_titles:
            continue
        pub = datetime.fromisoformat(it["published"]) if it.get("published") else None
        if pub and pub < cutoff:
            continue
        if pub and pub > now + timedelta(hours=1):  # bad clocks in feeds
            it["published"] = now.isoformat()
        seen_links.add(link)
        seen_titles.add(tkey)
        it["summary"] = truncate(it.get("summary", ""), int(s.get("summary_chars", 240)))
        merged.append(it)

    merged.sort(key=lambda i: i.get("published") or "", reverse=True)
    items = merged[: int(s.get("max_items", 120))]

    if not items and not fresh and all(err for *_, err in report):
        print("Every feed failed and there is no history; not overwriting the site.", file=sys.stderr)
        sys.exit(1)

    out.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "static").iterdir():
        shutil.copy2(f, out / f.name)
    (out / "index.html").write_text(render_index(cfg, items, now), "utf-8")
    (out / "about.html").write_text(render_about(cfg), "utf-8")
    (out / "feed.xml").write_text(render_rss(cfg, items, now), "utf-8")
    (out / "items.json").write_text(json.dumps({"built": now.isoformat(), "items": items},
                                               ensure_ascii=False, indent=1), "utf-8")
    (out / "robots.txt").write_text("User-agent: *\nAllow: /\n", "utf-8")
    (out / ".nojekyll").write_text("", "utf-8")
    client = cfg["monetization"].get("adsense_client", "").strip()
    if client:
        pub_id = client.replace("ca-", "")
        (out / "ads.txt").write_text(f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n", "utf-8")
    domain = os.environ.get("CUSTOM_DOMAIN", "").strip()
    if domain:
        (out / "CNAME").write_text(domain + "\n", "utf-8")

    print(f"Built {len(items)} stories into {out}")
    return {"items": items, "report": report}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--out", default=str(ROOT / "public"))
    args = ap.parse_args()
    build(Path(args.config), Path(args.out))


if __name__ == "__main__":
    main()
