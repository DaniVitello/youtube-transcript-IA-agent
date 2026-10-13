"""Orquestador de extracción con fallback: youtube_api -> ytdlp -> whisper."""

from __future__ import annotations

from core.models import Transcript
from utils.logging import get_logger

log = get_logger()


def get_transcript_with_fallback(
    video_id: str, config: dict, max_retries: int = 1
) -> tuple[Transcript, dict]:
    t_cfg = config.get("transcript", {})
    languages = t_cfg.get("preferred_languages", ["es", "en"])
    order = t_cfg.get("fallback_order", ["youtube_api", "ytdlp", "whisper"])
    flags: dict = {}
    last_error: Exception | None = None

    for provider in order:
        try:
            if provider == "youtube_api":
                from providers import youtube_transcript as p

                t, f = p.get_transcript(video_id, languages)
            elif provider == "ytdlp":
                from providers import ytdlp as p

                t, f = p.get_transcript(video_id, languages)
            elif provider == "whisper":
                from providers import whisper as p

                t, f = p.get_transcript(
                    video_id, languages, model_name=t_cfg.get("whisper_model", "small")
                )
            else:
                continue
            flags.update(f)
            log.info(f"Transcript OK vía {provider} ({len(t.segments)} segmentos).")
            return t, flags
        except Exception as e:
            last_error = e
            log.warning(f"{provider} falló: {e}")
    raise RuntimeError(f"Sin transcript disponible (todos los providers fallaron): {last_error}")
