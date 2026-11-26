#!/usr/bin/env python3
"""Build the News Nepal Crypto site.

Fetches the RSS/Atom feeds listed in config.json, keeps only matching stories, and writes a
static site to ./public in English and Nepali:

  index.html / index.ne.html                 crypto and finance headlines
  visa.html / visa.ne.html                   Australia visa news for Nepalis
  check-agent.html / check-agent.ne.html     "check your migration agent" tool
  visa-changes-2026(.ne).html, visa-scams(.ne).html   guides
  about.html / about.ne.html                 what the site is, plus the legal disclaimer
  items.json, visa-items.json                stories as data (keeps history and translations)
  feed.xml                                   the site's own RSS feed
  robots.txt, sitemap.xml, ads.txt (when an AdSense id is set), CNAME (when a domain is set)

Nepali translations come from scripts/translate.py when ANTHROPIC_API_KEY is set.
Only the standard library is needed to build; translation also needs `pip install anthropic`.

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
            "lang": feed.get("lang", "en"),
        })
    return out


# --------------------------------------------------------------------------- filtering

def compile_words(words: list[str]) -> re.Pattern | None:
    """Whole-word match for English words; plain substring match for Nepali (Devanagari) words,
    because Nepali adds endings straight onto words (भिसा, भिसामा, भिसाको)."""
    words = [w.strip() for w in words if w and w.strip()]
    if not words:
        return None
    ascii_w = [w for w in words if w.isascii()]
    other_w = [w for w in words if not w.isascii()]
    parts = []
    if ascii_w:
        alts = sorted((re.escape(w).replace(r"\ ", r"[\s-]+") for w in ascii_w), key=len, reverse=True)
        parts.append(r"(?<![\w])(?:" + "|".join(alts) + r")(?![\w])")
    if other_w:
        parts.append("(?:" + "|".join(sorted((re.escape(w) for w in other_w), key=len, reverse=True)) + ")")
    return re.compile("|".join(parts), re.IGNORECASE)


def keep(item: dict, feed: dict, include: re.Pattern | None, exclude: re.Pattern | None,
         require: re.Pattern | None = None) -> bool:
    text = f"{item['title']} {item['summary']}"
    if exclude and exclude.search(text):
        return False
    if require and not require.search(text):
        return False
    if feed.get("filter", True) and include is not None:
        return bool(include.search(text))
    return True


def norm_key(item: dict) -> str:
    title = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()
    return title[:90]


# --------------------------------------------------------------------------- language

import translate  # noqa: E402  (scripts/translate.py)
import visa_content as V  # noqa: E402  (scripts/visa_content.py)

LANGS = ("en", "ne")

T = {
    "en": {
        "headlines": "Headlines", "visa": "Australia visa", "check": "Check your agent", "about": "About",
        "switch": "नेपाली", "updated": "Updated", "stories_from": "{n} stories from {s} sources",
        "all": "All", "read_at": "Read at {src} ↗", "empty": "No stories right now. The next update runs within the hour.",
        "news_not_advice": "News, not advice",
        "news_not_advice_p": "We cover digital currency and finance as news and education. Crypto trading and mining are illegal in Nepal, so nothing here recommends buying or trading.",
        "sponsor": "Sponsor", "support": "Support the site", "recommended": "Recommended",
        "copy": "Copy", "tips_outside": "Tips from outside Nepal only, where this is legal.",
        "commission": "Some links earn us a commission at no cost to you.",
        "or_send": "Or send to <strong>{ud}</strong> from a wallet that supports Unstoppable Domains.",
        "orig_lang": "", "in_english": "",
        "footer_crypto": "<strong>News and education only.</strong> News Nepal Crypto collects headlines from other publishers and links to the original articles. Nothing here is financial advice or an offer to buy, sell or trade any asset. Under Nepal Rastra Bank rules, trading and mining cryptocurrency is illegal in Nepal.",
        "footer_visa": "<strong>General information only, not migration advice.</strong> News Nepal is not a migration agent or law firm and cannot advise on your visa. For advice about your own situation, use a registered migration agent or an Australian lawyer. Always check rules on the official Home Affairs website.",
        "footer_own": "Headlines and summaries belong to their publishers.", "contact": "Contact",
        "machine": "",
    },
    "ne": {
        "headlines": "समाचार", "visa": "अस्ट्रेलिया भिसा", "check": "एजेन्ट जाँच्नुहोस्", "about": "हाम्रोबारे",
        "switch": "English", "updated": "अपडेट गरिएको", "stories_from": "{s} स्रोतबाट {n} समाचार",
        "all": "सबै", "read_at": "{src} मा पूरा पढ्नुहोस् (अंग्रेजीमा) ↗",
        "empty": "अहिले कुनै समाचार छैन। अर्को अपडेट एक घण्टाभित्र हुन्छ।",
        "news_not_advice": "समाचार हो, सल्लाह होइन",
        "news_not_advice_p": "हामी डिजिटल मुद्रा र वित्तलाई समाचार र शिक्षाको रूपमा मात्र प्रस्तुत गर्छौं। नेपालमा क्रिप्टो कारोबार र माइनिङ गैरकानुनी छ, त्यसैले यहाँ केही पनि किन्न वा कारोबार गर्न सिफारिस गरिँदैन।",
        "sponsor": "प्रायोजक", "support": "साइटलाई सहयोग गर्नुहोस्", "recommended": "सिफारिस",
        "copy": "कपी", "tips_outside": "नेपालबाहिरबाट मात्र, जहाँ यो कानुनी छ।",
        "commission": "केही लिंकबाट हामीलाई कमिसन आउँछ, तपाईंलाई थप खर्च लाग्दैन।",
        "or_send": "वा Unstoppable Domains चल्ने वालेटबाट <strong>{ud}</strong> मा पठाउनुहोस्।",
        "orig_lang": "", "in_english": "(अंग्रेजीमा)",
        "footer_crypto": "<strong>समाचार र शिक्षाका लागि मात्र।</strong> न्युज नेपाल क्रिप्टोले अरू प्रकाशकका शीर्षक संकलन गरी मूल लेखको लिंक दिन्छ। यहाँको कुनै पनि कुरा वित्तीय सल्लाह वा कुनै सम्पत्ति किनबेचको प्रस्ताव होइन। नेपाल राष्ट्र बैंकको नियमअनुसार नेपालमा क्रिप्टोकरेन्सी कारोबार र माइनिङ गैरकानुनी छ।",
        "footer_visa": "<strong>सामान्य जानकारी मात्र, माइग्रेसन सल्लाह होइन।</strong> न्युज नेपाल माइग्रेसन एजेन्ट वा कानुनी फर्म होइन र तपाईंको भिसाबारे सल्लाह दिन सक्दैन। आफ्नो अवस्थाबारे सल्लाहका लागि दर्ता भएको माइग्रेसन एजेन्ट वा अस्ट्रेलियाली वकिल प्रयोग गर्नुहोस्। नियम सधैं गृह मामिला विभागको आधिकारिक वेबसाइटमा जाँच्नुहोस्।",
        "footer_own": "शीर्षक र सारांश सम्बन्धित प्रकाशकका हुन्।", "contact": "सम्पर्क",
        "machine": "शीर्षक र सारांश स्वचालित रूपमा अनुवाद गरिएका हुन्, त्यसैले सानातिना गल्ती हुन सक्छन्। मूल लेख अंग्रेजीमा छ।",
    },
}


def page_file(base: str, lang: str) -> str:
    return f"{base}.html" if lang == "en" else f"{base}.ne.html"


def tr(field: dict, lang: str) -> str:
    return field.get(lang) or field.get("en", "")


def item_text(it: dict, lang: str) -> tuple[str, str]:
    if it.get("lang") == "ne":
        return it["title"], it.get("summary", "")
    if lang == "ne" and it.get("title_ne"):
        return it["title_ne"], it.get("summary_ne", "")
    return it["title"], it.get("summary", "")


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


def page_shell(cfg: dict, lang: str, base_name: str, title: str, body: str, *,
               description: str, kind: str = "crypto") -> str:
    s, m, t = cfg["site"], cfg["monetization"], T[lang]
    base = s.get("base_url", "").rstrip("/")
    here = page_file(base_name, lang)
    other_lang = "ne" if lang == "en" else "en"
    other = page_file(base_name, other_lang)
    links = ""
    if base:
        links = (f'<link rel="canonical" href="{esc(base + "/" + here)}">\n'
                 f'<link rel="alternate" hreflang="en" href="{esc(base + "/" + page_file(base_name, "en"))}">\n'
                 f'<link rel="alternate" hreflang="ne" href="{esc(base + "/" + page_file(base_name, "ne"))}">')
    ads_head = ""
    if m.get("adsense_client", "").strip():
        ads_head = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='
                    f'{esc(m["adsense_client"].strip())}" crossorigin="anonymous"></script>')
    nav = [("index", t["headlines"]), ("visa", t["visa"]), ("check-agent", t["check"]), ("about", t["about"])]
    current = ' aria-current="page"'
    nav_html = "".join(
        f'<a href="{page_file(b, lang)}"{current if b == base_name else ""}>{esc(label)}</a>'
        for b, label in nav)
    footer = t["footer_visa"] if kind == "visa" else t["footer_crypto"]
    contact = (f' · <a href="mailto:{esc(m["contact_email"])}">{t["contact"]}</a>') if m.get("contact_email") else ""
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
{links}
<link rel="alternate" type="application/rss+xml" title="{esc(s['title'])}" href="feed.xml">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="style.css">
{ads_head}
</head>
<body>
<header class="masthead">
  <div class="wrap">
    <a class="brand" href="{page_file('index', lang)}"><span class="logo" aria-hidden="true">₿</span>{esc(s['title'])}</a>
    <nav>{nav_html}<a class="lang-switch" href="{other}" hreflang="{other_lang}" lang="{other_lang}">{t['switch']}</a></nav>
  </div>
</header>
{body}
<footer class="site-footer">
  <div class="wrap">
    <p class="disclaimer">{footer}</p>
    <p>{t['footer_own']} © {datetime.now(NEPAL_TZ).year} {esc(s['title'])}{contact}</p>
  </div>
</footer>
<script src="app.js" defer></script>
</body>
</html>
"""


def story_card(it: dict, lang: str, cats: dict | None) -> str:
    t = T[lang]
    title, summary = item_text(it, lang)
    summary_html = f'<p class="summary">{esc(summary)}</p>' if summary else ""
    when = (f'<time datetime="{esc(it["published"])}">{esc(nepal_time(it["published"]))}</time>'
            if it.get("published") else "")
    pill = (f'<span class="pill pill-{esc(it["category"])}">{esc(cats.get(it["category"], it["category"]))}</span>'
            if cats else "")
    read = t["read_at"].format(src=it["source"])
    if lang == "ne" and it.get("lang") == "ne":
        read = f'{it["source"]} मा पूरा पढ्नुहोस् ↗'
    title_lang = "ne" if (lang == "ne" and it.get("title_ne")) or it.get("lang") == "ne" else "en"
    return f"""<article class="story" data-cat="{esc(it.get('category', ''))}">
  <div class="meta">{pill}<span class="source">{esc(it['source'])}</span>{when}</div>
  <h2 lang="{title_lang}"><a href="{esc(it['link'])}" target="_blank" rel="noopener nofollow">{esc(title)}</a></h2>
  {summary_html}
  <a class="read" href="{esc(it['link'])}" target="_blank" rel="noopener nofollow">{esc(read)}</a>
</article>"""


def render_index(cfg: dict, items: list[dict], built_at: datetime, lang: str) -> str:
    s, m, t = cfg["site"], cfg["monetization"], T[lang]
    cats = {c["id"]: tr(c.get("label_i18n") or {"en": c["label"]}, lang) for c in cfg["categories"]}

    tabs = [f'<button class="tab is-active" data-cat="all" aria-pressed="true">{t["all"]}</button>']
    for c in cfg["categories"]:
        n = sum(1 for i in items if i["category"] == c["id"])
        if n:
            tabs.append(f'<button class="tab" data-cat="{esc(c["id"])}" aria-pressed="false">'
                        f'{esc(cats[c["id"]])} <span class="count">{n}</span></button>')

    cards = []
    every = max(int(m.get("ad_every_n_items") or 0), 0)
    for idx, it in enumerate(items, 1):
        cards.append(story_card(it, lang, cats))
        if every and idx % every == 0 and idx != len(items):
            ad = adsense_unit(m, m.get("adsense_slot_feed", ""), "In-feed ad (Google AdSense or a direct sponsor)")
            if ad:
                cards.append(ad)
    if not cards:
        cards.append(f'<p class="empty">{t["empty"]}</p>')

    side = []
    sp = m.get("sponsor") or {}
    if sp.get("text"):
        link = f'<a href="{esc(sp.get("url"))}" target="_blank" rel="noopener sponsored">{esc(sp["text"])}</a>' \
            if sp.get("url") else esc(sp["text"])
        side.append(f'<section class="box sponsor"><h3>{t["sponsor"]}</h3><p>{link}</p></section>')
    elif os.environ.get("SHOW_AD_PLACEHOLDERS") == "1":
        side.append(f'<section class="box sponsor ad-placeholder"><h3>{t["sponsor"]}</h3><p>Your brand here. Sell this spot to a Nepali business.</p></section>')

    don = m.get("donations") or {}
    addrs = [a for a in don.get("addresses", []) if a.get("address")]
    if addrs:
        rows = "".join(
            f'<li><span class="coin">{esc(a["coin"])}</span><code>{esc(a["address"])}</code>'
            f'<button class="copy" data-copy="{esc(a["address"])}">{t["copy"]}</button></li>' for a in addrs)
        ud = don.get("unstoppable_domain")
        ud_line = f'<p class="ud">{t["or_send"].format(ud=esc(ud))}</p>' if ud else ""
        msg = don.get("message_ne") if lang == "ne" and don.get("message_ne") else don.get("message", "")
        side.append(f'<section class="box donate"><h3>{t["support"]}</h3><p>{esc(msg)}</p>'
                    f'<ul class="addresses">{rows}</ul>{ud_line}'
                    f'<p class="fine">{t["tips_outside"]}</p></section>')
    elif os.environ.get("SHOW_AD_PLACEHOLDERS") == "1":
        side.append(f'<section class="box donate ad-placeholder"><h3>{t["support"]}</h3><p>Donation addresses appear here once added to config.json.</p></section>')

    affs = [a for a in m.get("affiliate_links", []) if a.get("label") and a.get("url")]
    if affs:
        rows = "".join(
            f'<li><a href="{esc(a["url"])}" target="_blank" rel="noopener sponsored">{esc(a["label"])}</a>'
            f'{(" <span>" + esc(a["note"]) + "</span>") if a.get("note") else ""}</li>' for a in affs)
        side.append(f'<section class="box affiliates"><h3>{t["recommended"]}</h3><ul>{rows}</ul>'
                    f'<p class="fine">{t["commission"]}</p></section>')

    top_ad = adsense_unit(m, m.get("adsense_slot_top", ""), "Top banner ad (Google AdSense or a direct sponsor)")
    counts = t["stories_from"].format(n=len(items), s=len({i["source"] for i in items}))
    tagline = s.get("tagline_ne") if lang == "ne" and s.get("tagline_ne") else s["tagline"]
    machine = f'<p class="fine machine">{t["machine"]}</p>' if lang == "ne" else ""
    visa_promo = (f'<section class="box promo"><h3>{T[lang]["visa"]}</h3><p>'
                  + ("Australia visa news in Nepali and English, and a free tool to check your migration agent."
                     if lang == "en" else "नेपाली र अंग्रेजीमा अस्ट्रेलिया भिसा समाचार, र आफ्नो माइग्रेसन एजेन्ट जाँच्ने निःशुल्क उपकरण।")
                  + f'</p><p><a href="{page_file("visa", lang)}">{T[lang]["visa"]} →</a> · '
                  f'<a href="{page_file("check-agent", lang)}">{T[lang]["check"]} →</a></p></section>')

    body = f"""<main class="wrap layout">
  <div class="feed">
    <div class="intro">
      <h1>{esc(tagline)}</h1>
      <p class="updated">{t['updated']} <time datetime="{built_at.isoformat()}" data-relative>{esc(nepal_time(built_at.isoformat()))}</time> · {counts}</p>
      {machine}
    </div>
    {top_ad}
    <div class="tabs" role="toolbar" aria-label="Filter by topic">{''.join(tabs)}</div>
    <div class="stories">
{chr(10).join(cards)}
    </div>
  </div>
  <aside class="side">
    <section class="box notice"><h3>{t['news_not_advice']}</h3><p>{t['news_not_advice_p']}</p></section>
    {visa_promo}
    {''.join(side)}
  </aside>
</main>"""
    title = (f"{s['title']} | Digital currency and finance news for Nepal" if lang == "en"
             else f"{s['title']} | नेपालका लागि डिजिटल मुद्रा र वित्त समाचार")
    return page_shell(cfg, lang, "index", title, body, description=tagline)


def render_about(cfg: dict, lang: str) -> str:
    s = cfg["site"]
    sources = sorted({f["name"] for f in cfg["feeds"]} | {f["name"] for f in cfg.get("visa", {}).get("feeds", [])})
    li = "".join(f"<li>{esc(n)}</li>" for n in sources)
    if lang == "en":
        text = f"""<h1>About {esc(s['title'])}</h1>
<p>{esc(s['title'])} gathers headlines about digital currencies, blockchain, banking and the economy, with a
focus on Nepal, plus Australian visa news for the Nepali community. A script checks the sources below every hour,
keeps only stories on those topics, and shows the headline, a short summary and a link to the full article on the
publisher's site. Every page is also available in Nepali; headlines in Nepali are machine-translated.</p>
<h2>Sources we check</h2>
<ul>{li}</ul>
<h2>Disclaimer</h2>
<p>This site is for news and education only. It is not financial, legal, migration or investment advice, and it does
not offer, promote or arrange the purchase, sale, trading or mining of any cryptocurrency. Nepal Rastra Bank has
declared cryptocurrency transactions illegal in Nepal. We are not a registered migration agent and do not give
immigration assistance. Readers are responsible for following the laws where they live.</p>
<p>Every headline and summary belongs to its original publisher. If you are a publisher and want your feed removed,
contact us and we will remove it.</p>"""
    else:
        text = f"""<h1>{esc(s['title'])} बारे</h1>
<p>{esc(s['title'])} ले नेपाल केन्द्रित डिजिटल मुद्रा, ब्लकचेन, बैंकिङ र अर्थतन्त्रका शीर्षकहरू, साथै नेपाली समुदायका लागि
अस्ट्रेलियाको भिसा समाचार संकलन गर्छ। एउटा स्क्रिप्टले तलका स्रोतहरू हरेक घण्टा जाँच्छ, यी विषयका समाचार मात्र राख्छ, र
शीर्षक, छोटो सारांश र प्रकाशकको साइटमा पूरा लेखको लिंक देखाउँछ। नेपाली शीर्षकहरू स्वचालित रूपमा अनुवाद गरिएका हुन्।</p>
<h2>हामीले जाँच्ने स्रोतहरू</h2>
<ul>{li}</ul>
<h2>अस्वीकरण</h2>
<p>यो साइट समाचार र शिक्षाका लागि मात्र हो। यो वित्तीय, कानुनी, माइग्रेसन वा लगानी सल्लाह होइन, र कुनै पनि क्रिप्टोकरेन्सी
किनबेच, कारोबार वा माइनिङको प्रस्ताव, प्रचार वा व्यवस्था गर्दैन। नेपाल राष्ट्र बैंकले नेपालमा क्रिप्टोकरेन्सी कारोबार
गैरकानुनी घोषणा गरेको छ। हामी दर्ता भएको माइग्रेसन एजेन्ट होइनौं र भिसा सहयोग (immigration assistance) दिँदैनौं।</p>
<p>हरेक शीर्षक र सारांश मूल प्रकाशकको हो। प्रकाशकले आफ्नो फिड हटाउन चाहेमा सम्पर्क गर्नुहोस्, हामी हटाउनेछौं।</p>"""
    return page_shell(cfg, lang, "about", f"{T[lang]['about']} | {s['title']}",
                      f'<main class="wrap prose">{text}</main>',
                      description=f"About {s['title']} and its sources")


# --------------------------------------------------------------------------- visa section

def featured_agents_box(cfg: dict, lang: str) -> str:
    vis = cfg.get("visa", {})
    agents = [a for a in vis.get("featured_agents", []) if a.get("name") and a.get("marn")]
    if not agents:
        if os.environ.get("SHOW_AD_PLACEHOLDERS") == "1":
            return ('<section class="box ad-placeholder"><h3>Featured registered agents</h3>'
                    '<p>Paid listings for registered agents appear here (see GUIDE.md).</p></section>')
        return ""
    rows = []
    for a in agents:
        name = f'<a href="{esc(a["url"])}" target="_blank" rel="noopener sponsored">{esc(a["name"])}</a>' \
            if a.get("url") else esc(a["name"])
        extra = " · ".join(esc(x) for x in (a.get("business"), a.get("city"), a.get("languages")) if x)
        rows.append(f'<li>{name}<br><span class="fine">MARN {esc(a["marn"])}{" · " + extra if extra else ""}</span></li>')
    head = "Featured registered agents" if lang == "en" else "विशेष सूचीमा दर्ता भएका एजेन्ट"
    note = ("Paid listing. We check each MARN on the official register, but this is not a recommendation."
            if lang == "en" else "सशुल्क सूची। हामी हरेक MARN आधिकारिक रजिस्टरमा जाँच्छौं, तर यो सिफारिस होइन।")
    return f'<section class="box agents"><h3>{head}</h3><ul>{"".join(rows)}</ul><p class="fine">{note}</p></section>'


def visa_sidebar(cfg: dict, lang: str) -> str:
    vis, t = cfg.get("visa", {}), T[lang]
    if lang == "en":
        notice = ('<section class="box notice"><h3>Information, not advice</h3><p>We explain news and official rules. '
                  'We are not migration agents and cannot advise on your visa. For your own case, use a registered '
                  'migration agent or an Australian lawyer.</p></section>')
        guides = ("Guides", [("check-agent", "Check your migration agent"), ("visa-changes-2026", "What changed in 2026"),
                             ("visa-scams", "Warning signs of a visa scam")])
    else:
        notice = ('<section class="box notice"><h3>जानकारी हो, सल्लाह होइन</h3><p>हामी समाचार र आधिकारिक नियम बुझाउँछौं। '
                  'हामी माइग्रेसन एजेन्ट होइनौं र तपाईंको भिसाबारे सल्लाह दिन सक्दैनौं। आफ्नो केसका लागि दर्ता भएको '
                  'माइग्रेसन एजेन्ट वा अस्ट्रेलियाली वकिल प्रयोग गर्नुहोस्।</p></section>')
        guides = ("गाइडहरू", [("check-agent", "आफ्नो माइग्रेसन एजेन्ट जाँच्नुहोस्"), ("visa-changes-2026", "२०२६ मा के बदलियो"),
                              ("visa-scams", "भिसा ठगीका संकेतहरू")])
    links = "".join(f'<li><a href="{page_file(b, lang)}">{esc(lbl)}</a></li>' for b, lbl in guides[1])
    sp = vis.get("sponsor") or {}
    sponsor = ""
    if sp.get("text"):
        link = f'<a href="{esc(sp.get("url"))}" target="_blank" rel="noopener sponsored">{esc(sp["text"])}</a>' \
            if sp.get("url") else esc(sp["text"])
        sponsor = f'<section class="box sponsor"><h3>{t["sponsor"]}</h3><p>{link}</p></section>'
    return (f'<aside class="side">{notice}<section class="box"><h3>{guides[0]}</h3><ul class="links">{links}</ul></section>'
            f'{featured_agents_box(cfg, lang)}{sponsor}</aside>')


def render_visa(cfg: dict, items: list[dict], built_at: datetime, lang: str) -> str:
    s, m, t = cfg["site"], cfg["monetization"], T[lang]
    cards = [story_card(it, lang, None) for it in items] or [f'<p class="empty">{t["empty"]}</p>']
    latest = V.CHANGES[:3]
    facts = "".join(f'<li><strong>{esc(tr(c["date"], lang))}:</strong> {esc(c[lang])}</li>' for c in latest)
    if lang == "en":
        h1 = "Australia visa news for Nepalis"
        lead = "The latest visa and migration news that matters to Nepali students, workers and families in Australia, updated every hour."
        key = "Key changes in 2026"
        more = "See all changes and sources"
        cta = ("Using a migration agent or education consultancy? "
               f'<a href="{page_file("check-agent", lang)}">Check they are registered and spot red flags →</a>')
    else:
        h1 = "नेपालीहरूका लागि अस्ट्रेलिया भिसा समाचार"
        lead = "अस्ट्रेलियामा रहेका नेपाली विद्यार्थी, कामदार र परिवारका लागि महत्त्वपूर्ण भिसा र आप्रवासन समाचार, हरेक घण्टा अपडेट।"
        key = "२०२६ का मुख्य परिवर्तन"
        more = "सबै परिवर्तन र स्रोत हेर्नुहोस्"
        cta = ("माइग्रेसन एजेन्ट वा शैक्षिक परामर्श संस्था प्रयोग गर्दै हुनुहुन्छ? "
               f'<a href="{page_file("check-agent", lang)}">उनीहरू दर्ता भएका छन् कि छैनन् र खतराका संकेत जाँच्नुहोस् →</a>')
    machine = f'<p class="fine machine">{t["machine"]}</p>' if lang == "ne" else ""
    top_ad = adsense_unit(m, cfg.get("visa", {}).get("adsense_slot_top", ""), "Top banner ad on the visa page")
    body = f"""<main class="wrap layout">
  <div class="feed">
    <div class="intro">
      <h1>{h1}</h1>
      <p>{lead}</p>
      <p class="updated">{t['updated']} <time datetime="{built_at.isoformat()}" data-relative>{esc(nepal_time(built_at.isoformat()))}</time></p>
    </div>
    <section class="box keyfacts"><h3>{key}</h3><ul>{facts}</ul>
      <p><a href="{page_file('visa-changes-2026', lang)}">{more} →</a></p></section>
    <p class="cta">{cta}</p>
    {top_ad}
    {machine}
    <div class="stories">
{chr(10).join(cards)}
    </div>
  </div>
  {visa_sidebar(cfg, lang)}
</main>"""
    return page_shell(cfg, lang, "visa", f"{h1} | {s['title']}", body, description=lead, kind="visa")


def render_check_agent(cfg: dict, lang: str) -> str:
    s = cfg["site"]
    qs = "".join(
        f'<li><label><input type="checkbox" class="flag" data-w="{q["w"]}"> {esc(q[lang])}</label></li>'
        for q in V.CHECK_QUESTIONS)
    res = " ".join(f'data-{k}="{esc(v[lang])}"' for k, v in V.RESULTS.items())
    reports = "".join(f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r[lang])} ↗</a></li>'
                      for r in V.REPORT_LINKS)
    portal, help_url, lawyer = V.OFFICIAL["omara_portal"], V.OFFICIAL["omara_help"], V.OFFICIAL["find_lawyer_nsw"]
    if lang == "en":
        h1 = "Check your migration agent"
        lead = ("Only a registered migration agent or an Australian lawyer can legally charge to help with your visa. "
                "Check yours in two minutes before you pay.")
        step1 = f"""<h2>Step 1. Check the official register</h2>
<p>Every registered agent has a <strong>MARN</strong> (Migration Agent Registration Number). Ask for it. It should be on
their website, card and service agreement.</p>
<form class="marn" id="marn-form">
  <label for="marn">Agent's MARN</label>
  <div class="row"><input id="marn" inputmode="numeric" autocomplete="off" placeholder="e.g. 1234567" maxlength="10">
  <button type="submit">Copy and open the register ↗</button></div>
  <p class="fine" id="marn-msg" data-bad="A MARN is a number. Check the digits with the agent." data-ok="MARN copied. On the register, choose Search for a registered agent and paste it into the MARN box."></p>
</form>
<ol class="steps">
  <li>Open the <a href="{portal}" target="_blank" rel="noopener">OMARA portal ↗</a> and choose <strong>Search for a registered agent</strong>.</li>
  <li>Paste the MARN (no other fields needed) and press Search. Open the agent's name to see their details.</li>
  <li>Check the name and business match the person you are dealing with. If they are <strong>not on the register</strong>, they are not registered and cannot legally give paid immigration help in Australia.</li>
</ol>
<p class="fine">Official instructions: <a href="{help_url}" target="_blank" rel="noopener">How do I find a registered migration agent? ↗</a>.
Lawyers are not on this register; check them with the law society in their state, for example the
<a href="{lawyer}" target="_blank" rel="noopener">Law Society of NSW ↗</a>.</p>"""
        step2 = "<h2>Step 2. Tick anything that has happened</h2><p>Your answers stay in your browser. Nothing is sent to us.</p>"
        step3 = "<h2>Report a problem</h2>"
        edu = ("<h2>Education agents and consultancies</h2><p>Education agents who only help you choose a course and apply "
               "to a college do not need to be registered, but they <strong>cannot</strong> give visa advice unless they are "
               "registered migration agents. Ask your college for its list of approved agents.</p>")
        result_label = "Result"
    else:
        h1 = "आफ्नो माइग्रेसन एजेन्ट जाँच्नुहोस्"
        lead = ("दर्ता भएको माइग्रेसन एजेन्ट वा अस्ट्रेलियाली वकिलले मात्र तपाईंको भिसामा सहयोग गरेबापत कानुनी रूपमा शुल्क लिन पाउँछन्। "
                "पैसा तिर्नुअघि दुई मिनेटमै जाँच्नुहोस्।")
        step1 = f"""<h2>चरण १. आधिकारिक रजिस्टर जाँच्नुहोस्</h2>
<p>हरेक दर्ता भएको एजेन्टसँग <strong>MARN</strong> (माइग्रेसन एजेन्ट दर्ता नम्बर) हुन्छ। माग्नुहोस्। यो उनीहरूको वेबसाइट,
कार्ड र सेवा सम्झौतामा हुनुपर्छ।</p>
<form class="marn" id="marn-form">
  <label for="marn">एजेन्टको MARN</label>
  <div class="row"><input id="marn" inputmode="numeric" autocomplete="off" placeholder="जस्तै 1234567" maxlength="10">
  <button type="submit">कपी गरी रजिस्टर खोल्नुहोस् ↗</button></div>
  <p class="fine" id="marn-msg" data-bad="MARN अंकमा हुन्छ। एजेन्टसँग अंक फेरि जाँच्नुहोस्।" data-ok="MARN कपी भयो। रजिस्टरमा Search for a registered agent छानेर MARN बाकसमा पेस्ट गर्नुहोस्।"></p>
</form>
<ol class="steps">
  <li><a href="{portal}" target="_blank" rel="noopener">OMARA पोर्टल ↗</a> खोल्नुहोस् र <strong>Search for a registered agent</strong> छान्नुहोस्।</li>
  <li>MARN पेस्ट गर्नुहोस् (अरू केही भर्नु पर्दैन) र Search थिच्नुहोस्। विवरण हेर्न एजेन्टको नाममा क्लिक गर्नुहोस्।</li>
  <li>नाम र व्यवसाय तपाईंसँग काम गरिरहेको व्यक्तिसँग मिल्छ कि जाँच्नुहोस्। <strong>रजिस्टरमा छैनन् भने</strong> उनीहरू दर्ता भएका छैनन् र अस्ट्रेलियामा पैसा लिएर भिसा सहयोग गर्न कानुनी रूपमा पाउँदैनन्।</li>
</ol>
<p class="fine">आधिकारिक निर्देशन: <a href="{help_url}" target="_blank" rel="noopener">How do I find a registered migration agent? ↗</a>।
वकिलहरू यो रजिस्टरमा हुँदैनन्; उनीहरूलाई सम्बन्धित राज्यको ल सोसाइटीमा जाँच्नुहोस्, जस्तै
<a href="{lawyer}" target="_blank" rel="noopener">Law Society of NSW ↗</a>।</p>"""
        step2 = "<h2>चरण २. भएका कुरामा चिन्ह लगाउनुहोस्</h2><p>तपाईंका उत्तर तपाईंकै ब्राउजरमा रहन्छन्। हामीलाई केही पठाइँदैन।</p>"
        step3 = "<h2>उजुरी गर्नुहोस्</h2>"
        edu = ("<h2>शैक्षिक एजेन्ट र परामर्श संस्था</h2><p>कोर्स छान्न र कलेजमा भर्ना हुन मात्र सहयोग गर्ने शैक्षिक एजेन्टले दर्ता "
               "गर्नु पर्दैन, तर दर्ता भएको माइग्रेसन एजेन्ट नभई उनीहरूले भिसा सल्लाह <strong>दिन पाउँदैनन्</strong>। "
               "आफ्नो कलेजसँग स्वीकृत एजेन्टको सूची माग्नुहोस्।</p>")
        result_label = "नतिजा"
    body = f"""<main class="wrap layout">
  <div class="feed prose-in">
    <h1>{h1}</h1>
    <p class="lead">{lead}</p>
    <section class="box tool">{step1}</section>
    <section class="box tool">{step2}
      <ul class="flags" id="flags">{qs}</ul>
      <div class="result" id="result" role="status" aria-live="polite" {res}>
        <strong>{result_label}:</strong> <span id="result-text">{esc(V.RESULTS['low'][lang])}</span></div>
    </section>
    <section class="box">{step3}<ul class="links">{reports}</ul></section>
    <section class="box">{edu}</section>
  </div>
  {visa_sidebar(cfg, lang)}
</main>"""
    return page_shell(cfg, lang, "check-agent", f"{h1} | {s['title']}", body, description=lead, kind="visa")


def render_changes(cfg: dict, lang: str) -> str:
    s = cfg["site"]
    rows = "".join(
        f'<li><span class="when">{esc(tr(c["date"], lang))}</span><p>{esc(c[lang])}</p>'
        f'<p class="fine">{"Source" if lang == "en" else "स्रोत"}: <a href="{esc(c["source"][1])}" target="_blank" rel="noopener">{esc(c["source"][0])} ↗</a></p></li>'
        for c in V.CHANGES)
    tips = "".join(f"<li>{esc(x[lang])}</li>" for x in V.GENERAL_TIPS)
    official = V.OFFICIAL["policy_changes"]
    if lang == "en":
        h1, lead = "What changed for Nepali students and migrants in 2026", \
            "A plain summary of the big Australian visa changes this year, with a source for each one. Last checked 26 November 2026."
        tips_h, off = "Before you apply", f'Official list: <a href="{official}" target="_blank" rel="noopener">Australian Government migration policy changes ↗</a>'
    else:
        h1, lead = "२०२६ मा नेपाली विद्यार्थी र आप्रवासीका लागि के बदलियो", \
            "यो वर्षका अस्ट्रेलियाली भिसाका ठूला परिवर्तनको सरल सारांश, हरेकको स्रोतसहित। अन्तिम पटक २६ नोभेम्बर २०२६ मा जाँचिएको।"
        tips_h, off = "आवेदन दिनुअघि", f'आधिकारिक सूची: <a href="{official}" target="_blank" rel="noopener">Australian Government migration policy changes ↗</a>'
    body = f"""<main class="wrap layout">
  <div class="feed prose-in">
    <h1>{h1}</h1>
    <p class="lead">{lead}</p>
    <ol class="timeline">{rows}</ol>
    <p>{off}</p>
    <section class="box"><h2>{tips_h}</h2><ul>{tips}</ul></section>
  </div>
  {visa_sidebar(cfg, lang)}
</main>"""
    return page_shell(cfg, lang, "visa-changes-2026", f"{h1} | {s['title']}", body, description=lead, kind="visa")


def render_scams(cfg: dict, lang: str) -> str:
    s = cfg["site"]
    signs = "".join(f"<li>{esc(x[lang])}</li>" for x in V.SCAM_SIGNS)
    reports = "".join(f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r[lang])} ↗</a></li>'
                      for r in V.REPORT_LINKS)
    fw = V.OFFICIAL["fair_work"]
    if lang == "en":
        h1 = "Warning signs of a visa scam"
        lead = ("Fake agents often target new arrivals through social media and community groups. "
                "If you see any of these signs, stop and check before you pay.")
        rep_h, work = "Where to report", (f'Being underpaid or asked to work off the books? Visa holders have the same work '
                                          f'rights as everyone else: <a href="{fw}" target="_blank" rel="noopener">Fair Work help for visa holders ↗</a>.')
        cta = f'<a href="{page_file("check-agent", lang)}">Use the agent check tool →</a>'
    else:
        h1 = "भिसा ठगीका चेतावनी संकेतहरू"
        lead = ("नक्कली एजेन्टहरूले प्रायः सामाजिक सञ्जाल र समुदायका समूहमार्फत नयाँ आउनेहरूलाई निशाना बनाउँछन्। "
                "यीमध्ये कुनै संकेत देखेमा पैसा तिर्नुअघि रोकिएर जाँच्नुहोस्।")
        rep_h, work = "कहाँ उजुरी गर्ने", (f'कम तलब पाइरहनुभएको छ वा कागजबिना काम गर्न भनिएको छ? भिसा भएकालाई पनि अरूसरह कामको अधिकार हुन्छ: '
                                         f'<a href="{fw}" target="_blank" rel="noopener">Fair Work: भिसा भएकाहरूका लागि सहयोग ↗</a>।')
        cta = f'<a href="{page_file("check-agent", lang)}">एजेन्ट जाँच्ने उपकरण प्रयोग गर्नुहोस् →</a>'
    body = f"""<main class="wrap layout">
  <div class="feed prose-in">
    <h1>{h1}</h1>
    <p class="lead">{lead}</p>
    <section class="box"><ul class="signs">{signs}</ul><p>{cta}</p></section>
    <section class="box"><h2>{rep_h}</h2><ul class="links">{reports}</ul></section>
    <p>{work}</p>
  </div>
  {visa_sidebar(cfg, lang)}
</main>"""
    return page_shell(cfg, lang, "visa-scams", f"{h1} | {s['title']}", body, description=lead, kind="visa")


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


def render_sitemap(cfg: dict, pages: list[str]) -> str:
    base = cfg["site"].get("base_url", "").rstrip("/")
    if not base:
        return ""
    urls = "".join(f"<url><loc>{esc(base + '/' + p)}</loc></url>" for p in pages)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'


# --------------------------------------------------------------------------- main

def load_previous(cfg: dict, out: Path, name: str = "items.json") -> list[dict]:
    """Earlier stories, so the page keeps history (and translations) when a feed drops older items."""
    local = out / name
    if local.exists():
        try:
            return json.loads(local.read_text("utf-8")).get("items", [])
        except Exception:
            pass
    base = cfg["site"].get("base_url", "").rstrip("/")
    if base:
        try:
            return json.loads(fetch(f"{base}/{name}", timeout=15)).get("items", [])
        except Exception as e:
            print(f"  (no previous {name} at {base}: {e})")
    return []


def collect(label: str, feeds: list[dict], keywords: dict, previous: list[dict], s: dict,
            max_items: int) -> tuple[list[dict], list]:
    include = compile_words(keywords.get("include", []))
    exclude = compile_words(keywords.get("exclude", []))
    require = compile_words(keywords.get("require", []))
    feeds_by_name = {f["name"]: f for f in feeds}

    fresh, report = [], []
    for feed in feeds:
        if feed.get("enabled") is False:
            continue
        try:
            raw = parse_feed(fetch(feed["url"]), feed)
            kept = [i for i in raw if keep(i, feed, include, exclude, require)]
            fresh.extend(kept)
            report.append((feed["name"], len(raw), len(kept), ""))
        except Exception as e:  # one broken feed must not break the site
            report.append((feed["name"], 0, 0, f"{type(e).__name__}: {e}"))

    print(f"Feed report ({label}):")
    for name, total, kept, err in report:
        print(f"  {name:32} {'ERROR ' + err if err else f'{kept:3d} kept of {total:3d}'}")

    previous = [i for i in previous
                if keep(i, feeds_by_name.get(i.get("feed"), {"filter": True}), include, exclude, require)]
    # Translations already made for a story are kept even when the feed sends it again.
    known = {i["link"].split("#")[0]: i for i in previous}

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
        old = known.get(link)
        if old and old is not it and old.get("title_ne") and old.get("title") == it["title"]:
            it["title_ne"], it["summary_ne"] = old["title_ne"], old.get("summary_ne", "")
        if re.search("[\u0900-\u097F]", it["title"]):  # headline already in Nepali (Devanagari)
            it["lang"] = "ne"
        if it.get("lang") == "ne":
            it.setdefault("title_ne", it["title"])
        seen_links.add(link)
        seen_titles.add(tkey)
        it["summary"] = truncate(it.get("summary", ""), int(s.get("summary_chars", 240)))
        merged.append(it)

    merged.sort(key=lambda i: i.get("published") or "", reverse=True)
    return merged[:max_items], report


def build(config_path: Path, out: Path) -> dict:
    cfg = json.loads(config_path.read_text("utf-8"))
    s = cfg["site"]
    if os.environ.get("SITE_BASE_URL"):
        s["base_url"] = os.environ["SITE_BASE_URL"]
    vis = cfg.get("visa", {})

    items, report = collect("news", cfg["feeds"], cfg["keywords"], load_previous(cfg, out, "items.json"),
                            s, int(s.get("max_items", 120)))
    visa_items, visa_report = collect("visa", vis.get("feeds", []), vis.get("keywords", {}),
                                      load_previous(cfg, out, "visa-items.json"), s, int(vis.get("max_items", 60)))

    if not items and all(err for *_, err in report):
        print("Every news feed failed and there is no history; not overwriting the site.", file=sys.stderr)
        sys.exit(1)

    # Visa stories first: they matter most to the Nepali-language audience.
    tr_settings = cfg.get("translation", {})
    translated = translate.translate_items(visa_items + items, tr_settings)

    now = datetime.now(timezone.utc)
    out.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "static").iterdir():
        if f.is_file():
            shutil.copy2(f, out / f.name)
    pages = []
    for lang in LANGS:
        for base_name, html_text in (
            ("index", render_index(cfg, items, now, lang)),
            ("about", render_about(cfg, lang)),
            ("visa", render_visa(cfg, visa_items, now, lang)),
            ("check-agent", render_check_agent(cfg, lang)),
            ("visa-changes-2026", render_changes(cfg, lang)),
            ("visa-scams", render_scams(cfg, lang)),
        ):
            name = page_file(base_name, lang)
            (out / name).write_text(html_text, "utf-8")
            pages.append(name)
    (out / "feed.xml").write_text(render_rss(cfg, items, now), "utf-8")
    for name, data in (("items.json", items), ("visa-items.json", visa_items)):
        (out / name).write_text(json.dumps({"built": now.isoformat(), "items": data},
                                           ensure_ascii=False, indent=1), "utf-8")
    sitemap = render_sitemap(cfg, pages)
    robots = "User-agent: *\nAllow: /\n"
    if sitemap:
        (out / "sitemap.xml").write_text(sitemap, "utf-8")
        robots += f"Sitemap: {s['base_url'].rstrip('/')}/sitemap.xml\n"
    (out / "robots.txt").write_text(robots, "utf-8")
    (out / ".nojekyll").write_text("", "utf-8")
    client = cfg["monetization"].get("adsense_client", "").strip()
    if client:
        pub_id = client.replace("ca-", "")
        (out / "ads.txt").write_text(f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n", "utf-8")
    domain = os.environ.get("CUSTOM_DOMAIN", "").strip()
    if domain:
        (out / "CNAME").write_text(domain + "\n", "utf-8")

    have_ne = sum(1 for i in items + visa_items if i.get("title_ne"))
    print(f"Built {len(items)} news and {len(visa_items)} visa stories into {out} "
          f"({translated} newly translated, {have_ne} with Nepali text)")
    return {"items": items, "visa_items": visa_items, "report": report + visa_report}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--out", default=str(ROOT / "public"))
    args = ap.parse_args()
    build(Path(args.config), Path(args.out))


if __name__ == "__main__":
    main()
