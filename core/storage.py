"""Guardado en carpetas por categoría + índice global idempotente."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import ProcessedVideo
from utils.files import fmt_ts, sanitize_filename


def ensure_category_folder(base_dir: Path, category: str) -> Path:
    folder = base_dir / sanitize_filename(category.lower().replace(" ", "_"))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def build_markdown(p: ProcessedVideo, include_timestamps: bool = True) -> str:
    m, a, t = p.metadata, p.analysis, p.transcript
    lines = [
        f"# {m.title or m.video_id}",
        "",
        f"- **URL:** {m.url}",
        f"- **Canal:** {m.channel}",
        f"- **Duración:** {fmt_ts(m.duration_seconds)}",
        f"- **Categoría:** `{a.category}`" + (f" / {a.subcategory}" if a.subcategory else ""),
        f"- **Tipo:** {a.content_type} | **Dificultad:** {a.difficulty or '-'}",
        f"- **Tags:** {', '.join(a.tags) or '-'}",
        f"- **Fuente transcript:** {t.source} ({t.language})",
        f"- **Procesado:** {p.processed_at.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Resumen",
        "",
        a.summary or "_(sin resumen)_",
        "",
        "## Puntos clave",
        "",
    ]
    for i, kp in enumerate(a.key_points, 1):
        lines.append(f"{i}. {kp}")
    if not a.key_points:
        lines.append("_(sin key points)_")

    if p.extra.get("chapters"):
        lines += ["", "## Capítulos", ""]
        for ch in p.extra["chapters"]:
            lines.append(f"- [{ch['ts']}] {ch['title']}")
    if p.extra.get("quotes"):
        lines += ["", "## Frases destacadas", ""]
        for q in p.extra["quotes"]:
            lines.append(f"> {q}")

    if p.sponsors.segments_removed:
        lines += ["", "## Nota: sponsors cortados", ""]
        for r in p.sponsors.segments_removed:
            lines.append(
                f"- [{fmt_ts(r['start'])}–{fmt_ts(r['end'])}] "
                f"({r.get('category', 'sponsor')}): _{r.get('text', '')}..._"
            )

    lines += ["", "## Transcripción completa (sin sponsors)", ""]
    if include_timestamps:
        for seg in t.segments:
            lines.append(f"[{fmt_ts(seg.start)}] {seg.text}")
    else:
        lines.append(t.full_text)
    lines.append("")
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def load_index(index_file: Path) -> dict[str, Any]:
    try:
        return json.loads(index_file.read_text(encoding="utf-8"))
    except Exception:
        return {"videos": {}}


def save_processed(p: ProcessedVideo, config: dict, project_root: Path) -> dict[str, Path]:
    paths_cfg = config.get("paths", {})
    out_dir = (project_root / paths_cfg.get("output_dir", "./data/processed")).resolve()
    raw_dir = (project_root / paths_cfg.get("raw_dir", "./data/raw")).resolve()
    index_file = (project_root / paths_cfg.get("index_file", "./data/index.json")).resolve()
    formats = config.get("output", {}).get("formats", ["markdown", "json"])
    include_ts = config.get("output", {}).get("include_timestamps", True)

    folder = ensure_category_folder(out_dir, p.analysis.category)
    base = f"{sanitize_filename(p.metadata.title or p.metadata.video_id)}_{p.metadata.video_id}"
    paths: dict[str, Path] = {}

    if "markdown" in formats:
        paths["markdown"] = folder / f"{base}.md"
        _atomic_write(paths["markdown"], build_markdown(p, include_ts))
    if "json" in formats:
        payload = {
            "video_id": p.metadata.video_id,
            "url": p.metadata.url,
            "title": p.metadata.title,
            "channel": p.metadata.channel,
            "duration_seconds": p.metadata.duration_seconds,
            "category": p.analysis.category,
            "tags": p.analysis.tags,
            "summary": p.analysis.summary,
            "key_points": p.analysis.key_points,
            "transcript_source": p.transcript.source,
            "sponsors_removed": len(p.sponsors.segments_removed),
            "processed_at": p.processed_at.isoformat(),
        }
        paths["json"] = folder / f"{base}.json"
        _atomic_write(paths["json"], json.dumps(payload, indent=2, ensure_ascii=False))

    if config.get("pipeline", {}).get("save_raw_transcript", True) and p.raw_transcript:
        raw_path = raw_dir / f"{base}.txt"
        _atomic_write(raw_path, p.raw_transcript.full_text)
        paths["raw"] = raw_path

    # Índice global (idempotencia)
    index = load_index(index_file)
    old_entry = index.get("videos", {}).get(p.metadata.video_id, {})
    old_cat = old_entry.get("category")
    if old_cat and old_cat != p.analysis.category:
        # La categoría cambió (--force): borrar archivos viejos para no dejar huérfanos
        for old_path_str in old_entry.get("paths", {}).values():
            try:
                old_path = Path(old_path_str)
                if old_path.is_file():
                    old_path.unlink()
            except Exception:
                pass
    index["videos"][p.metadata.video_id] = {
        "title": p.metadata.title,
        "category": p.analysis.category,
        "paths": {k: str(v) for k, v in paths.items() if k != "raw"},
        "processed_at": datetime.now().isoformat(),
    }
    index_file.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(index_file, json.dumps(index, indent=2, ensure_ascii=False))

    p.output_paths = paths
    return paths
