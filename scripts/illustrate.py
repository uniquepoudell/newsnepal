"""Original illustrations for stories whose publisher gave no picture.

Each picture is made once per story by a text-to-image model, saved as public/gen/<id>.jpg and reused on
later builds (it is downloaded back from the live site, so nothing is committed to the repository).

Provider: Cloudflare Workers AI, FLUX.1 [schnell]. Needs the CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AI_TOKEN
secrets. Free for about 50 to 150 pictures a day (10,000 free "neurons" daily), then roughly US$0.001 to
US$0.002 a picture on the paid Workers plan. Without the secrets no pictures are made and stories keep the
branded placeholder. (The free no-key service pollinations.ai was tried on 2026-11-26 and now answers
"402 Payment Required", so it is not used.)

A picture that fails is simply skipped: the story keeps the branded placeholder and is tried again next build.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; NewsNepalBot/1.0; +https://uniquepoudell.github.io/newsnepal/)"

# Bump when the look changes: pictures are stored as gen/<id>-v<STYLE_VERSION>.jpg, so a new version makes
# fresh pictures (a few per build) instead of reusing the old ones.
STYLE_VERSION = "2"

DEFAULT_STYLE = (
    "Bold editorial magazine illustration in a hand-drawn comic style: confident ink outlines, painterly cel "
    "shading, dramatic cinematic lighting, rich crimson, deep blue and warm gold colours, one clear focal "
    "point, symbolic and dynamic composition like the cover art of a finance news site."
)
NO_TEXT = (
    "The image contains no text at all: no letters, no words, no numbers, no captions, no banners, no signs "
    "with writing, no logos and no watermarks. Any signs or screens are blank. Generic people only, no "
    "recognisable real person, no flags with writing."
)
SETTING = {
    "nepal": "If it fits the story, add a small Nepali touch such as a pagoda roof, prayer flags or distant "
             "Himalaya, but keep the story's subject in front.",
    "visa": "About Nepali students and workers in Australia: for example a passport, a suitcase, an airport "
            "gate or a university campus.",
    "crypto": "About digital money: show glowing coins, blockchain links, charts or servers as objects.",
    "global": "About world markets and central banks: show charts, coins, banknotes, a bank building or a "
              "city skyline as objects.",
}


def story_id(link: str) -> str:
    return hashlib.sha1(link.split("#")[0].encode("utf-8")).hexdigest()[:16]


def file_name(link: str) -> str:
    return f"gen/{story_id(link)}-v{STYLE_VERSION}.jpg"


def _plain(text: str) -> str:
    """Headline text without quote marks, so the model draws the idea instead of printing the words."""
    return re.sub(r"\s+", " ", re.sub(r"[\"'‘’“”:|]", " ", text or "")).strip()


def make_prompt(it: dict, style: str = "") -> str:
    title = _plain(it.get("title", ""))
    summary = _plain(it.get("summary", ""))[:200]
    scene = (f"Subject: a symbolic scene that shows the idea of this news story, {title}."
             + (f" Background: {summary}." if summary else "")
             + " Show the idea with objects, symbols and at most one or two people, not a crowd.")
    setting = SETTING.get(it.get("category", ""), "")
    return f"{scene} {setting} {style or DEFAULT_STYLE} {NO_TEXT}"[:1900]


def shrink(data: bytes, width: int = 800, quality: int = 80) -> bytes:
    """Make the picture web sized (about 80 to 150 KB instead of about 850 KB) when Pillow is installed."""
    try:
        import io
        from PIL import Image
    except ImportError:
        return data
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        return buf.getvalue() if buf.tell() > 4000 else data
    except Exception:
        return data


def _is_image(data: bytes) -> bool:
    return len(data) > 4000 and (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
                                 or data[:4] == b"RIFF")


def cloudflare(prompt: str, timeout: int = 60) -> bytes:
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip().strip('"\'')
    token = os.environ.get("CLOUDFLARE_AI_TOKEN", "").strip().strip('"\'')
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not acct or not token:
        raise RuntimeError("no Cloudflare secrets")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    body = json.dumps({"prompt": prompt, "steps": 6}).encode()  # FLUX schnell rejects a "seed" field
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:  # show Cloudflare's own reason (never the token)
        detail = e.read()[:300].decode("utf-8", "replace")
        raise RuntimeError(f"Cloudflare HTTP {e.code}: {detail}") from None
    if _is_image(raw):
        return raw
    data = json.loads(raw)
    img = (data.get("result") or {}).get("image") or data.get("image")
    if not img:
        raise RuntimeError(f"no image in response: {str(data)[:200]}")
    return base64.b64decode(img)


PROVIDERS = {"cloudflare": cloudflare}


def providers_for(setting: str) -> list[str]:
    if setting in PROVIDERS:
        return [setting]
    if setting == "off":
        return []
    if os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_AI_TOKEN"):
        return ["cloudflare"]
    return []


def generate(it: dict, cfg: dict) -> bytes:
    """One picture for one story, trying each provider in turn. Raises when every provider fails."""
    settings = (cfg.get("images") or {}).get("generate") or {}
    prompt = make_prompt(it, settings.get("style", ""))
    errors = []
    for name in providers_for(settings.get("provider", "auto")):
        try:
            data = PROVIDERS[name](prompt)
            if _is_image(data):
                return shrink(data)
            errors.append(f"{name}: not an image ({len(data)} bytes)")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
    raise RuntimeError("; ".join(errors) or "image generation is off")
