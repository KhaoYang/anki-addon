from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aqt import gui_hooks, mw
from aqt.qt import QAction

from .cache import Cache
from .config import Config
from .parsing import context_from_card
from .review_ui import is_current_result, panel_html, update_js
from .service import Service


class Integration:
    def __init__(self) -> None:
        directory = Path(__file__).parent / "user_files"
        self.config = Config(directory)
        self.cache = Cache(directory / "cache.sqlite3")
        self.service = Service(self.config, self.cache)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="anki-context")
        self.sequence = 0
        self.active_card = 0
        self.active_key = ""
        gui_hooks.card_will_show.append(self.card_will_show)
        gui_hooks.reviewer_did_show_question.append(self.show_question)
        gui_hooks.reviewer_did_show_answer.append(self.show_answer)
        gui_hooks.webview_did_receive_js_message.append(self.handle_message)
        settings = QAction("AI Context settings…", mw)
        settings.triggered.connect(self.show_settings)
        mw.form.menuTools.addAction(settings)
        batch = QAction("AI Context: pre-generate deck…", mw)
        batch.triggered.connect(self.show_batch)
        mw.form.menuTools.addAction(batch)

    def card_will_show(self, html: str, card, kind: str) -> str:
        return html + panel_html(card.id) if kind == "reviewAnswer" else html

    def show_question(self, card) -> None:
        self.sequence += 1
        self.active_card = 0
        self.active_key = ""

    def _snapshot(self, card):
        deck = mw.col.decks.name(card.current_deck_id()) or ""
        return context_from_card(card, deck)

    def show_answer(self, card) -> None:
        try:
            snapshot = self._snapshot(card)
            key = self.service.key(snapshot)
            self.sequence += 1
            self.active_card = card.id
            self.active_key = key
            cached = self.service.cached(snapshot)
            if cached:
                if snapshot.has_rendered_image:
                    cached.image = None
                mw.reviewer.web.eval(update_js(cached))
                if (self.config.values["images"] and not cached.image_checked and
                    not snapshot.has_rendered_image and self.service.visual(snapshot, cached)):
                    self._run(snapshot, False)
            elif self.config.values["automatic"]:
                self._run(snapshot, False)
            else:
                mw.reviewer.web.eval(update_js(message="Choose Generate to add context."))
        except Exception as exc:
            mw.reviewer.web.eval(update_js(message=f"Context unavailable: {exc}", error=True))

    def _run(self, snapshot, regenerate: bool) -> None:
        self.sequence += 1
        sequence = self.sequence
        key = self.service.key(snapshot)
        mw.reviewer.web.eval(update_js(message="Generating context…" if regenerate else "Loading context…"))
        future = self.executor.submit(self.service.create, snapshot, regenerate=regenerate)

        def completed(done):
            def on_main():
                if not is_current_result(sequence, snapshot.card_id, key, self.sequence,
                                         self.active_card, self.active_key, mw.state,
                                         mw.reviewer.state, getattr(mw.reviewer.card, "id", 0)):
                    return
                try:
                    mw.reviewer.web.eval(update_js(done.result()))
                except Exception as exc:
                    mw.reviewer.web.eval(update_js(message=f"Context unavailable: {exc}. Choose Regenerate to retry.", error=True))
            mw.taskman.run_on_main(on_main)
        future.add_done_callback(completed)

    def handle_message(self, handled, message: str, context):
        if not message.startswith("anki-context:generate:"):
            return handled
        if context is not mw.reviewer or mw.state != "review" or mw.reviewer.state != "answer":
            return (True, None)
        try:
            card_id = int(message.rsplit(":", 1)[1])
        except ValueError:
            return (True, None)
        if card_id == self.active_card == getattr(mw.reviewer.card, "id", 0):
            self._run(self._snapshot(mw.reviewer.card), True)
        return (True, None)

    def show_settings(self) -> None:
        from .settings_ui import show_settings
        show_settings(mw, self.config, self.cache)

    def show_batch(self) -> None:
        from .batch_ui import show_batch
        show_batch(mw, self.service, self.executor)


_instance: Integration | None = None


def install() -> None:
    global _instance
    if _instance is None:
        _instance = Integration()
