"""Cliente LLM unificado: Groq o Google Gemini (REST, sin dependencias extra).

Se elige con `llm.provider` en config.yaml:
  provider: "gemini"  -> usa GOOGLE_API_KEY (o GEMINI_API_KEY), modelo gemini-2.0-flash
  provider: "groq"    -> usa GROQ_API_KEY, modelo openai/gpt-oss-120b
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class MissingKeyError(RuntimeError):
    pass


class GroqClient:
    provider = "groq"

    def __init__(
        self,
        model: str = "openai/gpt-oss-120b",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: int = 60,
    ) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", model).strip() or model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _require_key(self) -> None:
        if not self.api_key:
            raise MissingKeyError(
                "Falta GROQ_API_KEY. Agregala en el archivo .env "
                "(gratis en https://console.groq.com/keys)."
            )

    def chat(
        self,
        prompt: str,
        system: str = "Sos un asistente experto que responde en español.",
        json_mode: bool = False,
    ) -> str:
        self._require_key()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        r = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

    def chat_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        raw = self.chat(prompt, system or "Respondé SOLO con JSON válido.", json_mode=True)
        return _strip_json(raw)


class GeminiClient:
    provider = "gemini"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: int = 60,
    ) -> None:
        self.api_key = (
            os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        ).strip()
        self.model = os.getenv("GEMINI_MODEL", model).strip() or model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _require_key(self) -> None:
        if not self.api_key:
            raise MissingKeyError(
                "Falta GOOGLE_API_KEY. Agregala en el archivo .env "
                "(se crea en https://aistudio.google.com/apikey)."
            )

    def chat(
        self,
        prompt: str,
        system: str = "Sos un asistente experto que responde en español.",
        json_mode: bool = False,
    ) -> str:
        self._require_key()
        url = f"{GEMINI_BASE}/{self.model}:generateContent"
        body: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        r = requests.post(url, params={"key": self.api_key}, json=body, timeout=self.timeout)
        if r.status_code in (400, 403):
            raise RuntimeError(
                f"Gemini rechazó el pedido ({r.status_code}): {r.text[:300]}. "
                "Revisá que la key sea válida y que 'Generative Language API' esté habilitada."
            )
        r.raise_for_status()
        data = r.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Respuesta inesperada de Gemini: {str(data)[:300]}") from e

    def chat_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        raw = self.chat(prompt, system or "Respondé SOLO con JSON válido.", json_mode=True)
        return _strip_json(raw)


def _strip_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned)


def make_client(llm_cfg: dict[str, Any] | None = None):
    cfg = llm_cfg or {}
    provider = str(cfg.get("provider", "gemini")).lower()
    kwargs = {
        "temperature": float(cfg.get("temperature", 0.2)),
        "max_tokens": int(cfg.get("max_tokens", 2048)),
        "timeout": int(cfg.get("timeout_seconds", 60)),
    }
    if provider == "groq":
        return GroqClient(model=cfg.get("model", "openai/gpt-oss-120b"), **kwargs)
    return GeminiClient(model=cfg.get("model", "gemini-2.0-flash"), **kwargs)


def youtube_api_key() -> str:
    """La misma key de Google sirve para YouTube Data API si el servicio está activo."""
    return (
        os.getenv("YOUTUBE_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    ).strip()
