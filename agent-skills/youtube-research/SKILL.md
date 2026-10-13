---
name: youtube-research
description: Busca videos nuevos de los topicos del usuario y los propone para transcribir. Usar cuando el usuario pida descubrir videos, novedades, o diga "busca videos de X".
---

# YouTube Research

## Description
Research semanal/puntual de videos nuevos por tópico o categoría.
NUNCA transcribe sin confirmación explícita del usuario.

## Triggers
- "buscá videos nuevos", "qué hay de nuevo en X", "novedades de IA"
- Comando: /yt-research [--topic "..."] [--all]
- Rutina programada (cron / Task Scheduler): corre y deja el digest en `data/`

## Inputs
- topic (opcional): ej. "agentes IA con Groq"
- all (opcional): buscar en todas las categorías de `config.yaml`
- process (PROHIBIDO sin confirmación del usuario)

## Tools / Scripts
- `py main.py research [--topic "..."] [--all]` → busca y PROPONE (no procesa)
- Lee candidatos de `data/research_<fecha>.md`
- Tras el OK del usuario (`procesá 1, 3` o `todos`): `py main.py process <url>` por cada aprobado

## Behavior
1. Determinar topics: explícito del usuario, o `research.topics` de config,
   o derivados de `categories` (categoría → "… tutorial español").
2. Correr `research`: modo híbrido — YouTube Data API si hay `YOUTUBE_API_KEY`,
   si no `yt-dlp ytsearch` + RSS de `research.channels`. Filtrar ya-procesados
   (`data/index.json`) y ya-ofrecidos (`data/offered.json`, cooldown 7 días).
3. Presentar el digest numerado con título, canal, duración y URL.
4. Pedir confirmación explícita. Solo entonces procesar los aprobados con
   el skill `youtube-processor`.
5. Nunca usar `--process` sin el OK del usuario.

## Output Example
🎬 **Videos nuevos para transcribir** (respondé con los números que apruebes):

**inteligencia artificial tutorial español**
  1. Agentes con Groq y gpt-oss-120b — Canal X (18 min)
     https://www.youtube.com/watch?v=...
```

## Notes
- `offered.json` evita re-ofrecer lo mismo dentro del cooldown.
- Agregar `channel_id` en `research.channels` para vigilar canales vía RSS gratis.
- La API oficial da mejores metadatos pero consume cuota; yt-dlp es gratis e ilimitado.
