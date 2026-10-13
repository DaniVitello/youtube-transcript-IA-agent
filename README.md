# 🎬 YouTube Knowledge Agent

Agente que **transcribe → corta sponsors → categoriza → resume** videos de YouTube
y los guarda organizados por categoría. Hecho en **Python + skills** compatibles con
**OpenClaw y OpenCode** (formato `SKILL.md`), con LLM de **Groq (`openai/gpt-oss-120b`)**.

Tu boceto se tomó como base y se mejoró en estos puntos:

| Tu boceto | Mejora aplicada |
|---|---|
| Transcript con fallback | Mismo fallback, pero con parsing VTT propio y compatibilidad v0/v1 de `youtube-transcript-api` |
| Categorización LLM genérica | Cliente **Groq** concreto + **fallback heurístico** si no hay API key (el pipeline nunca se bloquea) |
| `detect_sponsors` como idea futura | **Implementado**: SponsorBlock API + heurística, con regla anti-falsos-positivos (>25% aborta) y auditoría en `data/raw/` |
| Sin research | **Nuevo módulo `core/research.py` híbrido**: YouTube Data API si hay key, si no `yt-dlp ytsearch` + RSS, con `offered.json` + cooldown para no repetir |
| Skills solo enunciados | **3 skills de agente listas** (`agent-skills/`) + **5 skills Python** plug-in (`skills/`) |
| Guardado básico | Markdown + JSON + índice global `index.json` idempotente (no reprocesa salvo `--force`) |

## Pipeline

```
URL ─▶ validar ─▶ metadata (yt-dlp) ─▶ transcript (api→ytdlp→whisper)
   ─▶ ✂️ corte sponsors (SponsorBlock→heurística) ─▶ análisis Groq ─▶ skills
   ─▶ md+json en data/processed/<categoria>/ ─▶ index.json
```

El orden importa: el análisis/resumen se hace sobre el transcript **ya limpio**,
así la publicidad no contamina el resumen. El crudo se conserva en `data/raw/`.

## Instalación (Windows PowerShell)

```powershell
cd youtube-agent
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# editar .env y pegar tu GROQ_API_KEY (gratis: https://console.groq.com/keys)
py main.py status
```

Extras opcionales:
- `YOUTUBE_API_KEY` (solo si quieres research vía API oficial con más metadatos).
- `ffmpeg` en PATH (solo para el fallback Whisper local). Verifica con `ffmpeg -version`.
- Para Whisper local: descomentar `faster-whisper` en `requirements.txt`.

## Uso

```powershell
# 1. Procesar un video
py main.py process "https://www.youtube.com/watch?v=VIDEO_ID"

# 2. Forzar categoría o reprocesar
py main.py process "URL" --category inteligencia_artificial
py main.py process "URL" --force

# 3. Lote desde archivo (una URL por línea)
py main.py process-batch urls.txt

# 4. Research: BUSCA y propone (no procesa solo)
py main.py research --topic "agentes IA con Groq"
py main.py research --all

# 5. Ver categorías / estado
py main.py list-categories
py main.py status
```

## Research con confirmación (flujo del agente)

1. `py main.py research --all` genera candidatos y los guarda en `data/research_<fecha>.md`.
2. El agente te muestra el digest numerado.
3. Respondes `procesá 1, 3` o `todos`.
4. Recién ahí corre `process` por cada aprobado. El flag `--process` existe pero el
   agente **tiene prohibido usarlo sin tu OK** (ver `agent-skills/youtube-research/SKILL.md`).

## Instalar las skills en tu agente

**OpenClaw** (por defecto busca en su workspace):
```powershell
Copy-Item -Recurse agent-skills\* "$env:USERPROFILE\.openclaw\workspace\skills\"
```

**OpenCode** (este repo usa `.opencode/skills/`):
```powershell
Copy-Item -Recurse agent-skills\* "C:\Users\DGVit\Desktop\.opencode\skills\"
```

Luego invocalas con: *"procesá este video URL…"*, *"buscá videos nuevos de X"*.

## Estructura

```
youtube-agent/
├── main.py                 # CLI: process | process-batch | research | status
├── config.yaml             # categorías, modelo Groq, sponsors, research (EDITABLE)
├── core/
│   ├── pipeline.py         # orquestador
│   ├── transcript.py       # fallback api→ytdlp→whisper
│   ├── sponsors.py         # SponsorBlock + heurística  ← novedad
│   ├── analyzer.py         # Groq + fallback heurístico
│   ├── research.py         # híbrido API/yt-dlp/RSS      ← novedad
│   └── storage.py          # md+json+index idempotente
├── providers/              # youtube_transcript.py, ytdlp.py, whisper.py
├── skills/                 # summary, key_points, chapters, quotes, sponsor_cut
├── agent-skills/           # SKILL.md para OpenClaw/OpenCode (3 skills)
└── data/processed/<cat>/   # salida organizada por categoría
```

## Recomendaciones de pipeline

1. **SponsorBlock primero, LLM después.** La API comunitaria da timestamps exactos
   gratis; el LLM solo como red de seguridad. Mantén `sb_categories: [sponsor, selfpromo]`
   y agrega `intro/outro/interaction` si quieres cortes agresivos.
2. **Nunca reprocesar sin `--force`.** `index.json` hace idempotente el pipeline;
   en lotes grandes un corte a mitad no duplica trabajo.
3. **Whisper solo como último recurso.** Es ~tiempo real en CPU; los captions de
   YouTube (manual > auto) son 100× más rápidos. Sube `whisper_model` a `medium`
   solo con GPU.
4. **Research con cooldown.** `offered.json` (7 días) evita que el digest semanal
   te re-proponga lo mismo. Vigila 3-5 canales por RSS (gratis, sin cuota).
5. **Automatiza el research** con Task Scheduler (Windows): semanal,
   `py main.py research --all`, y revisa `data/research_*.md`.
6. **Costo Groq: ~0.** `gpt-oss-120b` en Groq tiene tier gratuito generoso; el
   transcript se trunca a 12k chars (`max_chars_for_llm`) para no desperdiciar tokens.
7. **Extender:** nueva funcionalidad = archivo en `skills/` + registrar en
   `REGISTRY` + activar en `config.yaml → skills.enabled`. Ideas: `translate_to_spanish`,
   `extract_code_snippets`, `send_to_notion`, `anki_cards`.
