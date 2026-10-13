"""Research híbrido de videos nuevos: YouTube Data API si hay key, si no yt-dlp + RSS.

Flujo pensado para el agente:
  1. `research_topics()` busca candidatos por topic/categoría.
  2. Filtra ya-procesados (index.json) y ya-ofrecidos (offered.json, con cooldown).
  3. El agente MUESTRA la lista al usuario y solo procesa tras confirmación.
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from utils.logging import get_logger
from utils.url import extract_video_id, watch_url

log = get_logger()


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def ytdlp_search(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Búsqueda sin API key vía yt-dlp ytsearch. Devuelve [{video_id,title,channel,url,...}]."""
    try:
        import yt_dlp
    except ImportError as e:
        raise RuntimeError("Falta yt-dlp: pip install yt-dlp") from e
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
        data = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False) or {}
    out = []
    for entry in data.get("entries", []) or []:
        vid = entry.get("id") or extract_video_id(entry.get("url") or "")
        if not vid:
            continue
        out.append(
            {
                "video_id": vid,
                "title": entry.get("title", ""),
                "channel": entry.get("channel") or entry.get("uploader", ""),
                "url": watch_url(vid),
                "duration": entry.get("duration") or 0,
                "source": "ytsearch",
                "query": query,
            }
        )
    return out


def youtube_api_search(
    query: str,
    api_key: str,
    max_results: int = 8,
    order: str = "relevance",
    published_after: str = "",
) -> list[dict[str, Any]]:
    """Búsqueda oficial. order=relevance imita lo que YouTube te muestra (no date)."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": order,
        "key": api_key,
    }
    if published_after:
        params["publishedAfter"] = published_after
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params=params,
        timeout=20,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get("items", []):
        vid = (item.get("id") or {}).get("videoId", "")
        sn = item.get("snippet", {})
        if vid:
            out.append(
                {
                    "video_id": vid,
                    "title": sn.get("title", ""),
                    "channel": sn.get("channelTitle", ""),
                    "published": sn.get("publishedAt", ""),
                    "url": watch_url(vid),
                    "source": "youtube_api",
                    "query": query,
                }
            )
    return out


def _fmt_views(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n) if n else ""


def enrich_videos(video_ids: list[str], api_key: str) -> dict[str, dict[str, Any]]:
    """Trae viewCount + channelId + fecha vía videos.list (1 unidad de cuota cada 50)."""
    stats: dict[str, dict[str, Any]] = {}
    if not api_key or not video_ids:
        return stats
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "statistics,snippet",
                "id": ",".join(video_ids[:50]),
                "key": api_key,
            },
            timeout=20,
        )
        r.raise_for_status()
        for item in r.json().get("items", []):
            st = item.get("statistics", {})
            sn = item.get("snippet", {})
            stats[item.get("id", "")] = {
                "views": int(st.get("viewCount", 0) or 0),
                "channel_id": sn.get("channelId", ""),
                "published": sn.get("publishedAt", ""),
            }
    except Exception as e:
        log.warning(f"No se pudieron traer estadísticas: {e}")
    return stats


def channel_subs(channel_ids: list[str], api_key: str) -> dict[str, int]:
    """Subs por canal en UNA sola llamada (1 unidad cada 50 canales)."""
    subs: dict[str, int] = {}
    ids = [c for c in dict.fromkeys(channel_ids) if c]
    if not api_key or not ids:
        return subs
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "statistics", "id": ",".join(ids[:50]), "key": api_key},
            timeout=20,
        )
        r.raise_for_status()
        for item in r.json().get("items", []):
            raw = (item.get("statistics", {}) or {}).get("subscriberCount")
            subs[item.get("id", "")] = int(raw) if raw else 0  # 0 = ocultos/desconocido
    except Exception as e:
        log.warning(f"No se pudieron traer suscriptores: {e}")
    return subs


def channel_rss_videos(channel_id: str, limit: int = 6) -> list[dict[str, Any]]:
    """Últimos videos de un canal vía RSS público (sin key)."""
    r = requests.get(
        "https://www.youtube.com/feeds/videos.xml",
        params={"channel_id": channel_id},
        timeout=20,
    )
    r.raise_for_status()
    ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    root = ET.fromstring(r.text)
    out = []
    for entry in root.findall("atom:entry", ns)[:limit]:
        vid = (entry.find("yt:videoId", ns).text or "") if entry.find("yt:videoId", ns) is not None else ""
        title = entry.find("atom:title", ns).text if entry.find("atom:title", ns) is not None else ""
        author = entry.find("atom:author/atom:name", ns)
        if vid:
            out.append(
                {
                    "video_id": vid,
                    "title": title or "",
                    "channel": author.text if author is not None else "",
                    "url": watch_url(vid),
                    "source": "rss",
                }
            )
    return out


def research_topics(
    topics: list[str],
    config: dict,
    processed_ids: set[str],
    project_root: Path,
    api_key: str = "",
) -> list[dict[str, Any]]:
    """Busca candidatos, filtra procesados/ofrecidos recientemente. No procesa nada."""
    r_cfg = config.get("research", {})
    mode = r_cfg.get("mode", "hybrid")
    n = int(r_cfg.get("max_results_per_topic", 8))
    min_dur = int(r_cfg.get("min_duration_seconds", 0))
    cooldown_days = int(r_cfg.get("cooldown_days", 7))
    # --- Filtros de calidad (config.yaml) ---
    order = r_cfg.get("order", "relevance")       # relevance imita a youtube.com
    min_views = int(r_cfg.get("min_views", 0))    # ej. 10000: ignora videos chicos
    min_subs = int(r_cfg.get("min_subs", 0))      # ej. 5000: ignora canales chicos
    max_age_days = int(r_cfg.get("max_age_days", 0))  # ej. 365: solo último año
    prefer = [p.lower() for p in (r_cfg.get("prefer_channels") or [])]  # tus canales de confianza
    published_after = ""
    if max_age_days:
        from datetime import timedelta, timezone

        published_after = (
            datetime.now(timezone.utc) - timedelta(days=max_age_days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    offered_file = project_root / "data" / "offered.json"
    offered: dict[str, float] = _load_json(offered_file, {})
    now = time.time()
    fresh_offered = {k: v for k, v in offered.items() if now - v < cooldown_days * 86400}

    use_api = mode in ("api", "hybrid") and bool(api_key)
    candidates: list[dict[str, Any]] = []
    for topic in topics:
        results: list[dict[str, Any]] = []
        if use_api:
            try:
                results = youtube_api_search(topic, api_key, n, order, published_after)
            except Exception as e:
                log.warning(f"API de YouTube falló ({e}); usando yt-dlp gratis como respaldo.")
        if not results and mode in ("ytdlp", "hybrid"):
            try:
                results = ytdlp_search(topic, n)
            except Exception as e:
                log.warning(f"Research '{topic}' falló: {e}")
                continue
        for c in results:
            vid = c["video_id"]
            if vid in processed_ids:
                continue
            if vid in fresh_offered:
                continue
            if min_dur and (c.get("duration") or 0) and c["duration"] < min_dur:
                continue
            candidates.append(c)

    # Vigilar canales configurados
    for ch in r_cfg.get("channels", []) or []:
        try:
            for c in channel_rss_videos(ch):
                if c["video_id"] not in processed_ids and c["video_id"] not in fresh_offered:
                    candidates.append(c)
        except Exception as e:
            log.warning(f"RSS {ch} falló: {e}")

    # --- Enriquecer con vistas/subs y filtrar por calidad (solo si hay API key) ---
    if use_api and candidates and (min_views or min_subs):
        stats = enrich_videos([c["video_id"] for c in candidates], api_key)
        subs = channel_subs(
            [s.get("channel_id", "") for s in stats.values()], api_key
        )
        kept = []
        for c in candidates:
            st = stats.get(c["video_id"], {})
            views = int(c.get("view_count") or st.get("views") or 0)
            c["views"] = views
            c["channel_id"] = st.get("channel_id", "")
            if min_views and views and views < min_views:
                continue  # video chico con dato conocido -> fuera
            if min_subs:
                n_subs = subs.get(st.get("channel_id", ""), 0)
                if n_subs and n_subs < min_subs:
                    continue  # canal chico con dato conocido -> fuera
            kept.append(c)
        dropped = len(candidates) - len(kept)
        if dropped:
            log.info(f"Filtro de calidad: {dropped} candidatos descartados (pocas vistas/subs).")
        candidates = kept

    # --- Ordenar: tus canales de confianza primero, luego por vistas ---
    def _rank(c: dict) -> tuple:
        name = str(c.get("channel", "")).lower()
        trusted = any(p in name for p in prefer) if prefer else False
        return (0 if trusted else 1, -(c.get("views") or 0))

    candidates.sort(key=_rank)

    # Marcar como ofrecidos (para el cooldown) y persistir
    for c in candidates:
        fresh_offered[c["video_id"]] = now
    offered_file.parent.mkdir(parents=True, exist_ok=True)
    offered_file.write_text(json.dumps(fresh_offered, indent=2), encoding="utf-8")
    return candidates


def format_digest(candidates: list[dict[str, Any]]) -> str:
    """Texto listo para mostrar al usuario y pedir confirmación."""
    if not candidates:
        return "Sin candidatos nuevos: todo lo encontrado ya está procesado u ofrecido."
    by_query: dict[str, list[dict]] = {}
    for c in candidates:
        by_query.setdefault(c.get("query") or c.get("source", "?"), []).append(c)
    lines = ["Videos nuevos para transcribir (responde con los numeros que apruebas):", ""]
    idx = 0
    for topic, items in by_query.items():
        lines.append(f"**{topic}**")
        for c in items:
            idx += 1
            dur = f" ({int(c.get('duration', 0) // 60)} min)" if c.get("duration") else ""
            views = f" [{_fmt_views(c.get('views'))} vistas]" if c.get("views") else ""
            lines.append(f"  {idx}. {c['title']} — {c.get('channel', '?')}{dur}{views}")
            lines.append(f"     {c['url']}")
        lines.append("")
    lines.append("Decime ej: `procesá 1, 3` o `todos`, y los transcribo.")
    return "\n".join(lines)


def default_topics(config: dict) -> list[str]:
    r_cfg = config.get("research", {})
    if r_cfg.get("topics"):
        return list(r_cfg["topics"])
    # Derivar de categorías: "inteligencia_artificial" -> "inteligencia artificial"
    cats = [c for c in config.get("categories", []) if c != "sin-categorizar"]
    return [f"{c.replace('_', ' ')} tutorial español" for c in cats] + [
        f"{c.replace('_', ' ')} 2026" for c in cats[:3]
    ]


def log_research_run(project_root: Path, candidates: list[dict[str, Any]]) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = project_root / "data" / f"research_{ts}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_digest(candidates), encoding="utf-8")
    return path
