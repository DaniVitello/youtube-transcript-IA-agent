"""Provider 1: youtube-transcript-api (rápido, sin descargar nada)."""

from __future__ import annotations

from core.models import Transcript, TranscriptSegment, VideoMetadata
from utils.logging import get_logger

log = get_logger()


def get_transcript(
    video_id: str, languages: list[str] | None = None
) -> tuple[Transcript, dict]:
    """Devuelve (Transcript, meta_flags). Compatible con v1.x y v0.x del paquete."""
    languages = languages or ["es", "en"]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as e:
        raise RuntimeError("Falta youtube-transcript-api: pip install youtube-transcript-api") from e

    raw: list[dict] = []
    used_lang = languages[0]

    # API nueva (v1.x): YouTubeTranscriptApi().fetch(video_id, languages=[...])
    # devuelve FetchedTranscript iterable de snippets (.text/.start/.duration).
    # API vieja (v0.x): YouTubeTranscriptApi.get_transcript(...) -> list[dict].
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)  # type: ignore[attr-defined]
        else:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=languages)
            used_lang = getattr(fetched, "language_code", used_lang)
            raw = [
                {"text": s.text, "start": s.start, "duration": s.duration}
                for s in fetched  # iterable de snippets, NO to_raw_data()
            ]
    except Exception as e:
        msg = str(e).lower()
        if "no transcripts" in msg or "transcriptsdisabled" in msg or "not found" in msg:
            raise RuntimeError(f"Sin captions disponibles vía API: {e}") from e
        # Reintento idioma por idioma (algunos videos solo tienen 1 idioma)
        last: Exception = e
        for lang in languages:
            try:
                if hasattr(YouTubeTranscriptApi, "get_transcript"):
                    raw = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])  # type: ignore[attr-defined]
                else:
                    fetched = YouTubeTranscriptApi().fetch(video_id, languages=[lang])
                    used_lang = getattr(fetched, "language_code", lang)
                    raw = [
                        {"text": s.text, "start": s.start, "duration": s.duration}
                        for s in fetched
                    ]
                used_lang = lang
                last = None  # type: ignore[assignment]
                break
            except Exception as e2:
                last = e2
        if not raw:
            raise RuntimeError(f"youtube-transcript-api falló: {last}") from last

    segments = [
        TranscriptSegment(
            text=r.get("text", "").replace("\n", " ").strip(),
            start=float(r.get("start", 0.0)),
            duration=float(r.get("duration", 0.0)),
        )
        for r in raw
        if r.get("text", "").strip()
    ]
    if not segments:
        raise RuntimeError("API devolvió transcript vacío.")
    t = Transcript.from_segments(segments, source="youtube_api", language=used_lang)
    return t, {"has_manual_captions": True, "language": used_lang}


def probe_flags(video_id: str, metadata: VideoMetadata) -> None:
    metadata.has_manual_captions = True
