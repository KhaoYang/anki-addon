from __future__ import annotations

from aqt.qt import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                    QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout)
from aqt.utils import askUser


def show_settings(parent, config, cache) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("AI Context settings")
    layout = QVBoxLayout(dialog)
    form = QFormLayout()
    layout.addLayout(form)
    provider = QComboBox()
    provider.addItems(["openai", "gemini", "ollama"])
    provider.setCurrentText(str(config.values["provider"]))
    model = QLineEdit(str(config.values["model"]))
    key = QLineEdit(str(config.values["api_key"]))
    key.setEchoMode(QLineEdit.EchoMode.Password)
    automatic = QCheckBox()
    automatic.setChecked(bool(config.values["automatic"]))
    images = QCheckBox()
    images.setChecked(bool(config.values["images"]))
    references = QCheckBox()
    references.setChecked(bool(config.values["references"]))
    length = QComboBox()
    length.addItems(["short", "standard", "detailed"])
    length.setCurrentText(str(config.values["length"]))
    timeout = QSpinBox()
    timeout.setRange(5, 120)
    timeout.setValue(int(config.values["timeout"]))
    ollama = QLineEdit(str(config.values["ollama_url"]))
    form.addRow("Provider", provider)
    form.addRow("Model", model)
    form.addRow("API key", key)
    form.addRow("Generate after reveal", automatic)
    form.addRow("Artwork images", images)
    form.addRow("Wikisource search", references)
    form.addRow("Length", length)
    form.addRow("Timeout (seconds)", timeout)
    form.addRow("Ollama URL", ollama)
    layout.addWidget(QLabel("Environment variables OPENAI_API_KEY / GEMINI_API_KEY take precedence.\nA key entered here is stored locally in plain text."))
    clear = QPushButton(f"Clear explanation cache ({cache.count()})")
    clear.clicked.connect(lambda: cache.clear() if askUser("Clear all cached explanations and images?") else None)
    layout.addWidget(clear)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        config.values.update(provider=provider.currentText(), model=model.text().strip(), api_key=key.text().strip(),
                             automatic=automatic.isChecked(), images=images.isChecked(), references=references.isChecked(),
                             length=length.currentText(), timeout=timeout.value(), ollama_url=ollama.text().strip())
        config.save()
