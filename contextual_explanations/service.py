from __future__ import annotations

import threading
import time

from .cache import Cache, cache_key
from .config import Config
from .images import find_image
from .models import CardContext, Explanation
from .prompt import build_prompt
from .providers import generate
from .references import retrieve


class Service:
    def __init__(self, config: Config, cache: Cache):
        self.config = config
        self.cache = cache
        self.rate_lock = threading.Lock()
        self.last_request = 0.0
        self.key_locks = [threading.Lock() for _ in range(64)]

    @staticmethod
    def visual(card: CardContext, result: Explanation) -> bool:
        label = (card.subject + " " + result.detected_subject).lower()
        return any(word in label for word in ("visual", "painting", "sculpture", "architecture", "art history"))

    def key(self, card: CardContext) -> str:
        options = self.config.values
        return cache_key(card, str(options["provider"]), str(options["model"]), str(options["length"]), bool(options["references"]))

    def cached(self, card: CardContext) -> Explanation | None:
        return self.cache.get(self.key(card))

    def create(self, card: CardContext, *, regenerate: bool = False) -> Explanation:
        if not card.question and not card.answer:
            raise ValueError("This card has no readable question or answer")
        key = self.key(card)
        with self.key_locks[int(key[:4], 16) % len(self.key_locks)]:
            return self._create_locked(card, key, regenerate)

    def _create_locked(self, card: CardContext, key: str, regenerate: bool) -> Explanation:
        if not regenerate:
            existing = self.cache.get(key)
            if existing and (not self.config.values["images"] or existing.image_checked or card.has_rendered_image or not self.visual(card, existing)):
                return existing
        else:
            existing = None
        options = self.config.values.copy()
        if existing is None:
            references = retrieve(card, min(float(options["timeout"]), 8)) if options["references"] else []
            with self.rate_lock:
                delay = float(options["rate_seconds"]) - (time.monotonic() - self.last_request)
                if delay > 0:
                    time.sleep(delay)
                self.last_request = time.monotonic()
            result = generate(str(options["provider"]), str(options["model"]), self.config.api_key(),
                              build_prompt(card, str(options["length"]), references), float(options["timeout"]),
                              str(options["ollama_url"]))
            # Only expose retrieved URLs. The model cannot certify its own citations.
            result.sources = [ref["url"] for ref in references if ref["url"] in result.sources]
        else:
            result = existing
        if options["images"] and not card.has_rendered_image and self.visual(card, result):
            result.image = find_image(result.artwork, min(float(options["timeout"]), 8))
            result.image_checked = True
        self.cache.put(key, card.card_id, result)
        return result
