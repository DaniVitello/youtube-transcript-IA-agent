"""Detección y corte de sponsors / propaganda del transcript.

Estrategia en 2 niveles (la elegida por el usuario):
  1. SponsorBlock API (gratis, timestamps de la comunidad) -> corte preciso.
  2. Fallback heurístico + LLM (Groq) cuando SponsorBlock no tiene datos.

Referencia API: https://wiki.sponsor.ajay.app/w/API_Docs
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from core.models import SponsorReport, Transcript, TranscriptSegment
from utils.files import fmt_ts
from utils.logging import get_logger

log = get_logger()

SB_ENDPOINT = "https://sponsor.ajay.app/api/skipSegments"

# Frases típicas de sponsor / autopromo (ES + EN) para el fallback heurístico
_SPONSOR_PATTERNS = [
    r"gracias?\s+a\s+\w+\s+por\s+patrocinar",
    r"este\s+video\s+(está|esta)\s+patrocinado",
    r"sponsor(ed)?\s+by",
    r"usa\s+mi\s+c[óo]digo",
    r"c[óo]digo\s+de\s+descuento",
    r"link\s+en\s+la\s+descripci[óo]n",
    r"enlace\s+en\s+la\s+descripci[óo]n",
    r"prueba\s+gratis\s+por",
    r"suscr[íi]bete\s+a\s+\w+",
    r"haz\s+clic\s+en\s+el\s+enlace",
    r"con\s+el\s+cup[óo]n",
    r"nordvpn|hostinger|skillshare|audible|brilliant|ground\.news",
]
_SPONSOR_RE = re.compile("|".join(_SPONSOR_PATTERNS), re.IGNORECASE)


def fetch_sponsorblock_segments(
    video_id: str, categories: list[str] | None = None, timeout: int = 15
) -> list[dict[str, Any]]:
    """Consulta SponsorBlock. Devuelve [{start, end, category}]. Vacío si no hay datos."""
    categories = categories or ["sponsor", "selfpromo"]
    try:
        # La API espera `categories` como UN solo parámetro con array JSON:
        # ?videoID=xxx&categories=["sponsor","selfpromo"]
        r = requests.get(
            SB_ENDPOINT,
            params={"videoID": video_id, "categories": json.dumps(categories)},
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        if r.status_code == 404:
            return []  # video sin datos en la comunidad
        r.raise_for_status()
        out = []
        for item in r.json():
            seg = item.get("segment", [])
            if len(seg) == 2:
                out.append(
                    {
                        "start": float(seg[0]),
                        "end": float(seg[1]),
                        "category": item.get("category", "sponsor"),
                    }
                )
        return out
    except Exception as e:
        log.warning(f"SponsorBlock no disponible: {e}")
        return []


def cut_segments_by_ranges(
    segments: list[TranscriptSegment], ranges: list[dict[str, Any]]
) -> tuple[list[TranscriptSegment], list[dict[str, Any]]]:
    """Filtra segmentos que caen dentro de los rangos. Devuelve (limpios, removidos)."""
    removed: list[dict[str, Any]] = []
    kept: list[TranscriptSegment] = []
    for seg in segments:
        hit = next(
            (rg for rg in ranges if rg["start"] <= seg.start < rg["end"]), None
        )
        if hit:
            removed.append(
                {
                    "start": seg.start,
                    "end": seg.end,
                    "category": hit.get("category", "sponsor"),
                    "text": seg.text[:160],
                }
            )
        else:
            kept.append(seg)
    return kept, removed


def heuristic_ranges(transcript: Transcript) -> list[dict[str, Any]]:
    """Fallback sin red: marca segmentos con lenguaje típico de sponsor."""
    ranges = []
    for seg in transcript.segments:
        if _SPONSOR_RE.search(seg.text):
            # Ventana: el segmento + ~20s siguientes (el pitch suele durar eso)
            ranges.append(
                {"start": seg.start, "end": seg.start + 25.0, "category": "selfpromo?"}
            )
    return ranges


def apply_sponsor_cut(
    transcript: Transcript, video_id: str, config: dict, llm=None
) -> tuple[Transcript, SponsorReport]:
    """Aplica corte de sponsors. Devuelve (transcript_limpio, reporte)."""
    s_cfg = config.get("sponsors", {})
    report = SponsorReport(chars_before=len(transcript.full_text))

    if not s_cfg.get("enabled", True):
        report.chars_after = report.chars_before
        return transcript, report

    # Nivel 1: SponsorBlock
    ranges: list[dict[str, Any]] = []
    method = "none"
    if s_cfg.get("use_sponsorblock", True):
        ranges = fetch_sponsorblock_segments(video_id, s_cfg.get("sb_categories"))
        if ranges:
            method = "sponsorblock"

    # Nivel 2: fallback heurístico (+ nota de que LLM puede refinarlo)
    if not ranges and s_cfg.get("llm_fallback", True):
        ranges = heuristic_ranges(transcript)
        if ranges:
            method = "heuristic"
            # NOTA: el LLM ya recibe el texto limpio en analyzer.py; si la
            # heurística marcó algo dudoso (categoría "selfpromo?"), el resumen
            # lo confirma. No gastamos una llamada extra solo para esto.

    if not ranges:
        report.chars_after = report.chars_before
        return transcript, report

    kept, removed = cut_segments_by_ranges(transcript.segments, ranges)
    # No cortar más del 25%: si la heurística se disparó de más, abortar por seguridad
    if len(kept) < 0.75 * len(transcript.segments):
        log.warning("Corte de sponsors abortado: marcaba >25% del video (falso positivo).")
        report.chars_after = report.chars_before
        return transcript, report

    clean = Transcript.from_segments(kept, transcript.source, transcript.language)
    report.segments_removed = removed
    report.method = method
    report.chars_after = len(clean.full_text)
    total_s = sum(r["end"] - r["start"] for r in removed)
    log.info(
        f"Sponsors cortados ({method}): {len(removed)} segmentos, "
        f"~{fmt_ts(total_s)} eliminados."
    )
    return clean, report
