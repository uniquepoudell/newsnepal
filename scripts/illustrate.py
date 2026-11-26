"""Original illustrations for stories whose publisher gave no picture.

Each picture is made once per story by a text-to-image model, saved as public/gen/<id>.jpg and reused on
later builds (it is downloaded back from the live site, so nothing is committed to the repository).

Providers, in order:
  cloudflare   Cloudflare Workers AI, FLUX.1 [schnell]. Needs the CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AI_TOKEN
               secrets. Free for about 50 to 150 pictures a day (10,000 free "neurons" daily), then
               roughly US$0.002 a picture on the paid Workers plan.
  pollinations pollinations.ai, free and needs no key, but slower and with no guarantee it stays up.

A picture that fails is simply skipped: the story keeps the branded placeholder and is tried again next build.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; NewsNepalBot/1.0; +https://uniquepoudell.github.io/newsnepal/)"

DEFAULT_STYLE = (
    "Editorial news illustration in a hand-drawn comic style: confident ink outlines, painterly cel shading, "
    "dramatic cinematic lighting, rich crimson, deep blue and warm gold colours, clean composition with one "
    "clear focal point. No text, no letters, no words, no logos, no watermarks. Generic people only, "
    "no recognisable real person."
)
SETTING = {
    "nepal": "Set in Nepal, for example Kathmandu streets, a bank hall or the Himalaya in the background.",
    "visa": "About Nepali students and workers in Australia, for example an airport, a university campus "
            "or a Sydney street.",
    "crypto": "About digital money: coins, charts, servers or a glowing network shown as objects or scenes.",
    "global": "About world markets and central banks: trading floors, city skylines, charts and currency.",
}


def story_id(link: str) -> str:
    return hashlib.sha1(link.split("#")[0].encode("utf-8")).hexdigest()[:16]


def make_prompt(it: dict, style: str = "") -> str:
    title = re.sub(r"\s+", " ", it.get("title", "")).strip()
    summary = re.sub(r"\s+", " ", it.get("summary", "")).strip()[:220]
    scene = f"News headline to illustrate: \"{title}\"."
    if summary:
        scene += f" Context: {summary}"
    setting = SETTING.get(it.get("category", ""), "")
    return f"{style or DEFAULT_STYLE} {setting} {scene}"[:1900]


def _is_image(data: bytes) -> bool:
    return len(data) > 4000 and (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
                                 or data[:4] == b"RIFF")


def cloudflare(prompt: str, seed: int, timeout: int = 60) -> bytes:
    acct, token = os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""), os.environ.get("CLOUDFLARE_AI_TOKEN", "")
    if not acct or not token:
        raise RuntimeError("no Cloudflare secrets")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    body = json.dumps({"prompt": prompt, "steps": 6, "seed": seed}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if _is_image(raw):
        return raw
    data = json.loads(raw)
    img = (data.get("result") or {}).get("image") or data.get("image")
    if not img:
        raise RuntimeError(f"no image in response: {str(data)[:200]}")
    return base64.b64decode(img)


def pollinations(prompt: str, seed: int, timeout: int = 90) -> bytes:
    q = urllib.parse.urlencode({"width": 1024, "height": 576, "seed": seed, "model": "flux",
                                "nologo": "true", "private": "true"})
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:1200], safe="") + "?" + q
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


PROVIDERS = {"cloudflare": cloudflare, "pollinations": pollinations}


def providers_for(setting: str) -> list[str]:
    if setting in PROVIDERS:
        return [setting]
    if setting == "off":
        return []
    order = []
    if os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_AI_TOKEN"):
        order.append("cloudflare")
    order.append("pollinations")
    return order


def generate(it: dict, cfg: dict) -> bytes:
    """One picture for one story, trying each provider in turn. Raises when every provider fails."""
    settings = (cfg.get("images") or {}).get("generate") or {}
    prompt = make_prompt(it, settings.get("style", ""))
    seed = int(story_id(it["link"])[:8], 16) % 2_000_000_000
    errors = []
    for name in providers_for(settings.get("provider", "auto")):
        try:
            data = PROVIDERS[name](prompt, seed)
            if _is_image(data):
                return data
            errors.append(f"{name}: not an image ({len(data)} bytes)")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
    raise RuntimeError("; ".join(errors) or "image generation is off")
