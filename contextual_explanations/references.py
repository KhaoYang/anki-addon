from __future__ import annotations

import re
from urllib.parse import quote, urlencode

from .http import request_json
from .models import CardContext
from .parsing import plain_text


def retrieve(card: CardContext, timeout: float = 8) -> list[dict[str, str]]:
    """Small, optional evidence search. Source snippets are not treated as verification."""
    query = card.question.strip()
    if len(query) < 12:
        return []
    # A distinctive phrase helps quote cards; limit queries to avoid huge snippets.
    words = re.findall(r"[\w']+", query)
    phrase = " ".join(words[:12])
    if len(phrase) < 12:
        return []
    endpoint = "https://en.wikisource.org/w/api.php?" + urlencode({
        "action": "query", "list": "search", "srsearch": f'"{phrase}"',
        "srlimit": 3, "format": "json", "formatversion": 2,
    })
    try:
        results = request_json(endpoint, timeout=timeout, retries=0).get("query", {}).get("search", [])
    except Exception:
        return []
    return [{"title": str(item.get("title", "")),
             "snippet": plain_text(str(item.get("snippet", "")), 500),
             "url": "https://en.wikisource.org/wiki/" + quote(str(item.get("title", "")).replace(" ", "_"))}
            for item in results if item.get("title")]
