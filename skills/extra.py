"""Skills concretas: summary largo, key points, capítulos, quotes, sponsor-cut."""

from __future__ import annotations

import re
from typing import Any

from core.models import AnalysisResult, Transcript, VideoMetadata
from skills.base import Skill
from utils.files import fmt_ts


class SummarySkill(Skill):
    name = "summary"
    description = "Resumen extendido del video."

    def run(self, metadata, transcript, analysis, llm=None) -> str:
        if llm is not None and getattr(llm, "available", False):
            try:
                return llm.chat(
                    f"Resumí en español en 8-12 líneas este transcript de '{metadata.title}':\n\n"
                    + transcript.full_text[:10000]
                )
            except Exception:
                pass
        return analysis.summary


class KeyPointsSkill(Skill):
    name = "key_points"
    description = "Puntos clave numerados."

    def run(self, metadata, transcript, analysis, llm=None) -> list[str]:
        return analysis.key_points


class ChaptersSkill(Skill):
    name = "chapters"
    description = "Capítulos con timestamps (por silencios largos o LLM)."

    def run(self, metadata, transcript, analysis, llm=None) -> list[dict[str, str]]:
        segs = transcript.segments
        if not segs:
            return []
        # Heurística: nuevo capítulo cada ~5 min o tras un gap > 8s
        chapters = [{"ts": fmt_ts(segs[0].start), "title": "Inicio"}]
        last_mark = segs[0].start
        for prev, cur in zip(segs, segs[1:]):
            gap = cur.start - prev.end
            if cur.start - last_mark >= 300 or gap >= 8:
                title = " ".join(cur.text.split()[:6])
                chapters.append({"ts": fmt_ts(cur.start), "title": title or "Sección"})
                last_mark = cur.start
        return chapters[:20]


class QuotesSkill(Skill):
    name = "quotes"
    description = "Frases memorables / citables."

    def run(self, metadata, transcript, analysis, llm=None) -> list[str]:
        if llm is not None and getattr(llm, "available", False):
            try:
                raw = llm.chat(
                    "Extraé 3-5 frases citables literales (máx 25 palabras c/u) de este transcript, "
                    "una por línea con guion:\n\n" + transcript.full_text[:10000]
                )
                quotes = [
                    ln.strip("-• ").strip()
                    for ln in raw.split("\n")
                    if len(ln.strip()) > 20
                ]
                return quotes[:5]
            except Exception:
                pass
        # Fallback: oraciones largas con "yo creo", "lo importante", "recuerda", etc.
        out = []
        for s in re.split(r"[.!?]\s+", transcript.full_text):
            s = s.strip()
            if 60 < len(s) < 200 and re.search(
                r"importante|clave|recuerda|nunca|siempre|secreto|error|consejo", s, re.I
            ):
                out.append(s)
            if len(out) >= 5:
                break
        return out


class SponsorCutSkill(Skill):
    name = "sponsor_cut"
    description = "Reporte del corte de sponsors (se aplica en el pipeline, acá solo reporta)."

    def run(self, metadata, transcript, analysis, llm=None) -> Any:
        return getattr(transcript, "_sponsor_report", None)


REGISTRY: dict[str, Skill] = {
    s.name: s
    for s in (SummarySkill(), KeyPointsSkill(), ChaptersSkill(), QuotesSkill(), SponsorCutSkill())
}


def run_enabled_skills(
    enabled: list[str],
    metadata: VideoMetadata,
    transcript: Transcript,
    analysis: AnalysisResult,
    llm=None,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    applied: list[str] = []
    for name in enabled:
        skill = REGISTRY.get(name)
        if not skill or not skill.should_run(analysis):
            continue
        try:
            results[name] = skill.run(metadata, transcript, analysis, llm)
            applied.append(name)
        except Exception:
            continue
    return {"results": results, "applied": applied}
