"""Utilidades de URL de YouTube."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_PATTERNS = [
    re.compile(r"(?:v=|/v/|/embed/|/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"^([A-Za-z0-9_-]{11})$"),
]


def extract_video_id(url_or_id: str) -> str | None:
    """Devuelve el video_id de 11 chars o None si no es válido."""
    s = (url_or_id or "").strip()
    if not s:
        return None
    for pat in _PATTERNS:
        m = pat.search(s)
        if m:
            return m.group(1)
    # Intento extra vía query string (?v=...)
    try:
        qs = parse_qs(urlparse(s).query)
        v = (qs.get("v") or [""])[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", v):
            return v
    except Exception:
        pass
    return None


def is_youtube_url(url: str) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return ("youtube.com" in host or "youtu.be" in host) and extract_video_id(url) is not None


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
