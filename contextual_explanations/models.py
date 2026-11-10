from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CardContext:
    card_id: int
    note_id: int
    question: str
    answer: str
    fields: dict[str, str]
    deck: str = ""
    tags: tuple[str, ...] = ()
    subject: str = "unknown"
    has_rendered_image: bool = False
    content_hash: str = ""


@dataclass
class Artwork:
    title: str = ""
    artist: str = ""
    date: str = ""
    medium: str = ""
    institution: str = ""


@dataclass
class ImageResult:
    url: str
    page_url: str
    source: str
    title: str
    artist: str
    license: str
    attribution: str
    score: float = 0.0


@dataclass
class Explanation:
    explanation: str
    detected_subject: str = "unknown"
    identified_entity: str = ""
    factual_mismatch: str = ""
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    artwork: Artwork = field(default_factory=Artwork)
    image: ImageResult | None = None
    image_checked: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Explanation":
        explanation = str(value.get("explanation") or "").strip()
        if not explanation:
            raise ValueError("The model returned no explanation")
        artwork = value.get("artwork") or value.get("image_search_information") or {}
        if not isinstance(artwork, dict):
            artwork = {}
        image = value.get("image")
        try:
            confidence = max(0.0, min(1.0, float(value.get("confidence") or 0)))
        except (TypeError, ValueError):
            confidence = 0.0
        return cls(
            explanation=explanation,
            detected_subject=str(value.get("detected_subject") or "unknown"),
            identified_entity=str(value.get("identified_entity") or ""),
            factual_mismatch=str(value.get("factual_mismatch") or ""),
            confidence=confidence,
            sources=[x for x in value.get("sources", []) if isinstance(x, str) and x.startswith("https://")][:5] if isinstance(value.get("sources"), list) else [],
            artwork=Artwork(**{k: str(artwork.get(k) or "") for k in Artwork.__dataclass_fields__}),
            image=ImageResult(**image) if isinstance(image, dict) else None,
            image_checked=bool(value.get("image_checked", False)),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
