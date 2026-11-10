from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

from .models import CardContext, Explanation
from .prompt import PROMPT_VERSION


def cache_key(card: CardContext, provider: str, model: str, length: str, references: bool) -> str:
    data = [PROMPT_VERSION, card.card_id, card.note_id, card.question, card.answer,
            card.fields, card.deck, card.tags, card.has_rendered_image, card.content_hash,
            provider, model, length, references]
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Cache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("CREATE TABLE IF NOT EXISTS explanations (key TEXT PRIMARY KEY, card_id INTEGER, value TEXT NOT NULL)")
            self.db.commit()

    def get(self, key: str) -> Explanation | None:
        with self.lock:
            row = self.db.execute("SELECT value FROM explanations WHERE key=?", (key,)).fetchone()
        if row:
            try:
                return Explanation.from_dict(json.loads(row[0]))
            except (ValueError, TypeError, KeyError):
                return None
        return None

    def put(self, key: str, card_id: int, result: Explanation) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO explanations VALUES (?,?,?)", (key, card_id, json.dumps(result.as_dict())))
            self.db.commit()

    def delete(self, key: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM explanations WHERE key=?", (key,))
            self.db.commit()

    def clear(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM explanations")
            self.db.commit()

    def count(self) -> int:
        with self.lock:
            return int(self.db.execute("SELECT COUNT(*) FROM explanations").fetchone()[0])

    def close(self) -> None:
        with self.lock:
            self.db.close()
