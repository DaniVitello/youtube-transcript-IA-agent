"""Categorización + resumen + key points con Groq, con fallback heurístico.

Si no hay GROQ_API_KEY, usa un clasificador por keywords (sin costo) para que
el pipeline siga funcionando; el resumen pasa a ser extractivo.
"""

from __future__ import annotations

import re
from collections import Counter

from core.models import AnalysisResult
from utils.logging import get_logger

log = get_logger()

_KEYWORDS: dict[str, list[str]] = {
    "programacion": ["código", "function", "python", "javascript", "api", "deploy", "bug", "framework", "typescript", "react"],
    "inteligencia_artificial": ["gpt", "llm", "transformer", "prompt", "agente", "openai", "groq", "whisper", "embedding", "fine-tuning", "ia"],
    "ciencia": ["experimento", "hipótesis", "física", "química", "biología", "estudio", "científico", "universo"],
    "finanzas": ["inversión", "bolsa", "interés", "inflación", "cripto", "bitcoin", "portfolio", "dividendo", "acciones"],
    "productividad": ["hábito", "procrastinar", "notion", "obsidian", "pomodoro", "rutina", "foco", "organizar"],
    "negocios": ["startup", "marketing", "ventas", "emprendimiento", "ceo", "negocio", "cliente"],
    "educacion": ["curso", "aprender", "estudiar", "lección", "universidad", "examen"],
    "salud": ["dormir", "ejercicio", "nutrición", "salud", "estrés", "dieta", "médico"],
    "entretenimiento": ["juego", "película", "serie", "gameplay", "reacción", "vlog"],
}

_ANALYZE_SYSTEM = (
    "Sos un clasificador experto de contenido de YouTube. "
    "Respondés SOLO con JSON válido."
)


def _analyze_with_llm(
    title: str, channel: str, text: str, categories: list[str], llm
) -> AnalysisResult | None:
    prompt = f"""Título: {title}
Canal: {channel}
Transcript (extracto, ya sin sponsors):
{text[:12000]}

Categorías posibles: {categories}

Devolvé SOLO un JSON válido con esta estructura exacta:
{{
  "category": "una de las categorías posibles",
  "subcategory": "string o null",
  "confidence": 0.0-1.0,
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "resumen de 3-5 oraciones en español",
  "key_points": ["punto 1", "punto 2", "punto 3", "punto 4", "punto 5"],
  "main_topics": ["tema1", "tema2"],
  "difficulty": "principiante|intermedio|avanzado|null",
  "content_type": "tutorial|charla|podcast|review|entrevista|otro"
}}"""
    try:
        data = llm.chat_json(prompt, system=_ANALYZE_SYSTEM)
        cat = str(data.get("category", "sin-categorizar"))
        if cat not in categories:
            cat = "sin-categorizar"
        return AnalysisResult(
            category=cat,
            subcategory=data.get("subcategory"),
            confidence=float(data.get("confidence", 0.7)),
            tags=list(data.get("tags", []))[:8],
            summary=str(data.get("summary", "")),
            key_points=list(data.get("key_points", []))[:10],
            main_topics=list(data.get("main_topics", []))[:6],
            difficulty=data.get("difficulty"),
            content_type=str(data.get("content_type", "otro")),
            method="llm",
        )
    except Exception as e:
        log.warning(f"LLM falló, usando heurística: {e}")
        return None


def _heuristic(title: str, text: str, categories: list[str]) -> AnalysisResult:
    blob = f"{title} {text[:6000]}".lower()
    # Match por PALABRA COMPLETA: evita que "ia" matchee dentro de "going"/"saying",
    # o "api" dentro de "happy"/"rapid".
    scores = {}
    for cat in categories:
        score = 0
        for kw in _KEYWORDS.get(cat, []):
            score += len(re.findall(r"\b" + re.escape(kw.lower()) + r"\b", blob))
        scores[cat] = score
    category = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[category] == 0:
        category = "sin-categorizar"
    # Resumen extractivo: primeras 3 oraciones con contenido
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", text) if len(s.strip()) > 40][:3]
    summary = ". ".join(sentences) + ("." if sentences else "")
    # Key points: oraciones con palabras frecuentes
    words = Counter(re.findall(r"[a-záéíóúñ]{4,}", blob))
    stop = {"para", "como", "pero", "este", "esta", "esto", "porque", "cuando", "donde"}
    top_words = {w for w, _ in words.most_common(25)} - stop
    ranked = sorted(
        (s for s in re.split(r"[.!?]\s+", text) if 40 < len(s) < 220),
        key=lambda s: sum(1 for w in top_words if w in s.lower()),
        reverse=True,
    )[:5]
    return AnalysisResult(
        category=category,
        confidence=0.4,
        tags=[c for c, sc in sorted(scores.items(), key=lambda x: -x[1])[:3] if sc > 0],
        summary=summary or "(sin GROQ_API_KEY: resumen extractivo no disponible)",
        key_points=[k.strip() for k in ranked],
        main_topics=[],
        content_type="otro",
        method="heuristic",
    )


def analyze(title: str, channel: str, text: str, config: dict, llm=None) -> AnalysisResult:
    categories = config.get("categories", ["sin-categorizar"])
    if llm is not None and getattr(llm, "available", False):
        result = _analyze_with_llm(title, channel, text, categories, llm)
        if result:
            return result
    return _heuristic(title, text, categories)
