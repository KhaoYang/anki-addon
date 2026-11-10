from __future__ import annotations

import json
from urllib.parse import quote

from .http import NetworkError, request_json
from .models import Explanation
from .prompt import SYSTEM


def _parse_result(raw: str) -> Explanation:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    try:
        result = json.loads(raw)
    except ValueError as exc:
        raise NetworkError("The model did not return valid JSON") from exc
    if not isinstance(result, dict):
        raise NetworkError("The model returned an unexpected format")
    try:
        return Explanation.from_dict(result)
    except (TypeError, ValueError) as exc:
        raise NetworkError("The model returned no usable explanation") from exc


def generate(provider: str, model: str, api_key: str, prompt: str, timeout: float, ollama_url: str = "http://127.0.0.1:11434") -> Explanation:
    if not model.strip():
        raise NetworkError("Choose a model in settings")
    if provider == "openai":
        if not api_key:
            raise NetworkError("Set an OpenAI API key in settings or OPENAI_API_KEY")
        data = request_json(
            "https://api.openai.com/v1/responses",
            payload={"model": model, "instructions": SYSTEM, "input": prompt, "store": False,
                     "text": {"format": {"type": "json_object"}}},
            headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout,
        )
        parts = [part.get("text", "") for item in data.get("output", []) for part in item.get("content", []) if part.get("type") == "output_text"]
        return _parse_result("".join(parts))
    if provider == "gemini":
        if not api_key:
            raise NetworkError("Set a Gemini API key in settings or GEMINI_API_KEY")
        data = request_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent",
            payload={"systemInstruction": {"parts": [{"text": SYSTEM}]},
                     "contents": [{"parts": [{"text": prompt}]}],
                     "generationConfig": {"responseMimeType": "application/json"}},
            headers={"x-goog-api-key": api_key}, timeout=timeout,
        )
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return _parse_result("".join(str(p.get("text", "")) for p in parts))
    if provider == "ollama":
        if not ollama_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise NetworkError("Ollama URL must point to localhost")
        data = request_json(
            ollama_url.rstrip("/") + "/api/generate",
            payload={"model": model, "system": SYSTEM, "prompt": prompt, "format": "json", "stream": False},
            timeout=timeout,
        )
        return _parse_result(str(data.get("response", "")))
    raise NetworkError("Unknown provider")
