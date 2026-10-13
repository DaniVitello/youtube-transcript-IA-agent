---
name: youtube-processor
description: Procesa videos de YouTube, transcribe sin sponsors, categoriza, resume y guarda por categoria. Usar cuando el usuario envie una URL de YouTube o pida transcribir, resumir o analizar un video.
---

# YouTube Processor

## Description
Procesa videos de YouTube: extrae transcript completo, corta sponsors/propaganda,
categoriza el contenido, genera resumen + key points, y guarda todo en carpetas
organizadas por categoría.

## Triggers
- Usuario envía una URL de YouTube (youtube.com / youtu.be / /shorts/)
- Usuario dice: "procesá este video", "transcribí", "resumí", "analizá este youtube"
- Comando explícito: /yt o /youtube

## Inputs
- url (obligatorio): URL o video_id de YouTube
- force (opcional): reprocesar aunque ya exista
- category_override (opcional): forzar una categoría de `config.yaml`

## Tools / Scripts
- `py main.py process <url> [--category X] [--force]` → pipeline completo
- `py main.py process-batch urls.txt` → varias URLs (una por línea)
- Todo corre desde la carpeta del proyecto `youtube-agent/`

## Behavior
1. Validar que la URL sea de YouTube (si no, decirlo y no inventar nada).
2. Llamar al pipeline Python con la URL. El script es la fuente de verdad:
   metadata → transcript (youtube_api → ytdlp → whisper) → corte de sponsors
   (SponsorBlock + heurística) → análisis Groq `openai/gpt-oss-120b` → skills → guardado.
3. Esperar el resultado.
4. Responder al usuario con:
   - Categoría asignada (+ confianza y método llm/heuristic)
   - Resumen corto
   - Cantidad de sponsors cortados
   - Ruta donde se guardó el archivo
   - Key points principales
5. Si el video ya estaba procesado, informarlo y NO reprocesar salvo `--force`.
6. Si falla (sin captions, video privado, sin GROQ_API_KEY), informar el error
   exacto y sugerir alternativa concreta.

## Output Example
✅ Video procesado

**Título:** Cómo funciona Whisper por dentro
**Categoría:** inteligencia_artificial (llm, 85%)
**Tipo:** tutorial
**Sponsors cortados:** 2 segmentos (~01:24)

**Resumen:**
Explicación profunda del modelo Whisper de OpenAI...

**Guardado en:**
`data/processed/inteligencia_artificial/Como_funciona_Whisper_por_dentro_abc123.md`

## Notes
- El script Python es la fuente de verdad; este skill solo orquesta y reporta.
- El análisis se hace sobre el transcript YA LIMPIO (los sponsors no contaminan el resumen).
- El transcript crudo se conserva en `data/raw/` por si hay que auditar un corte.
- Nuevas capacidades: agregar skill Python en `skills/` + activar en `config.yaml`,
  o crear un skill de agente hermano (ver `youtube-research`, `youtube-sponsorcut`).
