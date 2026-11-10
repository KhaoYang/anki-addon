from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {
    "provider": "openai", "model": "gpt-4.1-mini", "api_key": "",
    "automatic": True, "length": "standard", "images": True,
    "references": True, "timeout": 20, "rate_seconds": 1.0,
    "ollama_url": "http://127.0.0.1:11434",
}


class Config:
    def __init__(self, directory: Path):
        self.path = directory / "settings.json"
        self.values = DEFAULTS.copy()
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.values.update({key: data[key] for key in DEFAULTS if key in data})
        except (FileNotFoundError, ValueError, OSError):
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def api_key(self) -> str:
        env = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}.get(str(self.values["provider"]))
        return (os.environ.get(env, "") if env else "") or str(self.values.get("api_key") or "")
