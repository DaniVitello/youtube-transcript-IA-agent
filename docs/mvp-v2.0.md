# YouTube Agent — MVP v2.0

> Fuente única de verdad para el alcance, diseño y decisiones de la versión 2.0.
> Se actualiza cada vez que se especifican nuevos pasos. Se consulta desde la sesión de `youtube-agent` y desde la sesión de planificación en `tests`.

---

## 1. Propósito del producto

Convertir videos largos de YouTube (charlas de 1–2 horas) en conocimiento accionable, sin necesidad de ver todo el video.

- **Uso académico:** aprender IA, UX, mercado, estilo de vida.
- **Uso personal:** transcribir, resumir, hacer RAG sobre múltiples transcripts.
- **No es un producto público:** uso privado, sin publicación, sin intención de monetizar ni publicar APK en stores.

---

## 2. Los 6 universos (documentos vivos en `docs/universos/`)

Cada decisión deja una línea con fecha y porqué en el universo que corresponda.

| Universo | Archivo | Qué registra |
|----------|---------|--------------|
| Producto | `producto.md` | Qué se construye y por qué (definición del "top 5", criterios de éxito v2.0, CRUD de topics) |
| UX/UI | `ux-ui.md` | Cómo se experimenta (ranking con motivo visible, medidor de contexto, chat UX, mobile-first) |
| Backend | `backend.md` | Cómo funciona (API, pipeline, almacenamiento, búsqueda ES/EN) |
| AI Engineering | `ai-engineering.md` | Cuánto cuesta, qué se aprende, chunking, RAG, modelos, tokenización |
| Project Management | `project-management.md` | Fases, prioridades, tiempos, reglas de cierre de v1 y apertura de v2.0 |
| Frontend | `frontend.md` | Qué se muestra (hoy vacío: sin UI no hay nada que registrar) |

> Mecánica: cada decisión tomada en chat deja una línea `YYYY-MM-DD: <decisión> — <porqué>` en el archivo del universo correspondiente.

---

## 3. Requerimientos funcionales v2.0

### RF1 — Chat agéntico (terminal, por ahora)
Conversación en lenguaje natural que entiende intenciones: "busca", "resume el 2 y el 4", "qué dicen estos videos sobre X". El agente orquesta las herramientas existentes (research, process) en vez de que el usuario corra comandos manuales.

### RF2 — Búsqueda por prompt bilingüe (ES + EN)
Ejemplo: "5 mejores videos en español y 5 en inglés sobre heurísticas en UX".
- Buscar en ambos idiomas (queries ES + EN).
- Aplicar filtros de calidad (vistas, relevancia, canales preferidos).
- Devolver 10 links numerados para elegir.
- **Ranking explicable:** score = métricas 60% + afinidad a canales preferidos 40% (ajustable en `config.yaml`). Cada candidato muestra sus motivos de por qué entró.

### RF3 — Resumen selectivo
Sobre los 10 candidatos, elegir 1, 2 o todos. Solo lo elegido se transcribe/procesa. Control de costo explícito: procesar 10 videos de 1 hora son ~10 llamadas LLM grandes.

### RF4 — Q&A multi-transcript (RAG)
Ejemplo: "¿Qué dicen estos 4 videos sobre onboarding?" → el agente recupera fragmentos relevantes de los 4 transcripts y responde sintetizando, citando de qué video viene cada parte.

### RF5 — Observabilidad AI engineering
Cada llamada LLM registra: tokens in/out, modelo, costo estimado, latencia.
- Feature: ver gastos en tiempo real.
- Laboratorio de aprendizaje: ventana de contexto, chunking, cuándo el RAG ahorra vs. mandar todo el texto.
- Medidor de contexto estilo OpenCode (círculo que se llena, aviso al acercarse al límite).

### RF6 — UI web mobile-first + APK (fase posterior)
Chat, lista de videos, visor de resúmenes. La APK saldrá de la web (envoltorio tipo PWA/Capacitor, a definir cuando toque stack). **No está en v2.0.**

---

## 4. Requerimientos no funcionales

| ID | Requerimiento |
|----|---------------|
| RNF1 | **Costo consciente:** ninguna operación gasta tokens sin confirmación o sin mostrar estimación previa. |
| RNF2 | **Uso personal:** sin publicación; los transcripts son para estudio privado (evita el problema de copyright por diseño). |
| RNF3 | **Evolutivo:** el RAG arranca con lo más simple que funcione (chunking fijo + búsqueda por similitud + SQLite), con métricas para justificar cada complejización. |
| RNF4 | **Separación backend/frontend desde el slice de UI, no antes** (no sobrediseñar ahora). |

---

## 5. Roadmap

| Versión | Alcance | Criterio de éxito |
|---------|---------|-------------------|
| **v2.0** | RF1 + RF2 + RF3 en terminal + RF5 básico (log de tokens en cada respuesta) | El ejemplo "heurísticas en UX" funciona de punta a punta |
| **v2.1** | RF4 (RAG multi-video) + tabla comparativa "con RAG vs sin RAG" en tokens | Aprendizaje de AI engineering con datos reales |
| **v2.2** | Refactor a backend API + UI web (definir stack aquí) | UI funcional |
| **v2.3** | APK mobile | APK instalable en Android |

---

## 6. Decisiones de diseño v2.0

### 6.1 Ranking de videos ("top 5")
- **Score explicable:** métricas (vistas, antigüedad, relevancia) 60% + afinidad a canales preferidos 40%.
- Ajustable en `config.yaml`.
- Cada candidato muestra por qué entró (ej. "entró por alta afinidad al canal X y 1.2M vistas").

### 6.2 Medidor de contexto
- Mostrar tokens en cada respuesta del chat (ej. `[1.2k in / 800 out · $0.002]`).
- Alertar al acercarse al límite de ventana de contexto (estilo OpenCode).

### 6.3 Topics
- Fijos al principio (IA, mercado, estilo de vida).
- CRUD permitido: agregar, modificar, borrar topics desde `config.yaml`.

---

## 7. Skills de `agent-skills` (Addy Osmani) a usar

| Fase | Skill | Para qué |
|------|-------|----------|
| DEFINE | `spec-driven-development` | Escribir el PRD de v2.0 antes de código |
| PLAN | `planning-and-task-breakdown` | Descomponer en tareas atómicas verificables |
| BUILD | `incremental-implementation` | Construir slice por slice sin romper v1 |
| BUILD/VERIFY | `test-driven-development` | Tests antes que código (especialmente RAG y búsqueda) |
| CONTEXTO | `context-engineering` | Decidir qué ir al LLM, chunking, RAG vs. todo el texto |
| FUENTE | `source-driven-development` | Basarse en documentación oficial (YouTube API, Groq, yt-dlp) |

---

## 8. Skills nuevas a crear en `youtube-agent/agent-skills/`

| Skill | Propósito |
|-------|-----------|
| `youtube-chat` | Chat agéntico por terminal: entender intenciones, orquestar tools existentes |
| `youtube-search-bilingual` | Búsqueda ES+EN por prompt, ranking explicable |
| `youtube-selective-summary` | Resumen de 1, 2 o todos los videos elegidos, con control de costo |
| `youtube-rag` | Q&A multi-transcript con citas de origen |
| `youtube-token-monitor` | Log de tokens in/out, modelo, costo estimado, latencia |

---

## 9. Archivos de referencia

- `config.yaml`: categorías, LLM (Groq `gpt-oss-120b`), sponsors, research, output, skills habilitadas.
- `core/pipeline.py`: orquestador actual (metadata → transcript → sponsors → análisis → skills → guardado).
- `core/research.py`: research híbrido actual (API/yt-dlp/RSS, cooldown, digest numerado).
- `skills/`: skills Python existentes (summary, key_points, chapters, quotes, sponsor_cut).
- `agent-skills/`: skills de agente existentes (youtube-processor, youtube-research, youtube-sponsorcut).
- `docs/universos/`: los 6 documentos vivos.

---

## 10. Restricciones consolidadas v2.0 (se deciden una vez, se aplican siempre)

| ID | Restricción | Umbral / regla concreta |
|----|-------------|-------------------------|
| C1 | Tamaño de cambio | Máximo ~100 líneas por commit; un commit = una tarea o sub-tarea |
| C2 | Costo visible | Toda llamada LLM muestra estimación de tokens antes de ejecutar si supera el umbral de `config.yaml` |
| C3 | Sin auto-procesado | Ningún video se transcribe sin elección explícita del usuario (`1, 3` o `todos`) |
| C4 | Config documentada | Ningún cambio en `config.yaml` sin reflejarlo en este documento |
| C5 | No romper v1 | Cada tarea se verifica contra el pipeline existente antes de commitear |
| C6 | Keys fuera del repo | `.env` nunca se commitea; si se filtra una key, se revoca y se rota antes de seguir |

---

## 11. Definición de terminado por tarea

Orden de implementación acordado 2026-10-15: **T4 primero** (es la instrumentación que permite medir T2 y T3).

| Tarea | Terminada cuando... | Cómo se verifica |
|-------|---------------------|------------------|
| T4 — Log de tokens | Cada llamada LLM imprime `tokens in / out / costo estimado / latencia` | Correr `process` sobre un video y ver la línea de tokens al final |
| T1 — Chat lenguaje natural | El programa recibe texto libre y clasifica la intención (buscar / resumir / preguntar) sin comandos rígidos | Escribir "busca videos de X" y "resume el 2" en lenguaje libre y que responda lo correcto |
| T2 — Búsqueda ES/EN | Devuelve 10 links numerados con canal, duración, vistas y motivo de inclusión | Comparar contra búsqueda manual en youtube.com del mismo tema |
| T3 — Resumen selectivo | Solo los videos elegidos se procesan; el resto queda intacto | Elegir `1, 3`, verificar que solo esos aparecen en `index.json` |
| T5 — CRUD topics | Agregar/modificar/borrar un topic sin editar `config.yaml` a mano | CRUD completo desde el chat y persistencia verificada al reiniciar |

---

## 12. Puerta de revisión (antes de dar por hecha cada tarea)

Revisión en 5 ejes, sin excepciones:

1. **Correctitud:** ¿hace lo que dice la definición de terminado?
2. **Claridad:** ¿lo entiende alguien que lee el código por primera vez?
3. **Tests:** ¿hay prueba o verificación que lo demuestre? ("parece que funciona" no alcanza)
4. **Seguridad:** ¿ninguna key, token o dato personal en código, logs o commits?
5. **Costo:** ¿los tokens gastados están medidos y justificados?

Si un eje falla, la tarea vuelve a trabajo. No se acumulan tareas sin revisar.

---

> Estado: **acordado 2026-10-15, en implementación**. Se actualiza desde la sesión de planificación (`tests`) y se consulta desde la sesión de implementación (`youtube-agent`).