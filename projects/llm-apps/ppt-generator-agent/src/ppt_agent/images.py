import html
import re
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "awesome-ml-ai-projects/ppt-generator-agent (educational demo)"}


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def find_image(query: str, cache_dir: str | Path, width: int = 900) -> dict | None:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"filetype:bitmap {query}", "gsrlimit": 6,
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": width,
    }
    try:
        pages = requests.get(API, params=params, headers=HEADERS, timeout=15).json().get("query", {}).get("pages", {})
    except (requests.RequestException, ValueError):
        return None
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png") or not info.get("thumburl"):
            continue
        meta = info.get("extmetadata", {})
        author = _strip_tags(meta.get("Artist", {}).get("value", "")) or "unknown author"
        licence = _strip_tags(meta.get("LicenseShortName", {}).get("value", "")) or "see source"
        ext = ".png" if info["mime"] == "image/png" else ".jpg"
        path = Path(cache_dir) / (re.sub(r"[^A-Za-z0-9]+", "_", query).strip("_")[:40] + ext)
        try:
            r = requests.get(info["thumburl"], headers=HEADERS, timeout=30)
            r.raise_for_status()
        except requests.RequestException:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return {"path": path, "credit": f"{author[:60]} / {licence} / Wikimedia Commons", "page": info.get("descriptionurl", "")}
    return None


def fetch_images(deck, cache_dir: str | Path, every: int = 2) -> dict[int, dict]:
    out = {}
    for i, slide in enumerate(deck.content_slides()):
        if slide.image_query and i % every == 0:
            img = find_image(slide.image_query, cache_dir)
            if img:
                out[i] = img
    return out
