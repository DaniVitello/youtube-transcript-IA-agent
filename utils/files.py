"""Nombres de archivo seguros y helpers de paths."""

from __future__ import annotations

import re
import unicodedata

_MAX_LEN = 80
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(text: str, max_len: int = _MAX_LEN) -> str:
    """Normaliza a ASCII, quita caracteres ilegales y colapsa espacios."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = _ILLEGAL.sub("", text)
    text = re.sub(r"\s+", " ", text).strip().replace(" ", "_")
    text = re.sub(r"_+", "_", text).strip("_.")
    if len(text) > max_len:
        text = text[:max_len].rstrip("_.")
    return text or "video"


def fmt_ts(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
