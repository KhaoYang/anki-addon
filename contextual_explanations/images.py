from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlencode

from .http import request_json
from .models import Artwork, ImageResult
from .parsing import plain_text


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def match_score(work: Artwork, title: str, artist: str, date: str = "", institution: str = "") -> float:
    expected = _norm(work.title)
    actual = _norm(title)
    if len(expected) < 5 or not actual:
        return 0
    if expected == actual:
        score = 0.65
    elif expected in actual:
        score = 0.55
    else:
        wanted = set(expected.split())
        overlap = len(wanted & set(actual.split())) / max(len(wanted), 1)
        if overlap < 0.9:
            return 0
        score = 0.42
    if work.artist:
        expected_artist = _norm(work.artist)
        actual_artist = _norm(artist)
        surname = expected_artist.split()[-1]
        if surname not in actual_artist.split():
            return 0
        score += 0.25
    if work.date and date:
        years = re.findall(r"\d{4}", work.date)
        candidate_years = re.findall(r"\d{4}", date)
        if years and candidate_years:
            gap = min(abs(int(a) - int(b)) for a in years for b in candidate_years)
            if gap > 75:
                return 0
            score += 0.05 if gap <= 15 else 0
    if work.institution and institution and _norm(work.institution) in _norm(institution):
        score += 0.05
    return min(score, 1.0)


def _commons(work: Artwork, timeout: float) -> list[ImageResult]:
    search = " ".join((work.title, work.artist)).strip()
    params = {"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {search}",
              "gsrnamespace": 6, "gsrlimit": 10, "prop": "imageinfo", "iiprop": "url|extmetadata",
              "iiurlwidth": 600, "format": "json", "formatversion": 2}
    data = request_json("https://commons.wikimedia.org/w/api.php?" + urlencode(params), timeout=timeout, retries=0)
    found = []
    for page in data.get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        value = lambda key: plain_text(str((meta.get(key) or {}).get("value", "")), 300)
        license_name = value("LicenseShortName") or value("UsageTerms")
        if not re.search(r"public domain|\bpd\b|cc0|cc by", license_name, re.I):
            continue
        # Commons ObjectName can contain huge machine-readable Wikidata markup.
        # File names give a cleaner signal and reveal detail crops/panels.
        title = str(page.get("title", "")).removeprefix("File:")
        if re.search(r"\b(detail|central panel|left panel|right panel|left wing|right wing|hell|paradise)\b", title, re.I):
            continue
        artist = value("Artist") or str(page.get("title", ""))
        score = match_score(work, title, artist, value("DateTimeOriginal"))
        if score < 0.8:
            continue
        url = info.get("thumburl") or info.get("url")
        if isinstance(url, str) and url.startswith("https://"):
            found.append(ImageResult(url, str(info.get("descriptionurl") or ""), "Wikimedia Commons", title,
                                     artist, license_name, value("Credit") or artist, score))
    return found


def _met(work: Artwork, timeout: float) -> list[ImageResult]:
    query = urlencode({"q": work.title, "hasImages": "true", "limit": 12})
    data = request_json("https://collectionapi.metmuseum.org/public/collection/v1.1/search?" + query, timeout=timeout, retries=0)
    found = []
    for object_id in (data.get("objectIDs") or [])[:12]:
        try:
            obj = request_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}", timeout=timeout, retries=0)
        except Exception:
            continue
        if not obj.get("isPublicDomain") or not obj.get("primaryImageSmall"):
            continue
        score = match_score(work, str(obj.get("title") or ""), str(obj.get("artistDisplayName") or ""),
                            str(obj.get("objectDate") or ""), "The Metropolitan Museum of Art")
        if score >= 0.8:
            found.append(ImageResult(str(obj["primaryImageSmall"]), str(obj.get("objectURL") or ""),
                                     "Metropolitan Museum of Art", str(obj.get("title") or ""),
                                     str(obj.get("artistDisplayName") or ""), "Public Domain",
                                     "The Metropolitan Museum of Art", score))
    return found


def _aic(work: Artwork, timeout: float) -> list[ImageResult]:
    params = {"q": work.title, "limit": 12, "fields": "id,title,artist_display,date_display,image_id,is_public_domain"}
    data = request_json("https://api.artic.edu/api/v1/artworks/search?" + urlencode(params), timeout=timeout, retries=0)
    base = str(data.get("config", {}).get("iiif_url") or "https://www.artic.edu/iiif/2").rstrip("/")
    found = []
    for obj in data.get("data", []):
        if not obj.get("is_public_domain") or not obj.get("image_id"):
            continue
        score = match_score(work, str(obj.get("title") or ""), str(obj.get("artist_display") or ""),
                            str(obj.get("date_display") or ""), "Art Institute of Chicago")
        if score >= 0.8:
            found.append(ImageResult(f"{base}/{obj['image_id']}/full/843,/0/default.jpg",
                                     f"https://www.artic.edu/artworks/{obj['id']}", "Art Institute of Chicago",
                                     str(obj.get("title") or ""), str(obj.get("artist_display") or ""),
                                     "Public Domain", "Art Institute of Chicago", score))
    return found


def find_image(work: Artwork, timeout: float = 8) -> ImageResult | None:
    if not work.title or not work.artist:
        return None
    candidates: list[ImageResult] = []
    for source in (_commons, _met, _aic):
        try:
            candidates.extend(source(work, timeout))
        except Exception:
            continue
        if candidates and max(c.score for c in candidates) >= 0.9:
            break
    return max(candidates, key=lambda c: c.score, default=None)
