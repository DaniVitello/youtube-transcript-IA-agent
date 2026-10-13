"""Provider 3: Whisper local (fallback cuando no hay captions).

Descarga solo el audio con yt-dlp y transcribe con faster-whisper.
Es el más lento (~tiempo real en CPU con modelo small) pero funciona siempre.
Requiere: pip install faster-whisper  +  ffmpeg en el PATH.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.models import Transcript, TranscriptSegment
from utils.logging import get_logger
from utils.url import watch_url

log = get_logger()


def get_transcript(
    video_id: str, languages: list[str] | None = None, model_name: str = "small"
) -> tuple[Transcript, dict]:
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("Falta yt-dlp: pip install yt-dlp") from e
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "Falta faster-whisper: pip install faster-whisper (y ffmpeg en PATH)"
        ) from e

    languages = languages or ["es", "en"]
    tmpdir = Path(tempfile.mkdtemp(prefix="yt-agent-"))
    audio_tpl = str(tmpdir / "audio.%(ext)s")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": audio_tpl,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
        ydl.download([watch_url(video_id)])
    audios = sorted(tmpdir.glob("audio.*"))
    if not audios:
        raise RuntimeError("No se pudo descargar el audio.")
    log.info(f"Whisper ({model_name}): transcribiendo {audios[0].name} ...")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    lang_hint = (languages[0] or "es").split("-")[0]
    segments_iter, info = model.transcribe(str(audios[0]), language=lang_hint)
    segments = [
        TranscriptSegment(text=s.text.strip(), start=float(s.start), duration=float(s.end - s.start))
        for s in segments_iter
        if s.text.strip()
    ]
    if not segments:
        raise RuntimeError("Whisper devolvió transcript vacío.")
    t = Transcript.from_segments(
        segments, source="whisper", language=getattr(info, "language", lang_hint)
    )
    return t, {"language": t.language}
