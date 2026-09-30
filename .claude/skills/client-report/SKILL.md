---
name: client-report
description: "Reportes de cambios para el cliente (docs/reports/): crea uno en español, no técnico, y prepara asunto, correo y WhatsApp como nota privada del documento. --list tabula; --find busca por tema. Publica al Gestor de Documentos (MCP) si está disponible, confirmando antes de crear/actualizar."
argument-hint: "[--list | --find <descripción> | <instrucciones libres>]"
---

# Client Report — reportes de cambios para el cliente

Cada entrega al cliente se documenta con un **reporte de cambios**: un markdown
en español, **no técnico**, que cita textualmente lo que el cliente reportó,
explica qué se hizo y le da una guía paso a paso para validarlo él mismo. Esta
skill crea esos reportes con el formato estándar del fleet, prepara la comunicación
para entregarlos (asunto, correo y WhatsApp) y también los lista y los busca.

**Cadena:** [[client-message]] corre esta skill como su Phase 4 cuando el operador
pide además el reporte. Invocable suelta para crear/listar/buscar reportes; en modo
create siempre genera el par de comunicación, aunque la salida de esta skill siga
siendo el estado del reporte. La coordenada del Gestor (`gestor:` en
`config/client-comms/clients/<codebase>.yml`) se resuelve y persiste **acá**, no allá.

Una respuesta a un mensaje entrante con discusión de etapa, alcance, aprobación o
cambios pertenece a [[client-response]]. Esa skill guarda su documento formal
directamente en ProjectApp y no crea un archivo bajo `docs/reports/`.

**Convención de almacenamiento (fleet-wide):**
- Carpeta: `docs/reports/` — **versionada en git** (a diferencia de `docs/tmp/`,
  que es para borradores efímeros y está gitignorada). Nota: en
  `vps-ops-toolkit` los reportes viven en `reports/` y `docs/audits/` — esta
  convención es para repos de proyecto.
- Nombre: `<Tema_En_Snake_Case>_DDMMYYYY.md` — la fecha SIEMPRE como **postfijo**
  y SIEMPRE obtenida de `date +%d%m%Y`, nunca asumida.
  Ej.: `Reporte_Respuestas_Reunion_22062026.md`.
- Un reporte por entrega/revisión. Si el mismo tema se re-entrega el mismo día,
  sufijo `_R2`, `_R3` antes de la fecha.

> **⚠️ How to invoke**:
> - `/client-report` → crea el reporte de lo hecho en **esta sesión**.
> - `/client-report enfócate solo en el módulo X y omite Y` → crear, con instrucciones libres.
> - `/client-report --list` → tabla concisa de los reportes existentes.
> - `/client-report --find notificaciones` → busca reportes donde se tocó ese tema.
>
> Claude Code substituye `$ARGUMENTS` con los flags/término pasados (vacío si se omiten).

---

## Phase 0 — Args & discovery

> **Post-`EnterWorktree`: UN comando simple por llamada.** Adentro de un worktree
> nativo, Claude rechaza el comando con `$(...)`, `{a,b}`, `for`/`while` o heredoc con
> sustitución — se cae el bloque entero. Por eso esta skill no parsea ni itera en
> bash: `$ARGUMENTS` lo leés vos y los listados salen de UN `grep` sobre el glob.
> Convención completa: `git-branch-protocol` §1 del CLAUDE.md del repo.

**Args** — los parseás vos leyendo `$ARGUMENTS`:

| Forma | MODE | Qué es el resto |
|---|---|---|
| `--list …` | `list` | — |
| `--find <descripción>` | `find` | el término de búsqueda |
| (texto libre) | `create` | el tema del reporte |

`REPORTS_DIR` es siempre `docs/reports`. **La fecha SIEMPRE del sistema** — regla del
fleet, nunca asumirla. Dos formatos, dos comandos simples: el `DDMMYYYY` del nombre de
archivo y la **fecha legible** que va en el encabezado del reporte (`<fecha legible>`
de la plantilla de la Phase 3):

```bash
date +%d%m%Y
```
```bash
LC_ALL=es_ES.UTF-8 date '+%d de %B de %Y' || date '+%d/%m/%Y'
```

Guard: `docs/reports` debe estar versionado. Si este comando sale `0`, el directorio
está gitignored en el proyecto y hay que corregir el `.gitignore` **antes** de crear
el reporte:

```bash
git check-ignore -q docs/reports
```

Inventario:

```bash
ls -1 docs/reports/*.md
```

---

## Phase 1 — `--list` (solo MODE=list)

Dos `grep` sobre el glob — uno para los títulos, otro para los puntos atendidos; sin
bucle (post-entry un `for` se rechaza) y sin `{n,m}` en el patrón (la llave con coma
es expansión de llaves para el gate de forma, aunque acá sea un cuantificador):

```bash
grep -m1 -H '^# ' docs/reports/*.md
```
```bash
grep -HnE '^(##|###) [0-9]' docs/reports/*.md
```

Claude renderiza UNA tabla concisa:

| Reporte | Fecha | Qué se atendió |
|---|---|---|

- `Reporte`: nombre del archivo (con backticks).
- `Fecha`: derivada del postfijo `DDMMYYYY` del nombre (formato `DD/MM/YYYY`).
- `Qué se atendió`: resumen de los títulos de los puntos, **≤ 1 frase por
  reporte** (agrupa: "espaciado PDF, preview archivados, tabs dashboard…").

> No uses el veredicto 🟢/🟡/🔴 — en modo `--list` la tabla ES la salida.

---

## Phase 2 — `--find <descripción>` (solo MODE=find)

Sin descripción → ❌ `--find requiere una descripción. Ej: /client-report --find notificaciones`.
`<término>` va **literal** en las dos llamadas:

```bash
grep -ilF '<término>' docs/reports/*.md
```
```bash
grep -inHE '^(##|###) ' docs/reports/*.md | grep -iF '<término>'
```

El primero da los archivos que matchean en cualquier parte; el segundo, los títulos de
punto que lo mencionan. Un archivo del primer listado que no aparece en el segundo
matcheó en el cuerpo, no en un título.

Claude reporta cada reporte que matchea con: archivo, fecha y **qué puntos**
tratan el tema (número + título + estado ✅/⏭️/⚠️). Si el término literal no
arroja resultados, reintenta el grep con raíces/sinónimos evidentes del término
(ej. "notificación" → "notificacion", "alerta") antes de declarar "sin
resultados".

---

## Phase 3 — Crear el reporte (MODE=create, default)

1. **Insumos.** La fuente primaria es el **contexto de la sesión actual** (lo que
   se implementó/arregló en esta conversación). Confirma contra el repo con
   `git log --oneline -20` (y `git show --stat <sha>` si hace falta). Si hay
   `$FREEFORM`, respétalo (alcance, énfasis, omisiones). **Nunca inventes
   cambios que no se hicieron**; si un punto quedó a medias, márcalo ⚠️ Parcial
   o 🔄 En curso — el reporte es un compromiso con el cliente.
2. **Clasifica cada punto**: tipo (🐞 bug / 💡 requerimiento-mejora / ❓ duda
   aclarada) y estado (✅ Atendido / ⏭️ Fuera de alcance / ⚠️ Parcial / 🔄 En curso).
3. **Redacta** con la plantilla de abajo. Reglas de estilo:
   - Español, **no técnico**: nada de nombres de funciones, endpoints de API ni
     variables de código. Los módulos y botones se nombran como los ve el
     usuario ("Archivos Jurídicos", "Previsualizar"), no como se llaman en el
     código. **Excepción:** las URLs y rutas navegables SÍ se incluyen — son
     texto que el usuario final ve y usa en el navegador, no jerga técnica.
   - Si existe el texto original del cliente (correo, reporte de bugs, acta),
     cítalo **textualmente** en el blockquote del punto.
   - "Cómo validar que funciona" siempre en **pasos numerados** accionables.
   - "Antes de probar necesitas": rol requerido, datos previos, y desde qué
     vista se empieza.
   - **Sin saltos de línea a mitad de párrafo.** Cada párrafo, ítem de lista,
     cita (`>`) y celda de tabla va en **una sola línea física**, por larga que
     sea — no envuelvas el texto manualmente a ~80 columnas. El cliente suele
     abrir el `.md` en visores que respetan los saltos duros, y un wrap a media
     frase se ve como un corte raro. La separación entre bloques se hace con
     **líneas en blanco**, nunca partiendo una frase.
   - **Asumí que quien valida es un usuario nuevo que no conoce el sistema.** No
     des nada por obvio: nombrá el menú, la pestaña y el botón exactos con el
     texto tal cual aparece en pantalla (en **negrita**), y describí el
     **resultado observable** esperado en cada paso. Si un botón muestra texto
     en inglés, ponelo con su traducción.
   - **Siempre incluí las URLs.** Cada punto debe indicar la URL donde (a) se
     presentaba el problema y (b) se valida el arreglo. Declará **una vez** la
     URL base del ambiente de pruebas en la cabecera; en cada punto, el **primer
     paso** de validación da la **URL completa** para llegar (lista para
     copiar/pegar) y los pasos siguientes usan nombres de pestañas/botones.

   **Cómo obtener las URLs reales (no las inventes):**

   ```bash
   # URL base del ambiente de pruebas — fuentes no circulares primero:
   grep -h 'domain:' ~/webapps/vps-ops-toolkit/projects.yml 2>/dev/null        # projects.yml del fleet (campo domain:)
   grep -h 'ALLOWED_HOSTS' backend/.env .env 2>/dev/null                       # hosts reales del ambiente
   # Reportes anteriores (fuente circular — sólo como último recurso):
   grep -rhoE 'https?://[a-z0-9.-]+\.(projectapp\.co|com)[^[:space:])"]*' docs/reports/ 2>/dev/null | sort -u
   # Ruta exacta de cada vista/módulo (Vue router / Django urls):
   grep -rnE "path:[[:space:]]*[\"']" frontend/src/router/ 2>/dev/null   # SPA Vue
   grep -rnE "path\(|re_path\(" backend/*/urls.py 2>/dev/null            # Django
   ```

   Si no encontrás la URL base con seguridad, preguntá al operador una vez;
   nunca la inventes.
4. **Guard de worktree (antes de escribir):** `git rev-parse --show-toplevel`
   debe caer bajo `~/webapps/.wt/`. Si cae en el clon principal del proyecto,
   creá tu worktree de sesión ANTES de seguir — `session-worktree.sh create
   docs <slug>` (o tmpl §5) — y entrá (Claude: `EnterWorktree`; Codex: `cd`).
   Si la sesión YA tiene su worktree de un turno anterior, seguí usándolo.
5. **Escribe el archivo** (ya dentro del worktree):

```bash
mkdir -p docs/reports
```

El archivo es `docs/reports/<Tema_En_Snake_Case>_<DDMMYYYY>.md` — el tema lo decide
Claude según el contenido (corto, descriptivo) y la fecha es la que imprimió Phase 0.
Si ya existe, sufijo de revisión: `<Tema>_R2_<DDMMYYYY>.md`, `_R3`, …

6. **NO commitees automáticamente.** El operador decide cuándo y cómo. El
   archivo viaja en la rama/PR de la sesión — `/git-commit` desde el worktree
   hace commit + push + PR. Sí sugiere el commit en Next steps.

---

## Phase 3B — Preparar la nota privada para el cliente (solo MODE=create)

Todo reporte nuevo o actualizado lleva una comunicación lista para enviar, guardada
como metadata privada del mismo documento y **nunca dentro del markdown/PDF**:

- `client_email_subject`: el asunto sin el prefijo `Asunto:`.
- `client_email_body`: el cuerpo completo del correo, desde el saludo hasta la firma;
  no duplica el asunto.
- `client_whatsapp_message`: el WhatsApp breve.

Generá los tres textos con el perfil del cliente y las reglas de las Phase 5 y 6 de
[[client-message]]. Esta es una subrutina **no recursiva**: no ejecutes el gating ni la
Phase 4 de `client-message`, y nunca generes un segundo reporte. Si esta skill fue
encadenada por `client-message`, reutilizá sus insumos verificados y su perfil ya
resuelto. Si fue invocada directamente, resolvé sólo el perfil necesario siguiendo su
Phase 0; no preguntes si se desea reporte porque ya se está creando uno.

El correo debe nombrar el título real del reporte creado en Phase 3. Conservá los tres
valores exactos durante el resto de la corrida: son los que se publican en Phase 4 y,
en una ejecución encadenada, los que `client-message` devuelve. **No redactes dos
versiones equivalentes** porque la copia mostrada al operador debe coincidir byte por
byte con la nota guardada.

---

## Phase 4 — Publicar en el Gestor de Documentos (MCP) — solo MODE=create

Tras escribir el `.md` local (Phase 3), publicá el reporte en el **Gestor de
Documentos** (MCP `Gestor de Documentos`), que lo versiona y genera el PDF con marca.
El `.md` en `docs/reports/` sigue siendo la fuente; este paso lo sincroniza al gestor.

**Precondición — disponibilidad del conector.** Este paso requiere las tools del
conector "Gestor de Documentos" en la sesión — nombre MCP completo:
`mcp__claude_ai_Gestor_de_Documentos__list_folders`, y con el mismo prefijo
`…__list_documents`, `…__read_document`, `…__create_folder`, `…__create_document`,
`…__update_document` — un conector claude.ai del operador. Si NO están disponibles
(sesión sin el conector o runtime sin acceso), **SALTAR** el paso: dejar constancia en el output (`Gestor de
Documentos: n/a en esta sesión`) y terminar con el reporte local. **Nunca falles por
esto.**

1. **Carpeta destino según el prompt/proyecto.**
   - **Primero, la coordenada persistida.** Leé
     `$HOME/webapps/vps-ops-toolkit/config/client-comms/clients/<codebase>.yml`
     (donde `<codebase>` es `basename -s .git` del `remote.origin.url` de este repo).
     Si trae un bloque `gestor:` con `folder_id`, **usalo sin preguntar** y saltá al
     punto 2 — ya se resolvió una vez y se guardó. El campo `gestor.naming` dice qué
     patrón de nombre usa esa carpeta; respetalo en vez de imponer el default.
     Si el prompt nombra explícitamente otra carpeta, ESA manda igual.
   - Si no hay coordenada guardada, deducí el proyecto/cliente del contexto de la
     sesión y de `$FREEFORM` (p.ej.
     "Vastago Project", "Xpandia Project") — el nombre que ve el cliente, no el del
     directorio del repo. Si el prompt nombra explícitamente una carpeta/subcarpeta,
     ESA manda.
   - `list_folders` → localizá la carpeta del proyecto (match por nombre, insensible a
     mayúsculas/acentos) y, dentro, la subcarpeta correcta para reportes de cambios
     (p.ej. "Feedback and Fixes", "Fixes", o la que indique el prompt). No hay una
     convención de subcarpeta fija en el fleet: **resolvé por prompt** y ante duda,
     preguntá.

2. **¿Ya existe el reporte?**
   - `list_documents(folder_id=<destino>)` → ¿hay un documento cuyo título corresponda
     a este reporte (mismo tema)? Si hay candidato, `read_document` para confirmar que
     es el mismo antes de decidir crear vs. actualizar.

3. **Decidir y CONFIRMAR con el operador (obligatorio, sin excepción):**
   - **Existe → ACTUALIZAR.** Antes de `update_document`, mostrá EXACTAMENTE qué se va a
     actualizar: `document_id`, título, carpeta, un resumen de qué cambia en el
     contenido (qué secciones/puntos) y que se reemplazarán los tres campos de la
     nota privada. Esperá confirmación explícita. Recién ahí
     `update_document(document_id=…, markdown=<cuerpo del reporte>,
     client_email_subject=…, client_email_body=…,
     client_whatsapp_message=…)`.
   - **No existe → CREAR, pero PREGUNTÁ ANTES.** Nunca crees documento ni carpeta sin
     preguntar. Mostrá: carpeta destino (y si hay que CREARLA porque falta la del
     proyecto o la subcarpeta, decilo explícito), título propuesto, `language="es"`,
     `client_name` y que se guardará la nota privada con asunto, correo y WhatsApp.
     Esperá confirmación. Recién ahí, en orden:
     - si el operador aprueba crear carpeta: `create_folder(name=…, parent_id=…)`;
     - `create_document(title=…, markdown=<cuerpo del reporte>, folder_id=…,
       language="es", client_name=…, client_email_subject=…,
       client_email_body=…, client_whatsapp_message=…)`.

   **Reglas de confirmación:** (a) preguntar SIEMPRE antes de crear algo nuevo (carpeta
   o documento); (b) al actualizar, confirmar qué documento y qué contenido se
   sobrescribe; (c) ante ambigüedad (varias carpetas/documentos candidatos), NO
   adivines — preguntá.

4. **Contenido y nota.** El markdown que subís es el MISMO cuerpo del reporte de
   Phase 3 (la plantilla del cliente), no un resumen. Los tres valores de Phase 3B
   viajan en sus campos separados y no se insertan en el markdown. El gestor convierte
   únicamente el reporte a PDF.

   Si el conector no está disponible o el operador omite la publicación, la nota queda
   generada pero no persistida: declaralo explícitamente en el output. Nunca afirmes que
   fue guardada si `create_document`/`update_document` no terminó correctamente.

5. **Persistí la coordenada** (sólo si en el punto 1 hubo que resolverla preguntando).
   Escribí el bloque `gestor:` en
   `$HOME/webapps/vps-ops-toolkit/config/client-comms/clients/<codebase>.yml`
   (creando el archivo si falta) para que la próxima corrida no vuelva a preguntar
   el destino:

   ```yaml
   gestor:
     folder_id: <id real>
     folder_path: "<Cliente> Project / <subcarpeta>"
     naming: "<patrón observado en esa carpeta>"
   ```

   El `naming` se deriva de los títulos que ya viven en la carpeta (`list_documents`)
   — la convención NO es uniforme entre clientes y se respeta, no se normaliza.
   No commitees: dejá el cambio visible para `/git-commit` (este archivo vive
   en el toolkit — flujo trunk, commit directo a master, sin worktree). Schema
   completo en `config/client-comms/README.md`.

---

## Plantilla del reporte (usar literal, ajustando contenido)

```markdown
# Reporte de cambios — <contexto de la entrega> (<fecha legible>)

> <1–3 líneas de contexto: de dónde salen estos puntos (correo, reunión,
> reporte de bugs), proyecto y ambiente donde se pueden probar.>

**Convenciones:**
- 🐞 = bug reportado
- 💡 = requerimiento / mejora de UX
- ❓ = duda del cliente que se aclara
- ✅ Atendido | ⏭️ Fuera de alcance | ⚠️ Parcial | 🔄 En curso

**Ambiente de pruebas:** <URL base del staging, ej. `https://proyecto.projectapp.co`>. Iniciá sesión en <URL base>/<ruta de login, ej. `/sign_in`> con una cuenta de <rol>.

**Para todas las pruebas:** <requisito global: datos previos, rol si varía por punto.>

---

## Resumen rápido

| Clasificación | Cantidad |
|---|---:|
| ✅ Atendido | N |
| ⏭️ Fuera de alcance | N |
| **Total puntos** | **N** |

| # | Punto | Estado |
|---|---|---|
| 1 | <título corto> | ✅ Atendido |

---

## 1. ✅ Atendido — 🐞 <Título del punto>

> **Observación del cliente:** "<cita textual>"

**Qué se hizo:** <explicación no técnica. Si ayuda, usar el par
**Antes:** / **Ahora:** para contrastar comportamiento.>

**Dónde se ve / URL:** <URL completa, ej. `https://proyecto.projectapp.co/ruta?tab=…`> — <breadcrumb: Módulo → pestaña → sección donde ocurría y donde se valida>.

**Antes de probar necesitas:**
- <rol con el que ingresar>
- <datos o estado previo necesario>
- <la URL exacta desde donde empezás (la de arriba)>

**Cómo validar que funciona:**
1. Abre <URL completa> (si no iniciaste sesión, primero te llevará al login).
2. <paso: nombrá la pestaña/botón literal en **negrita** y el resultado visible>
3. <resultado final esperado, observable y sin ambigüedad>

---

## Cierre

| Categoría | Total puntos | ✅ Atendidos | ⚠️ Parciales | ⏭️ Fuera de alcance |
|---|---|---|---|---|
| <categoría> | N | N | N | N |
| **TOTAL** | **N** | **N** | **N** | **N** |

<Frase de cierre: quedamos atentos a dudas/ajustes.>
```

---

## Acciones disponibles

Tras el reporte (modo create), si la sesión es interactiva y NO hubo flags
explícitos (reglas de gating de [[_output-protocol]] §4), ofrecer vía
AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| Listar reportes existentes | tabla concisa de `docs/reports/` (read-only) | `/client-report --list` |
| Buscar por tema | busca en qué reportes se tocó un tema | `/client-report --find <tema>` |
| Publicar en Gestor de Documentos | sube el .md al gestor (pide confirmación como siempre antes de crear/actualizar) | `/client-report publicá en el Gestor el reporte recién creado` |
| Commitear el reporte | add+commit+push+PR del reporte recién creado, desde el worktree de sesión | `/git-commit` |

---

## Output final

Reportar siguiendo [[_output-protocol]]. Plantilla específica:

```markdown
🟢 client-report OK — <archivo> creado
| Dimensión | Estado | Detalle |
|---|---|---|
| Phase 0 — Args | ✅ | MODE=create, fecha DDMMYYYY del sistema |
| Phase 3 — Insumos | ✅ | N puntos (sesión + git log) |
| Plantilla | ✅ | citas textuales + validación paso a paso |
| Nota privada | ✅ | asunto + correo + WhatsApp guardados / generados sin persistir |
| Phase 4 — Gestor de Documentos | ✅ | creado id=… / actualizado id=… / n/a (sin conector) / omitido por operador |
| Git | ⚠️ | sin commitear (decisión del operador) |

## Next steps
- `git add docs/reports/<archivo> && git commit -m "docs(reports): ..."`

Report path: docs/reports/<archivo>.md
```

- En modo **create**, la ÚLTIMA línea de la respuesta es SIEMPRE la literal
  `Report path: docs/reports/<archivo>.md`.
- En modos `--list`/`--find` no hay veredicto: la tabla/los matches SON la salida.

---

## Notas de fleet

- Fuente canónica: `vps-ops-toolkit/workflows/.claude/client-report.md`. La
  copia generada en `.agents/skills/` adapta el frontmatter para Codex.
- La convención `docs/reports/` + `_DDMMYYYY` es fleet-wide: aplica igual en
  todos los proyectos que reciben esta skill.
- `docs/tmp/` sigue siendo el espacio de borradores (gitignorado); lo que se
  entrega al cliente vive en `docs/reports/` y se commitea.
