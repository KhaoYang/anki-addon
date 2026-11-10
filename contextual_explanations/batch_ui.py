from __future__ import annotations

import threading

from aqt.qt import (QComboBox, QDialog, QHBoxLayout, QLabel, QProgressBar,
                    QPushButton, QTimer, QVBoxLayout)

from .parsing import context_from_card
from .batch import process_batch


def show_batch(mw, service, executor) -> None:
    dialog = QDialog(mw)
    dialog.setWindowTitle("Pre-generate AI Context")
    layout = QVBoxLayout(dialog)
    decks = QComboBox()
    deck_names = sorted(mw.col.decks.all_names())
    decks.addItems(deck_names)
    layout.addWidget(QLabel("Deck (including subdecks)"))
    layout.addWidget(decks)
    estimate = QLabel("Cost estimate unavailable: model prices vary. Check your provider's usage dashboard.")
    layout.addWidget(estimate)
    progress = QProgressBar()
    layout.addWidget(progress)
    status = QLabel("Choose Start to prepare cards.")
    layout.addWidget(status)
    row = QHBoxLayout()
    start = QPushButton("Start")
    cancel = QPushButton("Close")
    row.addWidget(start)
    row.addWidget(cancel)
    layout.addLayout(row)
    stop = threading.Event()
    state = {"ids": [], "snapshots": [], "index": 0, "running": False}

    def close_or_cancel():
        stop.set()
        dialog.reject()

    cancel.clicked.connect(close_or_cancel)
    dialog.rejected.connect(stop.set)

    def build_next():
        if stop.is_set():
            return
        ids = state["ids"]
        end = min(state["index"] + 50, len(ids))
        for i in range(state["index"], end):
            try:
                card = mw.col.get_card(ids[i])
                deck = mw.col.decks.name(card.current_deck_id()) or ""
                state["snapshots"].append(context_from_card(card, deck))
            except Exception:
                pass
        state["index"] = end
        progress.setValue(end)
        status.setText(f"Preparing {end}/{len(ids)} cards…")
        if end < len(ids):
            QTimer.singleShot(0, build_next)
        else:
            snapshots = state["snapshots"]
            pending = [card for card in snapshots if service.cached(card) is None]
            status.setText(f"{len(pending)} API calls estimated; {len(snapshots) - len(pending)} cached. Generating…")
            progress.setRange(0, len(pending))
            progress.setValue(0)
            executor.submit(process, pending)

    def process(cards):
        def update_progress(done, failures):
            def update(done=done, failures=failures):
                if dialog.isVisible():
                    progress.setValue(done)
                    status.setText(f"Processed {done}/{len(cards)}; {failures} failed.")
            mw.taskman.run_on_main(update)
        done, failures = process_batch(cards, service.create, stop, update_progress,
                                       float(service.config.values["rate_seconds"]))
        def finish():
            if dialog.isVisible():
                status.setText(("Cancelled. " if stop.is_set() else "Finished. ") + f"Processed {done}; {failures} failed.")
                cancel.setText("Close")
        mw.taskman.run_on_main(finish)

    def begin():
        if state["running"] or not decks.currentText():
            return
        state["running"] = True
        start.setEnabled(False)
        cancel.setText("Cancel")
        name = decks.currentText().replace('"', '\\"')
        state["ids"] = mw.col.find_cards(f'deck:"{name}"')
        progress.setRange(0, len(state["ids"]))
        QTimer.singleShot(0, build_next)

    start.clicked.connect(begin)
    dialog.exec()
