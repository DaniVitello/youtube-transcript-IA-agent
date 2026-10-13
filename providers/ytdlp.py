"""Provider 2: yt-dlp (metadata + subtítulos auto/manuales sin descargar video)."""

from __future__ import annotations

import re

from core.models import Transcript, TranscriptSegment, VideoMetadata
from utils.logging import get_logger
from utils.url import watch_url

log = get_logger()

_VTT_TS = re.compile(r"(\d{2,}):(\d{2}):(\d{2})[.,](\d{3})")


def _ts_to_seconds(ts: str) -> float:
    h, m, s, ms = _VTT_TS.match(ts).groups()  # type: ignore[union-attr]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_vtt(content: str) -> list[TranscriptSegment]:
    """Parsea un .vtt / .srt básico a segmentos (quita tags y duplicados)."""
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    # Quitar tags tipo <c>, <00:00:00.000>, [Música]
    text = re.sub(r"<[^>]+>", "", text)
    blocks = re.split(r"\n\s*\n", text)
    segments: list[TranscriptSegment] = []
    last_text = ""
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        # Buscar línea de tiempos
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            continue
        times = lines[idx].split("-->")
        try:
            start = _ts_to_seconds(times[0].strip().split(" ")[0])
        except Exception:
            continue
        body = " ".join(lines[idx + 1:]).strip()
        body = re.sub(r"\s+", " ", body)
        if not body or body == last_text:
            continue
        last_text = body
        segments.append(TranscriptSegment(text=body, start=start, duration=0.0))
    # Durations derivadas del siguiente inicio
    for i, seg in enumerate(segments):
        if i + 1 < len(segments):
            seg.duration = max(0.5, segments[i + 1].start - seg.start)
        else:
            seg.duration = 3.0
    return segments


def fetch_metadata(video_id: str) -> VideoMetadata:
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("Falta yt-dlp: pip install yt-dlp") from e
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
        info = ydl.extract_info(watch_url(video_id), download=False) or {}
    return VideoMetadata(
        video_id=video_id,
        url=watch_url(video_id),
        title=(info.get("title") or "").strip(),
        channel=(info.get("channel") or info.get("uploader") or "").strip(),
        channel_id=(info.get("channel_id") or "").strip(),
        duration_seconds=int(info.get("duration") or 0),
        upload_date=str(info.get("upload_date") or "") or None,
        language=str(info.get("language") or "es"),
        has_manual_captions=bool(info.get("subtitles")),
        has_auto_captions=bool(info.get("automatic_captions")),
    )


def get_transcript(
    video_id: str, languages: list[str] | None = None
) -> tuple[Transcript, dict]:
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("Falta yt-dlp: pip install yt-dlp") from e
    languages = languages or ["es", "en"]
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": languages,
        "subtitlesformat": "vtt",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
        info = ydl.extract_info(watch_url(video_id), download=False) or {}
    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    # Preferir manuales en idioma preferido, luego automáticos
    for pool, manual in ((subs, True), (auto, False)):
        for lang in languages + ["en", "es"]:
            tracks = pool.get(lang) or pool.get(lang.split("-")[0]) or []
            for track in tracks:
                url = track.get("url")
                if not url:
                    continue
                import requests

                content = requests.get(url, timeout=30).text
                segments = parse_vtt(content)
                if segments:
                    t = Transcript.from_segments(segments, source="ytdlp", language=lang)
                    return t, {
                        "has_manual_captions": manual,
                        "has_auto_captions": True,
                        "language": lang,
                    }
    raise RuntimeError("yt-dlp no encontró subtítulos (ni manuales ni automáticos).")
