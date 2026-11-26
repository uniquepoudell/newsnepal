#!/usr/bin/env python3
"""Build the News Nepal Crypto site.

Fetches the RSS/Atom feeds listed in config.json, keeps only matching stories, and writes a
static site to ./public in English and Nepali:

  index.html / index.ne.html                 crypto and finance headlines
  visa.html / visa.ne.html                   Australia visa news for Nepalis
  check-agent.html / check-agent.ne.html     "check your migration agent" tool
  visa-changes-2026(.ne).html, visa-scams(.ne).html   guides
  about.html / about.ne.html                 what the site is, plus the legal disclaimer
  support.html / support.ne.html             ways readers pay: card (Stripe), Nepal QR (eSewa/Fonepay), crypto
  img/ph-*.svg                               branded pictures for stories whose publisher gave no image
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
from urllib.parse import quote
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


# --------------------------------------------------------------------------- images

IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", re.IGNORECASE)


def clean_image_url(url: str | None) -> str:
    """Only https images are used (an http image breaks the padlock on an https site)."""
    url = html.unescape((url or "").strip())
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://") or len(url) > 1000 or any(c in url for c in ' "<>'):
        return ""
    return url


def _first_img_in_html(text: str) -> str:
    m = re.search(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", text or "", re.IGNORECASE)
    return m.group(1) if m else ""


def find_image(e, summary_html: str = "") -> str:
    """The story's own image from the feed: media:content, media:thumbnail, an image
    enclosure, or the first <img> in the summary or full content."""
    candidates: list[str] = []
    for mc in list(e.iter(f"{MEDIA}content")):
        medium, typ, url = mc.get("medium", ""), mc.get("type", ""), mc.get("url", "")
        if medium == "image" or typ.startswith("image/") or (not medium and not typ and IMG_EXT.search(url)):
            candidates.append(url)
    for mt in e.iter(f"{MEDIA}thumbnail"):
        candidates.append(mt.get("url", ""))
    for enc in e.findall("enclosure") + [l for l in e.findall(f"{ATOM}link") if l.get("rel") == "enclosure"]:
        typ, url = enc.get("type", ""), enc.get("url") or enc.get("href") or ""
        if typ.startswith("image/") or (not typ and IMG_EXT.search(url)):
            candidates.append(url)
    for path in ("description", f"{CONTENT}encoded", f"{ATOM}content", f"{ATOM}summary"):
        el = e.find(path)
        if el is not None and el.text:
            candidates.append(_first_img_in_html(el.text))
    candidates.append(_first_img_in_html(summary_html))
    for c in candidates:
        url = clean_image_url(c)
        if url:
            return url
    return ""


class _MetaImage(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:secure_url", "twitter:image", "twitter:image:src") and a.get("content"):
            self.found.setdefault(key, a["content"])


def og_image(url: str, timeout: int = 8) -> str:
    """The article's own preview image (og:image), read from the first part of its page."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if "html" not in (resp.headers.get("Content-Type") or "html"):
            return ""
        head = resp.read(300_000).decode("utf-8", "replace")
    head = head.split("</head>", 1)[0]
    parser = _MetaImage()
    try:
        parser.feed(head)
    except Exception:
        return ""
    for key in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"):
        img = clean_image_url(parser.found.get(key))
        if img:
            return img
    return ""


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
                "image": find_image(e),
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
                "image": "" if is_google else find_image(e),
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
            "image": it.get("image", ""),
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
import illustrate  # noqa: E402  (scripts/illustrate.py)

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
        "search": "Search stories", "no_match": "No stories match. Try another word or topic.",
        "support_btn": "Support", "support_h": "Support News Nepal", "image_by": "Image: {src}", "illustration": "Illustration: News Nepal (AI)",
        "support_msg": "News Nepal is free. If it helps you, a small tip keeps it running.",
        "all_ways": "All ways to support →", "crypto_tips": "Crypto tips (from outside Nepal)", "crypto": "Crypto",
        "qr_label": "In Nepal? Scan with eSewa, Khalti or any Fonepay bank app.",
        "pay_card": "Pay by card (AUD)", "stripe_note": "Secure card, Apple Pay and Google Pay checkout by Stripe.",
        "support_lead": "News Nepal is free and has no paywall. If it helps you follow Nepal's economy, remittances, visas and digital money, a small payment keeps the site running and growing.",
        "support_fine": "Payments are voluntary tips to support the site. They don't buy advice, access or any financial product.",
        "support_soon": "Support options are coming soon.",
        "markets": "Markets", "nrb_sell": "NRB sell", "mid_rate": "market rate", "theme": "Light / dark", "share": "Share",
        "updates": "Get updates", "updates_p": "Follow every new story in your feed reader.", "rss": "RSS feed",
        "skip": "Skip to stories", "footer_images": "Images belong to the publishers credited on each story.",
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
        "search": "समाचार खोज्नुहोस्", "no_match": "कुनै समाचार भेटिएन। अर्को शब्द वा विषय प्रयोग गर्नुहोस्।",
        "support_btn": "सहयोग", "support_h": "न्युज नेपाललाई सहयोग गर्नुहोस्", "image_by": "तस्बिर: {src}", "illustration": "चित्र: न्युज नेपाल (AI)",
        "support_msg": "न्युज नेपाल निःशुल्क छ। उपयोगी लागेमा सानो सहयोगले यसलाई चलाइराख्छ।",
        "all_ways": "सहयोगका सबै तरिका →", "crypto_tips": "क्रिप्टो सहयोग (नेपालबाहिरबाट मात्र)", "crypto": "क्रिप्टो",
        "qr_label": "नेपालमा हुनुहुन्छ? eSewa, Khalti वा कुनै पनि Fonepay बैंक एपबाट स्क्यान गर्नुहोस्।",
        "pay_card": "कार्डबाट तिर्नुहोस् (AUD)", "stripe_note": "Stripe मार्फत सुरक्षित कार्ड, Apple Pay र Google Pay भुक्तानी।",
        "support_lead": "न्युज नेपाल निःशुल्क छ। नेपालको अर्थतन्त्र, रेमिट्यान्स, भिसा र डिजिटल मुद्राबारे जानकारी पाउन यसले सहयोग गरेको छ भने सानो भुक्तानीले साइट चलाउन र बढाउन मद्दत गर्छ।",
        "support_fine": "भुक्तानी साइटका लागि स्वैच्छिक सहयोग हो। यसले कुनै सल्लाह, पहुँच वा वित्तीय सेवा किन्दैन।",
        "support_soon": "सहयोगका तरिका चाँडै आउँदैछन्।",
        "markets": "बजार", "nrb_sell": "राष्ट्र बैंक बिक्री", "mid_rate": "बजार दर", "theme": "उज्यालो / अँध्यारो", "share": "सेयर",
        "updates": "अपडेट पाउनुहोस्", "updates_p": "हरेक नयाँ समाचार आफ्नो फिड रिडरमा पाउनुहोस्।", "rss": "RSS फिड",
        "skip": "समाचारमा जानुहोस्", "footer_images": "तस्बिरहरू हरेक समाचारमा उल्लेख गरिएका प्रकाशकका हुन्।",
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


DEFAULT_CAT_COLORS = {"nepal": "#1d4fb8", "crypto": "#e07a00", "global": "#16915a", "visa": "#7c3aed"}
FALLBACK_COLORS = ["#c8102e", "#0e7490", "#be185d", "#4d7c0f", "#7c3aed", "#b45309"]


def cat_colors(cfg: dict) -> dict[str, str]:
    out = {}
    for n, c in enumerate(cfg.get("categories", [])):
        out[c["id"]] = c.get("color") or DEFAULT_CAT_COLORS.get(c["id"]) or FALLBACK_COLORS[n % len(FALLBACK_COLORS)]
    return out


def placeholder_svg(label: str, color: str) -> str:
    """Branded stand-in picture for stories whose publisher gave no image."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360">
<defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{esc(color)}"/>
<stop offset="1" stop-color="#111827"/></linearGradient></defs>
<rect width="640" height="360" fill="url(#b)"/>
<path d="M0 300 L120 190 L200 250 L330 120 L440 230 L520 170 L640 260 V360 H0Z" fill="#fff" opacity=".10"/>
<path d="M0 330 L150 240 L260 300 L380 210 L500 280 L640 220 V360 H0Z" fill="#fff" opacity=".08"/>
<g transform="translate(288 118) scale(1)"><rect width="64" height="64" rx="15" fill="#fff" opacity=".95"/>
<path d="M14 48 V18 L32 38 V22 L50 46" fill="none" stroke="{esc(color)}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="47" cy="19" r="5" fill="#ffd24a"/></g>
<text x="320" y="228" text-anchor="middle" font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif"
font-size="26" font-weight="700" fill="#fff">{esc(label)}</text></svg>
"""


def _nrb_rates(wanted: list[str]) -> list[dict]:
    today = datetime.now(NEPAL_TZ).date()
    url = (f"https://www.nrb.org.np/api/forex/v1/rates?page=1&per_page=5"
           f"&from={today - timedelta(days=4)}&to={today}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    days = data["data"]["payload"]
    days.sort(key=lambda d: d.get("date", ""), reverse=True)
    rates = {r["currency"]["iso3"].upper(): r for r in days[0]["rates"]}
    return [{"code": c, "unit": int(rates[c]["currency"].get("unit") or 1), "buy": float(rates[c]["buy"]),
             "sell": float(rates[c]["sell"]), "date": days[0]["date"], "src": "nrb"} for c in wanted if c in rates]


def _market_rates(wanted: list[str]) -> list[dict]:
    """Fallback: free daily mid-market rates (open.er-api.com, no key), shown as NPR per unit."""
    data = json.loads(fetch("https://open.er-api.com/v6/latest/USD", timeout=15))
    r = data["rates"]
    npr = float(r["NPR"])
    out = []
    for c in wanted:
        if c in r and float(r[c]):
            unit = 100 if c == "INR" else 1
            mid = npr / float(r[c]) * unit
            out.append({"code": c, "unit": unit, "buy": mid, "sell": mid, "date": "", "src": "market"})
    return out


def fetch_forex(cfg: dict) -> list[dict]:
    """Rupee exchange rates for the ticker: Nepal Rastra Bank first, a free market-rate API if NRB is unreachable.
    Empty on any failure, which hides that part of the strip."""
    t = cfg.get("ticker") or {}
    wanted = [c.upper() for c in t.get("forex", [])]
    if not wanted or os.environ.get("NO_FOREX") == "1":
        return []
    for name, fn in (("Nepal Rastra Bank", _nrb_rates), ("market rates", _market_rates)):
        try:
            out = fn(wanted)
            if out:
                print(f"  forex: {len(out)} rates from {name}")
                return out
        except Exception as e:
            print(f"  (forex from {name} unavailable: {type(e).__name__}: {e})")
    return []


def support_methods(m: dict) -> dict:
    sup = m.get("support") or {}
    don = m.get("donations") or {}
    return {
        "stripe": (sup.get("stripe_payment_link") or "").strip(),
        "qr": (sup.get("nepal_qr_image") or "").strip(),
        "crypto": [a for a in don.get("addresses", []) if a.get("address")],
        "cfg": sup,
        "don": don,
    }


def has_support(m: dict) -> bool:
    sm = support_methods(m)
    return bool(sm["stripe"] or sm["qr"] or sm["crypto"]) or os.environ.get("SHOW_AD_PLACEHOLDERS") == "1"


THEME_BOOT = ("<script>try{var t=localStorage.getItem('nn-theme');if(t)document.documentElement.dataset.theme=t;}"
              "catch(e){}</script>")


SHARE_ICONS = {
    "facebook": '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M14 8h3V4h-3c-2.8 0-4 1.7-4 4.3V10H7v4h3v8h4v-8h3l1-4h-4V8.6c0-.4.3-.6.6-.6z"/></svg>',
    "whatsapp": '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 0 0-8.7 15l-1.3 5 5.1-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.8s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.9 2.1c.1.2.1.4 0 .5l-.4.6-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.3 2.4 1.5.3.1.5.1.6-.1l.9-1.1c.2-.3.4-.2.7-.1l2 1c.3.1.5.2.5.3.1.2.1.6-.1 1.2z"/></svg>',
    "x": '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M17.8 3h3.1l-6.8 7.7L22 21h-6.2l-4.9-6.3L5.3 21H2.2l7.3-8.3L2 3h6.4l4.4 5.8L17.8 3zm-1.1 16.2h1.7L7.4 4.7H5.5l11.2 14.5z"/></svg>',
    "link": '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
}


def share_bar(it: dict) -> str:
    u, t = quote(it["link"], safe=""), quote(it["title"], safe="")
    return (f'<div class="share" aria-label="Share">'
            f'<a class="sh sh-fb" href="https://www.facebook.com/sharer/sharer.php?u={u}" target="_blank" rel="noopener" title="Share on Facebook">{SHARE_ICONS["facebook"]}</a>'
            f'<a class="sh sh-wa" href="https://wa.me/?text={t}%20{u}" target="_blank" rel="noopener" title="Share on WhatsApp">{SHARE_ICONS["whatsapp"]}</a>'
            f'<a class="sh sh-x" href="https://twitter.com/intent/tweet?text={t}&amp;url={u}" target="_blank" rel="noopener" title="Share on X">{SHARE_ICONS["x"]}</a>'
            f'<button class="sh sh-copy" type="button" data-share="{esc(it["link"])}" data-title="{esc(it["title"])}" title="Copy link or share">{SHARE_ICONS["link"]}</button>'
            f'</div>')


def render_ticker(cfg: dict, forex: list[dict], lang: str = "en") -> str:
    t = cfg.get("ticker") or {}
    coins = [c for c in t.get("coins", []) if c.get("id")]
    if not forex and not coins:
        return ""
    cells = []
    for r in forex:
        unit = f'{r["unit"]} ' if r["unit"] != 1 else ""
        cells.append(f'<span class="tk"><b>{esc(unit + r["code"])}</b> Rs {r["sell"]:,.2f}'
                     f'<small>{T[lang]["nrb_sell"] if r.get("src") == "nrb" else T[lang]["mid_rate"]}</small></span>')
    for c in coins:
        cells.append(f'<span class="tk tk-coin" data-coin="{esc(c["id"])}"><b>{esc(c.get("symbol", c["id"]).upper())}</b>'
                     f' <span class="px">…</span><span class="chg"></span></span>')
    note = esc(t.get("note", "Exchange rates from Nepal Rastra Bank (or market rates when NRB is unreachable). Coin prices from CoinGecko, shown as market news only."))
    vs = esc((t.get("coin_currency") or "usd").lower())
    strip = "".join(cells)
    return (f'<div class="ticker" data-vs="{vs}" title="{note}"><div class="wrap ticker-in">'
            f'<span class="tk-label">{T[lang]["markets"]}</span><div class="tk-scroll"><div class="tk-track">{strip}</div></div>'
            f'</div></div>')


def page_shell(cfg: dict, lang: str, base_name: str, title: str, body: str, *,
               description: str, kind: str = "crypto", ticker: str = "") -> str:
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
    sup = has_support(m)
    support_btn = (f'<a class="btn btn-support" href="{page_file("support", lang)}"><span aria-hidden="true">♥</span> '
                   f'{t["support_btn"]}</a>' if sup else "")
    support_link = f' · <a href="{page_file("support", lang)}">{t["support_btn"]}</a>' if sup else ""
    tagline = s.get("tagline_ne") if lang == "ne" and s.get("tagline_ne") else s["tagline"]
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="theme-color" content="#c8102e">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
{links}
<link rel="alternate" type="application/rss+xml" title="{esc(s['title'])}" href="feed.xml">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="style.css">
{THEME_BOOT}
{ads_head}
</head>
<body>
<a class="skip" href="#main">{t['skip']}</a>
<header class="masthead">
  <div class="wrap bar">
    <a class="brand" href="{page_file('index', lang)}"><img src="logo-mark.svg" width="40" height="40" alt="">
      <span class="brand-text"><span class="b1">News</span><span class="b2">Nepal</span></span></a>
    <nav class="nav">{nav_html}</nav>
    <div class="actions">
      <a class="lang-switch" href="{other}" hreflang="{other_lang}" lang="{other_lang}">{t['switch']}</a>
      <button class="icon-btn" id="theme-toggle" type="button" aria-label="{t['theme']}" title="{t['theme']}">
        <svg class="i-sun" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="12" cy="12" r="4.5" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 1.5v2.5M12 20v2.5M1.5 12H4M20 12h2.5M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8"/></g></svg>
        <svg class="i-moon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>
      </button>
      {support_btn}
    </div>
  </div>
  <div class="flagline" aria-hidden="true"></div>
  {ticker}
</header>
{body}
<footer class="site-footer">
  <div class="wrap foot">
    <div class="foot-brand"><img src="logo.svg" width="150" height="32" alt="News Nepal" class="foot-logo">
      <p>{esc(tagline)}</p></div>
    <div>
    <p class="disclaimer">{footer}</p>
    <p>{t['footer_own']} {t['footer_images']} © {datetime.now(NEPAL_TZ).year} {esc(s['title'])}{support_link}{contact}</p>
    </div>
  </div>
</footer>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script src="app.js" defer></script>
</body>
</html>
"""


def story_card(it: dict, lang: str, cats: dict | None, *, hero: bool = False, colors: dict | None = None) -> str:
    t = T[lang]
    title, summary = item_text(it, lang)
    cat = it.get("category", "")
    color = (colors or {}).get(cat) or DEFAULT_CAT_COLORS.get(cat, "#64748b")
    ph = f"img/ph-{cat}.svg" if cat else "img/ph-visa.svg"
    img = it.get("image") or ""
    credit = esc(t["image_by"].format(src=it["source"]))
    if not img and it.get("gen"):
        img, credit = it["gen"], esc(t["illustration"])
    if img:
        pic = (f'<img class="thumb" src="{esc(img)}" alt="" loading="{"eager" if hero else "lazy"}" decoding="async" '
               f'referrerpolicy="no-referrer" onerror="this.onerror=null;this.src=\'{ph}\';this.nextElementSibling.hidden=true">'
               f'<span class="credit">{credit}</span>')
    else:
        pic = f'<img class="thumb" src="{ph}" alt="" loading="lazy" decoding="async"><span class="credit" hidden></span>'
    summary_html = f'<p class="summary">{esc(summary)}</p>' if summary else ""
    when = (f'<time datetime="{esc(it["published"])}" data-relative>{esc(nepal_time(it["published"]))}</time>'
            if it.get("published") else "")
    pill = f'<span class="pill">{esc(cats.get(cat, cat))}</span>' if cats else ""
    read = t["read_at"].format(src=it["source"]).replace(" ↗", "")
    if lang == "ne" and it.get("lang") == "ne":
        read = f'{it["source"]} मा पूरा पढ्नुहोस्'
    title_lang = "ne" if (lang == "ne" and it.get("title_ne")) or it.get("lang") == "ne" else "en"
    search = esc(f'{title} {summary} {it["title"]} {it["source"]}'.lower())
    link = esc(it["link"])
    return f"""<article class="story{' hero' if hero else ''}" data-cat="{esc(cat)}" data-q="{search}" style="--c:{esc(color)}">
  <a class="pic" href="{link}" target="_blank" rel="noopener nofollow" tabindex="-1" aria-hidden="true">{pic}</a>
  <div class="body">
    <div class="meta">{pill}<span class="source">{esc(it['source'])}</span>{when}</div>
    <h2 lang="{title_lang}"><a href="{link}" target="_blank" rel="noopener nofollow">{esc(title)}</a></h2>
    {summary_html}
    <div class="foot-row"><a class="read" href="{link}" target="_blank" rel="noopener nofollow">{esc(read)} <span aria-hidden="true">→</span></a>
    {share_bar(dict(it, title=title))}</div>
  </div>
</article>"""


def support_box(cfg: dict, lang: str, *, compact: bool) -> str:
    """Ways to pay: card (Stripe Payment Link, AUD), Nepal QR (eSewa / Khalti / Fonepay), crypto."""
    t = T[lang]
    m = cfg["monetization"]
    sm = support_methods(m)
    sup, don = sm["cfg"], sm["don"]
    # Nepali pages use the *_ne text when given, else the built-in Nepali wording (not the English text).
    pick = lambda key, default: (sup.get(key + "_ne") if lang == "ne" else sup.get(key)) or default
    show_ph = os.environ.get("SHOW_AD_PLACEHOLDERS") == "1"
    parts = []
    if sm["stripe"]:
        parts.append(f'<a class="btn btn-pay" href="{esc(sm["stripe"])}" target="_blank" rel="noopener">'
                     f'{esc(pick("stripe_button_text", t["pay_card"]))}</a>'
                     f'<p class="fine">{esc(pick("stripe_note", t["stripe_note"]))}</p>')
    elif show_ph:
        parts.append('<span class="btn btn-pay is-placeholder">Pay by card (AUD): add your Stripe link</span>')
    if sm["qr"]:
        name = f'<br><strong>{esc(sup["nepal_account_name"])}</strong>' if sup.get("nepal_account_name") else ""
        parts.append(f'<div class="qr"><img src="{esc(sm["qr"])}" alt="Payment QR code" width="180" height="180" loading="lazy">'
                     f'<p>{esc(pick("nepal_qr_label", t["qr_label"]))}{name}</p></div>')
    elif show_ph:
        parts.append('<div class="qr is-placeholder"><span>Your eSewa / Fonepay QR</span></div>')
    if sm["crypto"] and not compact:
        rows = "".join(
            f'<li><span class="coin">{esc(a["coin"])}</span><code>{esc(a["address"])}</code>'
            f'<button class="copy" type="button" data-copy="{esc(a["address"])}">{t["copy"]}</button></li>' for a in sm["crypto"])
        ud = don.get("unstoppable_domain")
        ud_line = f'<p class="ud">{t["or_send"].format(ud=esc(ud))}</p>' if ud else ""
        parts.append(f'<h4>{t["crypto"]}</h4><ul class="addresses">{rows}</ul>{ud_line}'
                     f'<p class="fine">{t["tips_outside"]}</p>')
    elif sm["crypto"]:
        parts.append(f'<p class="fine"><a href="{page_file("support", lang)}">{t["crypto_tips"]}</a></p>')
    if not parts:
        return ""
    msg = pick("message", t["support_msg"])
    more = '' if not compact else f'<a class="more" href="{page_file("support", lang)}">{t["all_ways"]}</a>'
    return (f'<section class="box support-box"><h3>{t["support_h"]}</h3><p>{esc(msg)}</p>'
            f'{"".join(parts)}{more}</section>')


def render_support(cfg: dict, lang: str) -> str:
    s, t = cfg["site"], T[lang]
    box = support_box(cfg, lang, compact=False) or f'<p>{t["support_soon"]}</p>'
    body = f"""<main id="main" class="wrap prose support-page">
<h1>{t['support_h']}</h1>
<p>{t['support_lead']}</p>
{box}
<p class="fine">{t['support_fine']}</p>
</main>"""
    return page_shell(cfg, lang, "support", f"{t['support_h']} | {s['title']}", body, description=t["support_lead"])


def render_index(cfg: dict, items: list[dict], built_at: datetime, lang: str, forex: list[dict] | None = None) -> str:
    s, m, t = cfg["site"], cfg["monetization"], T[lang]
    cats = {c["id"]: tr(c.get("label_i18n") or {"en": c["label"]}, lang) for c in cfg["categories"]}
    colors = cat_colors(cfg)

    chips = [f'<button class="chip is-active" type="button" data-cat="all" aria-pressed="true">{t["all"]} '
             f'<span class="count">{len(items)}</span></button>']
    for c in cfg["categories"]:
        n = sum(1 for i in items if i["category"] == c["id"])
        if n:
            chips.append(f'<button class="chip" type="button" data-cat="{esc(c["id"])}" aria-pressed="false" '
                         f'style="--c:{esc(colors[c["id"]])}">{esc(cats[c["id"]])} <span class="count">{n}</span></button>')

    hero_idx = next((n for n, i in enumerate(items[:6]) if i.get("image")), 0 if items else None)
    hero = story_card(items[hero_idx], lang, cats, hero=True, colors=colors) if hero_idx is not None else ""
    rest = [it for n, it in enumerate(items) if n != hero_idx]

    cards = []
    every = max(int(m.get("ad_every_n_items") or 0), 0)
    for idx, it in enumerate(rest, 1):
        cards.append(story_card(it, lang, cats, colors=colors))
        if every and idx % every == 0 and idx != len(rest):
            ad = adsense_unit(m, m.get("adsense_slot_feed", ""), "In-feed ad (Google AdSense or a direct sponsor)")
            if ad:
                cards.append(ad)
    if not items:
        cards.append(f'<p class="empty">{t["empty"]}</p>')

    side = []
    sb = support_box(cfg, lang, compact=True)
    if sb:
        side.append(sb)
    sp = m.get("sponsor") or {}
    if sp.get("text"):
        link = f'<a href="{esc(sp.get("url"))}" target="_blank" rel="noopener sponsored">{esc(sp["text"])}</a>' \
            if sp.get("url") else esc(sp["text"])
        side.append(f'<section class="box sponsor"><h3>{t["sponsor"]}</h3><p>{link}</p></section>')
    elif os.environ.get("SHOW_AD_PLACEHOLDERS") == "1":
        side.append(f'<section class="box sponsor ad-placeholder"><h3>{t["sponsor"]}</h3><p>Your brand here. Sell this spot to a Nepali business.</p></section>')

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
    visa_promo = (f'<section class="box promo"><h3>{t["visa"]}</h3><p>'
                  + ("Australia visa news in Nepali and English, and a free tool to check your migration agent."
                     if lang == "en" else "नेपाली र अंग्रेजीमा अस्ट्रेलिया भिसा समाचार, र आफ्नो माइग्रेसन एजेन्ट जाँच्ने निःशुल्क उपकरण।")
                  + f'</p><p><a href="{page_file("visa", lang)}">{t["visa"]} →</a> · '
                  f'<a href="{page_file("check-agent", lang)}">{t["check"]} →</a></p></section>')

    body = f"""<main id="main" class="wrap">
  <section class="intro">
    <div>
      <h1>{esc(tagline)}</h1>
      <p class="updated"><span class="live-dot" aria-hidden="true"></span>{t['updated']} <time datetime="{built_at.isoformat()}" data-relative>{esc(nepal_time(built_at.isoformat()))}</time> · {counts}</p>
      {machine}
    </div>
  </section>
  {top_ad}
  <div class="toolbar">
    <div class="chips" role="toolbar" aria-label="Filter by topic">{''.join(chips)}</div>
    <label class="search"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="M20 20l-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <input type="search" id="q" placeholder="{t['search']}" aria-label="{t['search']}" autocomplete="off"></label>
  </div>
  <div class="layout">
    <div class="feed">
      {hero}
      <div class="stories">
{chr(10).join(cards)}
      </div>
      <p class="empty no-match" hidden>{t['no_match']}</p>
    </div>
    <aside class="side">
      <section class="box notice"><h3>{t['news_not_advice']}</h3><p>{t['news_not_advice_p']}</p></section>
      {visa_promo}
      {''.join(side)}
      <section class="box follow"><h3>{t['updates']}</h3><p>{t['updates_p']}</p>
      <a class="btn btn-ghost" href="feed.xml">{t['rss']}</a></section>
    </aside>
  </div>
</main>"""
    title = (f"{s['title']} | Digital currency and finance news for Nepal" if lang == "en"
             else f"{s['title']} | नेपालका लागि डिजिटल मुद्रा र वित्त समाचार")
    return page_shell(cfg, lang, "index", title, body, description=tagline,
                      ticker=render_ticker(cfg, forex or [], lang))


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
                      f'<main id="main" class="wrap prose">{text}</main>',
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
            f'{featured_agents_box(cfg, lang)}{support_box(cfg, lang, compact=True)}{sponsor}</aside>')


def render_visa(cfg: dict, items: list[dict], built_at: datetime, lang: str) -> str:
    s, m, t = cfg["site"], cfg["monetization"], T[lang]
    cards = [story_card(it, lang, None, colors={"visa": DEFAULT_CAT_COLORS["visa"]}) for it in items] or [f'<p class="empty">{t["empty"]}</p>']
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
    body = f"""<main id="main" class="wrap layout">
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
    body = f"""<main id="main" class="wrap layout">
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
    body = f"""<main id="main" class="wrap layout">
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
    body = f"""<main id="main" class="wrap layout">
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
            max_items: int, max_age_days: int | None = None) -> tuple[list[dict], list]:
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
            # Some sources are always about Australia (SBS Nepali), so they skip the "require" check.
            req = None if feed.get("skip_require") else require
            kept = [i for i in raw if keep(i, feed, include, exclude, req)]
            fresh.extend(kept)
            report.append((feed["name"], len(raw), len(kept), ""))
        except Exception as e:  # one broken feed must not break the site
            report.append((feed["name"], 0, 0, f"{type(e).__name__}: {e}"))

    print(f"Feed report ({label}):")
    for name, total, kept, err in report:
        print(f"  {name:32} {'ERROR ' + err if err else f'{kept:3d} kept of {total:3d}'}")

    def _req(i):
        return None if feeds_by_name.get(i.get("feed"), {}).get("skip_require") else require
    previous = [i for i in previous
                if keep(i, feeds_by_name.get(i.get("feed"), {"filter": True}), include, exclude, _req(i))]
    # Translations already made for a story are kept even when the feed sends it again.
    known = {i["link"].split("#")[0]: i for i in previous}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(max_age_days or s.get("max_age_days", 10)))
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
        if old and old is not it and not it.get("image") and (old.get("image") or old.get("image_checked")):
            it["image"], it["image_checked"] = old.get("image", ""), old.get("image_checked", False)
        if old and old is not it and old.get("gen") and not it.get("gen"):
            it["gen"] = old["gen"]
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


def enrich_images(cfg: dict, items: list[dict]) -> None:
    """For stories whose feed had no picture, read the article's own og:image (a few per build)."""
    limit = int((cfg.get("images") or {}).get("og_lookups_per_build", 30))
    if os.environ.get("NO_OG_LOOKUPS") == "1":
        limit = 0
    done = 0
    for it in items:
        if done >= limit:
            break
        if it.get("image") or it.get("image_checked") or "news.google.com" in it["link"]:
            continue
        it["image_checked"] = True
        done += 1
        try:
            it["image"] = og_image(it["link"])
        except Exception:
            it["image"] = ""
    print(f"  images: looked up {done} article pages; {sum(1 for i in items if i.get('image'))} of {len(items)} stories have a picture")


def illustrate_items(cfg: dict, items: list[dict], out: Path) -> None:
    """Give stories without a publisher picture an original AI illustration (see scripts/illustrate.py).
    Each is made once; later builds download it back from the live site instead of making it again."""
    settings = (cfg.get("images") or {}).get("generate") or {}
    if not settings.get("enabled", False) or os.environ.get("NO_IMAGE_GEN") == "1":
        return
    if not illustrate.providers_for(settings.get("provider", "auto")):
        print("  illustrations: off (add the CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AI_TOKEN secrets, see GUIDE.md Part 8)")
        return
    budget = int(settings.get("per_build", 6))
    base = cfg["site"].get("base_url", "").rstrip("/")
    (out / "gen").mkdir(parents=True, exist_ok=True)
    made = reused = failed = 0
    first_error = ""
    for it in items:
        if it.get("image"):
            continue
        name = f"gen/{illustrate.story_id(it['link'])}.jpg"
        path = out / name
        if path.exists():
            it["gen"] = name
            continue
        if it.get("gen") and base:
            try:
                req = urllib.request.Request(f"{base}/{name}", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = resp.read()
                if len(data) > 4000:
                    path.write_bytes(data)
                    it["gen"] = name
                    reused += 1
                    continue
            except Exception:
                pass
        it.pop("gen", None)
        if budget <= 0:
            continue
        budget -= 1
        try:
            path.write_bytes(illustrate.generate(it, cfg))
            it["gen"] = name
            made += 1
        except Exception as e:
            failed += 1
            first_error = first_error or str(e)
    print(f"  illustrations: {made} new, {reused} reused, {failed} failed"
          + (f" (first error: {first_error[:300]})" if first_error else ""))


def write_placeholders(cfg: dict, out: Path) -> None:
    (out / "img").mkdir(exist_ok=True)
    colors = cat_colors(cfg)
    for c in cfg.get("categories", []):
        (out / "img" / f"ph-{c['id']}.svg").write_text(placeholder_svg(c["label"], colors[c["id"]]), "utf-8")
    (out / "img" / "ph-visa.svg").write_text(placeholder_svg("Australia visa", DEFAULT_CAT_COLORS["visa"]), "utf-8")


def build(config_path: Path, out: Path) -> dict:
    cfg = json.loads(config_path.read_text("utf-8"))
    s = cfg["site"]
    if os.environ.get("SITE_BASE_URL"):
        s["base_url"] = os.environ["SITE_BASE_URL"]
    vis = cfg.get("visa", {})

    items, report = collect("news", cfg["feeds"], cfg["keywords"], load_previous(cfg, out, "items.json"),
                            s, int(s.get("max_items", 120)))
    visa_items, visa_report = collect("visa", vis.get("feeds", []), vis.get("keywords", {}),
                                      load_previous(cfg, out, "visa-items.json"), s, int(vis.get("max_items", 60)),
                                      int(vis.get("max_age_days", 45)))

    if not items and all(err for *_, err in report):
        print("Every news feed failed and there is no history; not overwriting the site.", file=sys.stderr)
        sys.exit(1)

    enrich_images(cfg, items + visa_items)

    # Visa stories first: they matter most to the Nepali-language audience.
    tr_settings = cfg.get("translation", {})
    translated = translate.translate_items(visa_items + items, tr_settings)

    now = datetime.now(timezone.utc)
    out.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "static").iterdir():
        if f.is_file():
            shutil.copy2(f, out / f.name)
    write_placeholders(cfg, out)
    illustrate_items(cfg, items + visa_items, out)
    forex = fetch_forex(cfg)
    pages = []
    for lang in LANGS:
        for base_name, html_text in (
            ("index", render_index(cfg, items, now, lang, forex)),
            ("support", render_support(cfg, lang)),
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
