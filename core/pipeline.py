"""Orquestador principal: valida -> metadata -> transcript -> sponsors -> análisis -> skills -> guardado."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from core import analyzer, sponsors, storage, transcript as transcript_mod
from core.models import ProcessedVideo, VideoMetadata
from skills.extra import run_enabled_skills
from utils.llm import make_client
from utils.logging import get_logger
from utils.url import extract_video_id, watch_url

log = get_logger()


class AlreadyProcessed(Exception):
    pass


class InvalidURLError(ValueError):
    pass


def load_config(project_root: Path) -> dict[str, Any]:
    import yaml

    cfg_path = project_root / "config.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def is_processed(video_id: str, project_root: Path, config: dict) -> dict | None:
    index_file = project_root / config.get("paths", {}).get("index_file", "./data/index.json")
    index = storage.load_index(index_file)
    return index.get("videos", {}).get(video_id)


def process_video(
    url_or_id: str,
    config: dict,
    project_root: Path,
    category_override: str | None = None,
    force: bool = False,
) -> ProcessedVideo:
    video_id = extract_video_id(url_or_id)
    if not video_id:
        raise InvalidURLError(f"URL/ID de YouTube no válido: {url_or_id!r}")

    if not force and config.get("pipeline", {}).get("skip_if_already_processed", True):
        cached = is_processed(video_id, project_root, config)
        if cached:
            raise AlreadyProcessed(
                f"Video {video_id} ya procesado ({cached.get('category')}). "
                f"Usá --force para reprocesar."
            )

    # 1. Metadata (yt-dlp; si falla, metadata mínima para no bloquear)
    try:
        from providers import ytdlp as ytdlp_prov

        metadata = ytdlp_prov.fetch_metadata(video_id)
    except Exception as e:
        log.warning(f"Metadata vía yt-dlp falló ({e}); usando mínima.")
        metadata = VideoMetadata(video_id=video_id, url=watch_url(video_id))

    # 2. Transcript con fallback
    transcript_raw, flags = transcript_mod.get_transcript_with_fallback(video_id, config)
    for k in ("has_manual_captions", "has_auto_captions", "language"):
        if k in flags and hasattr(metadata, k):
            setattr(metadata, k, flags[k])

    # 3. Corte de sponsors (ANTES del análisis: el resumen no debe incluir publicidad)
    llm = make_client(config.get("llm"))
    clean_transcript, sponsor_report = sponsors.apply_sponsor_cut(
        transcript_raw, video_id, config, llm
    )
    clean_transcript._sponsor_report = sponsor_report  # type: ignore[attr-defined]

    # 4. Análisis sobre el texto LIMPIO
    analysis = analyzer.analyze(
        metadata.title, metadata.channel, clean_transcript.full_text, config, llm
    )
    if category_override:
        if category_override in config.get("categories", []):
            analysis.category = category_override
        else:
            log.warning(f"Categoría override '{category_override}' no existe; se ignora.")

    # 5. Skills adicionales
    enabled = config.get("skills", {}).get("enabled", [])
    skill_out = run_enabled_skills(enabled, metadata, clean_transcript, analysis, llm)

    # 6-8. Construir, guardar, indexar
    processed = ProcessedVideo(
        metadata=metadata,
        transcript=clean_transcript,
        raw_transcript=deepcopy(transcript_raw),
        analysis=analysis,
        sponsors=sponsor_report,
        skills_applied=skill_out["applied"],
        extra={
            k: v
            for k, v in skill_out["results"].items()
            if k in ("chapters", "quotes", "summary")
        },
    )
    storage.save_processed(processed, config, project_root)
    return processed
