---
name: youtube-sponsorcut
description: Detecta y corta sponsors, intros, autopromos y propaganda del transcript. Se aplica automaticamente en el pipeline; este skill permite auditar o re-evaluar un corte.
---

# YouTube SponsorCut

## Description
El corte de sponsors corre AUTOMÁTICAMENTE dentro del pipeline antes del análisis.
Este skill existe para auditar, explicar o ajustar un corte.

## Triggers
- Automático en cada `process` (no requiere invocación)
- Manual: "¿qué sponsors cortaste?", "revisá el corte de X", "el resumen incluye publicidad"

## Inputs
- video_id o ruta del .md procesado (para auditoría)
- sb_categories (opcional): ej. agregar "intro", "outro", "interaction" al corte

## Tools / Scripts
- Lógica en `core/sponsors.py` (`apply_sponsor_cut`)
- Crudo vs limpio: comparar `data/raw/<titulo>_<id>.txt` con la sección
  "Transcripción completa" del .md procesado

## Behavior
1. En `process` normal no hacer nada extra: el pipeline ya corta con
   SponsorBlock (`sponsor` + `selfpromo`) y fallback heurístico.
2. Si el usuario pide auditoría: mostrar la sección "Nota: sponsors cortados"
   del .md (timestamps + texto) y el método usado (sponsorblock/heuristic/none).
3. Si el resumen menciona publicidad o el usuario reporta un falso positivo:
   el crudo está intacto en `data/raw/` — ofrecer reprocesar con `--force`
   y/o ajustar `sponsors.sb_categories` en `config.yaml`.
4. Regla de seguridad del pipeline: si el corte marcaría >25% del video,
   se aborta automáticamente (evita falsos positivos de la heurística).

## Output Example
✂️ **Sponsors cortados** (vía SponsorBlock):
- [04:12–05:36] (sponsor): _"gracias a Hostinger por patrocinar..."_
- [21:03–21:28] (selfpromo): _"usa mi código..."_
Transcript crudo intacto en `data/raw/...txt`.

## Notes
- SponsorBlock depende de la comunidad: videos chicos/nuevos pueden no tener datos
  (ahí entra la heurística + el ojo del LLM en el resumen).
- Para máxima agresividad (quitar intros/outros/recaps), agregar categorías
  `intro`, `outro`, `preview`, `interaction` en `config.yaml → sponsors.sb_categories`.
