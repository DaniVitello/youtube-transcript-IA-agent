"""CLI del agente YouTube. Uso (Windows PowerShell, desde la carpeta del proyecto):

  py main.py process <url> [--category CATEGORIA] [--force]
  py main.py process-batch urls.txt
  py main.py research [--topic "texto"] [--all] [--process]
  py main.py list-categories
  py main.py status
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Consola Windows (cp1252): no crashear con caracteres raros del transcript,
# los reemplaza por ? en pantalla (los archivos .md/.json guardan UTF-8 intacto).
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

load_dotenv(PROJECT_ROOT / ".env")

from core.pipeline import AlreadyProcessed, InvalidURLError, load_config, process_video  # noqa: E402
from core.research import (  # noqa: E402
    default_topics,
    format_digest,
    log_research_run,
    research_topics,
)
from core.storage import load_index  # noqa: E402
from utils.logging import get_logger  # noqa: E402

log = get_logger()


def cmd_process(args, config) -> int:
    try:
        p = process_video(
            args.url, config, PROJECT_ROOT,
            category_override=args.category, force=args.force,
        )
    except AlreadyProcessed as e:
        print(f"[SKIP] {e}")
        return 0
    except (InvalidURLError, RuntimeError) as e:
        print(f"[ERROR] {e}")
        return 1
    md = p.output_paths.get("markdown", "?")
    print("[OK] Video procesado\n")
    print(f"Título:    {p.metadata.title}")
    print(f"Categoría: {p.analysis.category} (confianza {p.analysis.confidence:.0%}, vía {p.analysis.method})")
    print(f"Tipo:      {p.analysis.content_type}")
    print(f"Sponsors:  {len(p.sponsors.segments_removed)} segmentos cortados ({p.sponsors.method})")
    print(f"\nResumen:\n{p.analysis.summary}\n")
    print("Key points:")
    for kp in p.analysis.key_points[:5]:
        print(f"  • {kp}")
    print(f"\nGuardado en:\n  {md}")
    return 0


def cmd_batch(args, config) -> int:
    urls = [ln.strip() for ln in Path(args.file).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    ok, fail, skip = 0, 0, 0
    for url in urls:
        try:
            process_video(url, config, PROJECT_ROOT, force=args.force)
            print(f"[OK] {url}")
            ok += 1
        except AlreadyProcessed:
            print(f"[SKIP] ya procesado: {url}")
            skip += 1
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            fail += 1
    print(f"\nListo: {ok} OK, {skip} omitidos, {fail} fallidos.")
    return 1 if fail else 0


def cmd_research(args, config) -> int:
    """Solo BUSCA y propone. Procesa únicamente con --process tras confirmación del usuario."""
    index = load_index(PROJECT_ROOT / config.get("paths", {}).get("index_file", "./data/index.json"))
    processed_ids = set(index.get("videos", {}).keys())
    if args.topic:
        topics = [args.topic]
    elif args.all:
        topics = default_topics(config)
    else:
        topics = default_topics(config)[:3]
        print("(tip: --all busca en todas las categorías, --topic \"...\" en una puntual)\n")
    print(f"Buscando en {len(topics)} topic(s)...")
    from utils.llm import youtube_api_key

    candidates = research_topics(
        topics, config, processed_ids, PROJECT_ROOT,
        api_key=youtube_api_key(),
    )
    digest = format_digest(candidates)
    print("\n" + digest)
    path = log_research_run(PROJECT_ROOT, candidates)
    print(f"\nDigest guardado en: {path}")
    if args.process and candidates:
        print("\n[!] --process: transcribiendo candidatos propuestos...")
        for c in candidates:
            try:
                process_video(c["url"], config, PROJECT_ROOT)
                print(f"[OK] {c['title']}")
            except Exception as e:
                print(f"[ERROR] {c['url']}: {e}")
    elif candidates:
        print("\nPara transcribir, corré p. ej.: py main.py process <url>")
    return 0


def cmd_categories(config) -> int:
    print("Categorias configuradas (config.yaml):")
    for c in config.get("categories", []):
        print(f"  - {c}")
    return 0


def cmd_status(config) -> int:
    index = load_index(PROJECT_ROOT / config.get("paths", {}).get("index_file", "./data/index.json"))
    videos = index.get("videos", {})
    print(f"Videos procesados: {len(videos)}")
    by_cat: dict[str, int] = {}
    for v in videos.values():
        by_cat[v.get("category", "?")] = by_cat.get(v.get("category", "?"), 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat}: {n}")
    import shutil

    from utils.llm import make_client, youtube_api_key

    llm = make_client(config.get("llm"))
    print(f"\nLLM: {llm.provider} ({llm.model}): {'[OK] key configurada' if llm.available else '[X] falta key en .env'}")
    print(f"YouTube API (research): {'[OK] key configurada' if youtube_api_key() else '[ ] no configurada (research usa yt-dlp)'}")
    print(f"ffmpeg: {'[OK]' if shutil.which('ffmpeg') else '[X] falta (necesario solo para fallback Whisper)'}")
    return 0


def main() -> int:
    config = load_config(PROJECT_ROOT)
    ap = argparse.ArgumentParser(description="Agente de transcripción de YouTube")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("process", help="Transcribir + resumir un video")
    p.add_argument("url")
    p.add_argument("--category", default=None)
    p.add_argument("--force", action="store_true")

    b = sub.add_parser("process-batch", help="Procesar URLs desde un archivo (una por línea)")
    b.add_argument("file")
    b.add_argument("--force", action="store_true")

    r = sub.add_parser("research", help="Buscar videos nuevos y proponerlos (no procesa salvo --process)")
    r.add_argument("--topic", default=None)
    r.add_argument("--all", action="store_true")
    r.add_argument("--process", action="store_true",
                   help="Procesar los candidatos SIN pedir confirmación. El agente NO debe usarlo sin tu OK.")

    sub.add_parser("list-categories", help="Ver categorías")
    sub.add_parser("status", help="Estado del agente")

    args = ap.parse_args()
    if args.cmd == "process":
        return cmd_process(args, config)
    if args.cmd == "process-batch":
        return cmd_batch(args, config)
    if args.cmd == "research":
        return cmd_research(args, config)
    if args.cmd == "list-categories":
        return cmd_categories(config)
    if args.cmd == "status":
        return cmd_status(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
