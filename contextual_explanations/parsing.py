from __future__ import annotations

import html
import hashlib
import json
import re
from html.parser import HTMLParser


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script"):
            self.suppressed += 1
        if tag in ("br", "p", "div", "li", "tr"):
            self.parts.append("\n")
        if tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.parts.append(" " + alt + " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script") and self.suppressed:
            self.suppressed -= 1
        if tag in ("p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data)


def plain_text(raw: str, limit: int = 5000) -> str:
    raw = re.sub(r"\[sound:[^]]+\]", " ", raw or "", flags=re.I)
    raw = re.sub(r"\{\{c\d+::(.*?)(?:::(.*?))?\}\}", lambda m: m.group(1) or m.group(2) or "", raw, flags=re.S)
    parser = _Text()
    parser.feed(raw)
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:limit]


def has_image(raw: str) -> bool:
    return bool(re.search(r"<img\b|\[anki:img\]|\.(?:png|jpe?g|gif|webp)[\"']", raw or "", re.I))


def detect_subject(question: str, answer: str, deck: str, tags: tuple[str, ...]) -> str:
    text = " ".join((question, answer, deck, " ".join(tags))).lower()
    matches = {
        "visual arts": r"\b(painting|painter|sculpture|sculptor|fresco|mosaic|architecture|architect|canvas|artwork|triptych|altarpiece|museum|bosch|vermeer)\b",
        "literature": r"\b(poem|poet|novel|playwright|stanza|speaker|narrator|literature)\b",
        "music": r"\b(opera|symphony|composer|sonata|concerto|aria)\b",
        "philosophy": r"\b(philosopher|philosophy|argument|epistemology)\b",
        "mythology": r"\b(myth|mythology|zeus|odin|hades)\b",
        "history": r"\b(history|historical|revolution|war|emperor|treaty)\b",
        "science": r"\b(physics|chemistry|biology|theorem|experiment)\b",
    }
    return next((name for name, pattern in matches.items() if re.search(pattern, text)), "unknown")


def context_from_card(card: object, deck: str) -> "CardContext":
    from .models import CardContext

    note = card.note()
    raw_fields = list(note.items())
    fields = {name: plain_text(value, 1200) for name, value in raw_fields if plain_text(value, 1200)}
    question_html = card.question()
    answer_html = card.answer()
    question = plain_text(question_html)
    answer = plain_text(answer_html)
    if answer.startswith(question) and len(answer) > len(question):
        answer = answer[len(question):].strip()
    tags = tuple(note.tags)
    return CardContext(
        card_id=int(card.id), note_id=int(note.id), question=question, answer=answer,
        fields=fields, deck=deck, tags=tags,
        subject=detect_subject(question, answer, deck, tags),
        has_rendered_image=has_image(question_html) or has_image(answer_html),
        content_hash=hashlib.sha256(json.dumps([question_html, answer_html, raw_fields], ensure_ascii=False).encode()).hexdigest(),
    )
