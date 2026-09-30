---
name: client-message
description: "Redacta el par correo + mensaje de WhatsApp para avisarle algo a un cliente: envío de un documento, entrega o aprobación ya resuelta. El correo lleva asunto y cuerpo completo; el WhatsApp es breve. Opcionalmente genera el reporte de cambios y guarda ese mismo par como nota privada del documento en el Gestor. Si no se pasa el tema, pregunta proponiendo lo último trabajado. Para analizar y responder un mensaje entrante usa client-response. Devuelve texto en español para copiar y pegar; no envía nada."
allowed-tools: Bash, Read, Write, AskUserQuestion, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__claude_ai_Gestor_de_Documentos__list_folders, mcp__claude_ai_Gestor_de_Documentos__list_documents, mcp__claude_ai_Gestor_de_Documentos__read_document, mcp__claude_ai_Gestor_de_Documentos__create_folder, mcp__claude_ai_Gestor_de_Documentos__create_document, mcp__claude_ai_Gestor_de_Documentos__update_document
argument-hint: "[tema del mensaje — ej: 'avisar que se envió el OTROSÍ y resumir qué contiene' | vacío = pregunta]"
---

# Client Message — el correo + el WhatsApp para el cliente

Cuando hay algo que avisarle a un cliente —se le envió un documento, quedó lista
una entrega, se respondieron sus observaciones— hacen falta **dos textos, no uno**:
el correo que lleva el contenido, y el WhatsApp que lo empuja a abrir el correo.

Esta skill devuelve ese par, en español no técnico, listo para copiar y pegar.
Opcionalmente encadena el **reporte de cambios** delegando en [[client-report]];
cuando lo hace, el mismo asunto, correo y WhatsApp quedan como nota privada del
documento en el Gestor.

Si el punto de partida es un mensaje entrante que exige reconstruir el hilo,
separar etapas, decidir alcance o pedir aceptación, el flujo correcto es
[[client-response]]. Esta skill queda para avisos salientes cuyo fondo ya está
resuelto.

> **La diferencia en una línea: el correo es el documento; el WhatsApp es el
> golpecito en el hombro.**

> **⚠️ Cómo invocar**:
> - `/client-message avisarle que se le envió el OTROSÍ y resumirle qué contiene`
>   → **redacta directo**, sin preguntar el tema.
> - `/client-message` → pregunta de qué se trata, proponiendo lo último que se trabajó.
> - En lenguaje natural: *"dame un correo y un whatsapp para avisarle al cliente
>   que ya quedó"* → se auto-invoca.
>
> Claude Code sustituye `$ARGUMENTS` con lo que se haya pasado (vacío si se omite).

**Se invoca parado dentro del repo del cliente** — de ahí salen los insumos
(`git log`, `docs/reports/`). El perfil de firma y la coordenada del Gestor viven
en el toolkit (ver "Persistencia").

---

## Phase 0 — Discovery (read-only, corre SIEMPRE)

```bash
set -o pipefail
ARGS="$ARGUMENTS"

TOOLKIT="$HOME/webapps/vps-ops-toolkit"
[ -d "$TOOLKIT" ] || TOOLKIT="$(ls -d /home/*/webapps/vps-ops-toolkit 2>/dev/null | head -1)"
PROFILE="$TOOLKIT/config/client-comms/profile.yml"

# La fecha SIEMPRE del sistema — regla del fleet, nunca asumirla.
FECHA=$(date +%d%m%Y)
FECHA_LEGIBLE=$(LC_ALL=es_ES.UTF-8 date '+%d de %B de %Y' 2>/dev/null || date '+%d/%m/%Y')

# Identidad del repo → clave de cliente (MISMA convención que config/qa-memory/)
ORIGIN=$(git config --get remote.origin.url 2>/dev/null)
CODEBASE=$(basename -s .git "${ORIGIN:-$(pwd)}")
CLIENT_FILE="$TOOLKIT/config/client-comms/clients/${CODEBASE}.yml"

echo "=== FECHA: $FECHA_LEGIBLE  ($FECHA)"
echo "=== CODEBASE: $CODEBASE   rama: $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
echo "=== ARGS: ${ARGS:-(vacío)}"
echo "=== TOOLKIT: ${TOOLKIT:-(NO ENCONTRADO)}"
echo "=== PERFIL FLEET:";   [ -f "$PROFILE" ]     && cat "$PROFILE"     || echo "(NO EXISTE — primera corrida)"
echo "=== PERFIL CLIENTE:"; [ -f "$CLIENT_FILE" ] && cat "$CLIENT_FILE" || echo "(sin override para $CODEBASE)"
echo "=== CANDIDATOS DE FIRMA (sólo se usan si el perfil no existe):"
git config user.name; git config user.email
echo "=== ÚLTIMO TRABAJO:"
git log --oneline -15 2>/dev/null
git log -3 --format='%h %ad %s' --date=short --stat 2>/dev/null | head -40
echo "=== ÚLTIMOS REPORTES AL CLIENTE:"
ls -1t docs/reports/*.md 2>/dev/null | head -5
echo "=== DOMINIO DEL PROYECTO:"
grep -A6 -E "name:[[:space:]]+\"?${CODEBASE}\"?$" "$TOOLKIT/projects.yml" 2>/dev/null | grep 'domain:' | head -2
```

**Regla de contexto:** si `CODEBASE = vps-ops-toolkit`, la opción "lo último
trabajado" **no se ofrece** (esos commits son de infraestructura, no hay cliente
detrás) y **el flujo de reporte se desactiva**. El tema se pide siempre.

---

## Cómo invocar este skill (gating de preguntas)

Reglas, evaluadas **en este orden**. Son el corazón de la skill:

1. **`$ARGUMENTS` no vacío → PROHIBIDO preguntar el tema.** El tema *es*
   `$ARGUMENTS`. Se redacta directo: sin picker, sin "¿confirmás?", sin "¿te
   referís a…?". Si falta un dato menor, se marca con `[…]` en el borrador y se
   lista al final — **nunca** se convierte en una pregunta.
2. `$ARGUMENTS` vacío pero la intención es clara por la sesión (se acaba de
   implementar o arreglar algo concreto en esta conversación, o el operador lo
   describió en su mensaje anterior) → **no abrir picker**: proponer en una línea
   (`Voy a redactar sobre: <tema>`) y esperar confirmación en texto. Regla 2 de
   [[_output-protocol]] §4.
3. `$ARGUMENTS` vacío y sin intención clara → disparar la `AskUserQuestion`.
4. **Nunca** preguntar en modo fleet/headless/cron.
5. **El perfil ausente NO abre un segundo turno**: va como pregunta adicional de
   la *misma* llamada. Si `$ARGUMENTS` trae tema pero falta el perfil, se pregunta
   **sólo la firma** — la regla 1 aplica al tema, no a la config, que se pregunta
   una vez en la vida.
6. **Misma lógica para el reporte:** si el contexto o `$ARGUMENTS` ya dicen que hay
   que generarlo y de qué (ej. *"…y hacé el reporte de los fixes de esta semana"*),
   **no se pregunta**. Si no, entra como pregunta de esta misma llamada.
7. Si la opción elegida no trae los hechos necesarios (la skill no puede saber qué
   dice el OTROSÍ), se piden en **texto plano, una sola vez, todo junto en ≤3
   bullets** — nunca un segundo `AskUserQuestion`.

### `AskUserQuestion` #1 — hasta 3 preguntas en UNA sola llamada

**P1 "Tema"** — sólo si no quedó resuelto por las reglas 1–2.

| label | description |
|---|---|
| `Lo último trabajado` | **Se rellena en runtime desde Phase 0, nunca literal.** Formato: `"<resumen no técnico de los últimos commits> (últimos N commits, <fecha del más reciente>). Aviso de entrega + qué puede revisar."` Ej.: `"Ajustes al módulo de Archivos Jurídicos y al buscador (últimos 3 commits, 28/07). Aviso de entrega + qué puede revisar."` **Se omite** si `CODEBASE = vps-ops-toolkit` o si `git log` vino vacío. |
| `Envío de un documento` | Le avisás que se le envió un documento (OTROSÍ, contrato, propuesta, factura) y le resumís qué contiene. |
| `Respuesta a lo que reportó` | Respondés los puntos que el cliente reportó por correo o WhatsApp y le decís qué quedó atendido. |
| `Coordinar o pedirle algo` | Le pedís información, aprobación, firma o una reunión para poder avanzar. |

**P2 "Firma"** — sólo en la primera corrida, cuando `profile.yml` no existe. Las
descriptions se **rellenan en runtime** con `git config user.name` / `user.email`
para que la elección sea decision-complete:

| label | description |
|---|---|
| `Nombre + agencia` | Cierra con «`<user.name>`» y el nombre de tu agencia. Detectado de git config; si no es exacto, elegí Other y escribí el bloque tal cual. |
| `Sólo tu nombre` | Cierra sólo con «`<user.name>`». El más liviano; sirve para clientes de trato frecuente. |
| `Nombre + cargo + agencia` | El más formal. Para contratos, otrosíes y temas de dinero. |
| `Sin bloque de firma` | Termina en la despedida. El correo ya sale desde tu cuenta y con eso alcanza. |

(`Other` → el operador pega el bloque literal, que se guarda en `firma.literal`.)

**P3 "¿Reporte?"** — salvo que el contexto ya lo haya resuelto (regla 6) o
`CODEBASE = vps-ops-toolkit`:

| label | description |
|---|---|
| `No, sólo correo + WhatsApp` | Lo más común: avisar un envío o coordinar algo no necesita documento. |
| `Sí, reporte de cambios` | Genera además el documento con la plantilla del fleet, lo guarda en `docs/reports/` y lo publica en el Gestor de Documentos (pide confirmación antes de crear o actualizar). |

**El tratamiento (usted/tú) NO se pregunta.** Default `usted` — cliente de agencia
en Colombia: nunca es incorrecto. Queda escrito en `profile.yml` con un comentario
que dice cómo cambiarlo, y es sobreescribible per-cliente. Una pregunta menos en el
único momento de fricción de la skill.

---

## Phase 2 — Persistir el perfil (sólo si el gating preguntó la firma)

```bash
mkdir -p "$TOOLKIT/config/client-comms/clients"
if [ -f "$PROFILE" ]; then
  echo "perfil ya existe — no se sobrescribe"
else
  cat > "$PROFILE" <<'YAML'
# (contenido de abajo, con las respuestas del operador interpoladas)
YAML
  echo "✅ perfil guardado en $PROFILE"
fi
git -C "$TOOLKIT" status --short config/client-comms/
```

La skill **no commitea**: deja el `status --short` visible para que el operador lo
haga con `/git-commit`.

---

## Phase 3 — Insumos verificables

- `git show --stat <sha>` de los commits del tema (si el tema es "lo último trabajado").
- `Read` de los 1–2 `docs/reports/*.md` más recientes: **heredar el tono** y
  **evitar repetir lo que ya se le contó**.
- URL / dominio desde `projects.yml` (campo `domain:`) — **nunca inventarla**.
- **MCP opcional, todo read-only:**
  - `Gmail search_threads` / `get_thread` → nombre real del contacto y asunto del
    hilo previo (para que el correo enganche con la conversación existente).
  - `Gestor de Documentos list_documents` / `read_document` → nombre exacto del
    documento que se le envió.
  - **Guardrail:** si el conector no está en la sesión, **SALTAR**, dejar una línea
    de constancia y seguir. **Nunca fallar por esto.**

**Regla de cierre de fase:** cada afirmación que vaya a entrar al correo tiene una
fuente concreta — sesión, commit, reporte previo, documento, o `$ARGUMENTS`. Lo que
no la tiene, **no entra**.

---

## Phase 4 — Reporte de cambios (opcional, sólo si el gating dijo que sí)

> **Orden no negociable: esta fase va ANTES de mostrar el correo**, porque éste
> referencia el reporte ("te envié el reporte con…") y necesita su nombre real.

**Se delega en [[client-report]] — no se reimplementa nada de esto.** Aplicá su
procedimiento tal cual: su Phase 3 (crear el reporte con la plantilla del fleet en
`docs/reports/<Tema_En_Snake_Case>_DDMMYYYY.md`), su Phase 3B (preparar la nota
privada) y su Phase 4 (publicar reporte + nota en el Gestor de Documentos), usando
como insumos los que ya reuniste en la Phase 3 de acá.

De `client-report` se hereda **todo** lo del reporte y del Gestor, incluida la
resolución y persistencia de la coordenada (`gestor:` en
`config/client-comms/clients/<codebase>.yml`): leerla si ya existe y no preguntar,
resolverla con `AskUserQuestion` sobre carpetas reales si falta, proponer crear la
jerarquía si el proyecto todavía no tiene carpeta, y guardarla al publicar.
**No dupliques esa lógica acá.** Si algo de eso hay que cambiar, se cambia en
`client-report` y esta skill lo hereda.

Lo único que aporta esta fase es el **encadenamiento**: correrla antes del output y
recibir el nombre, la ubicación y los tres textos exactos de la nota. Las Phase 5 y
6 de esta skill muestran esos valores; **no los vuelven a redactar**.

---

## Phase 5 — El correo

Si hubo reporte, usá exactamente `client_email_subject` y `client_email_body`
producidos por la Phase 3B de [[client-report]]: el primero va después de `Asunto:`
y el segundo debajo, sin cambios. Si no hubo reporte, redactalos ahora con esta
plantilla y estas reglas.

```
Asunto: <5 a 9 palabras, concreto, sin "Re:" y sin mayúsculas sostenidas>

<Saludo>, <contacto>:

<Párrafo 1 — la noticia en la primera línea: qué se envió, qué quedó listo, qué pasó.>

<Bloque 2 — el detalle. Si son 3 o más puntos, viñetas; si son 1 o 2, párrafo corrido.>
- <punto: qué es y qué implica PARA ÉL, no cómo se hizo>

<Párrafo 3 — qué necesitás de él, si aplica: revisar, firmar, responder, aprobar. UNO solo y explícito.>

<Despedida del perfil>

<Firma según perfil>
```

- **150–300 palabras.** Arriba de 350 sobra contexto.
- **Sin saltos de línea a mitad de párrafo:** cada párrafo, viñeta y cita va en
  **una sola línea física**, por larga que sea. La separación entre bloques es con
  línea en blanco, nunca partiendo una frase.
- Español **no técnico**: los módulos y botones se nombran **como los ve el
  cliente** ("Archivos Jurídicos", "Previsualizar"), no como se llaman en el código.
  **Excepción:** las URLs sí van — son navegables, no jerga.
- El documento se nombra **igual que como se lo envió** ("el OTROSÍ", no "el anexo
  modificatorio").
- **Sin emojis**, ni en el asunto ni en el cuerpo.
- Sin nombre de contacto conocido → saludo neutro (`Buen día:`). **Nunca** un
  placeholder `[Nombre]` en el saludo: es justo lo que se olvida de reemplazar.

## Phase 6 — El WhatsApp

Si hubo reporte, usá exactamente `client_whatsapp_message` producido por la Phase
3B de [[client-report]]. Si no hubo reporte, redactalo ahora con esta plantilla y
estas reglas.

```
<Saludo corto>, <contacto>. <Una frase: te envié un correo con X.>

Ahí vas a encontrar:
- <3 a 5 palabras>
- <3 a 5 palabras>
- <3 a 5 palabras>

<Cierre de una línea: qué esperás de él, o quedo atento.>
```

- **40–80 palabras. Techo duro: 90.** Tiene que entrar en una pantalla de celular
  sin "ver más".
- **No repite el correo: lo anticipa.** Las viñetas son etiquetas de contenido, no
  resúmenes.
- Sin asunto, sin firma, sin despedida formal — "Cordialmente" no va.
- Mismo tratamiento (usted/tú) que el perfil, **un escalón más cercano** en registro.
- Emojis según `tono.emojis_whatsapp`; default `pocos` = máximo 1, y **cero** en
  temas de contrato, otrosí o dinero.
- Nunca URLs largas: si hace falta, "te lo dejé en el correo".
- El documento se nombra exactamente igual que en el correo.

**Ambos textos van en bloques de código con texto plano, sin markdown de énfasis
adentro** — los asteriscos salen literales al pegarlos en Gmail y en WhatsApp.

---

## Persistencia — perfil de firma y coordenadas

Precedente en el repo: `config/qa-memory/` (memoria de skill, en el toolkit,
versionada, con README de schema, escrita por la propia skill).

| Ruta | Qué guarda |
|---|---|
| `config/client-comms/profile.yml` | Identidad y tono del operador, fleet-wide |
| `config/client-comms/clients/<codebase>.yml` | Override per-cliente: nombre del cliente, contacto, tono **y la coordenada del Gestor** |

Clave del archivo per-cliente: `basename -s .git remote.origin.url` — misma
convención que `config/qa-memory/`. **Precedencia campo a campo: cliente > fleet >
default de la skill.** No hay parser: el YAML se `cat`ea al contexto en Phase 0.

**Vive en el toolkit y no en cada repo** por tres razones: `sync-shared-skills.sh`
sobrescribe las skills distribuidas **sin backup**; los datos del cliente (contacto,
notas de tono) no deben quedar dentro del repo que el cliente eventualmente ve; y el
toolkit resuelve al mismo path en dev y en todo VPS, así que se contesta una vez y
sirve en todos lados. `sync-shared-skills.sh` **no toca `config/`**.

**Degradación (nunca falla):**

- **Sin toolkit alcanzable** → defaults (`solo_nombre` desde `git config user.name`,
  `tratamiento: usted`), redacta igual, avisa `Perfil no persistido — la firma se
  volverá a preguntar` y el veredicto baja a 🟡.
- **Perfil incompleto o corrupto** → usa lo que se pueda leer, completa con
  defaults, **no lo reescribe** y no vuelve a preguntar.
- **Override del cliente ausente** → caso normal y silencioso. **No se crea solo**,
  salvo que se resuelva una coordenada del Gestor o el operador lo pida
  explícitamente ("acordate que a este cliente se le habla de tú").

---

## Guardrails

1. **No inventar hechos.** Todo sale de la sesión, `git log`/`git show`,
   `docs/reports/`, un documento nombrado por el operador, o `$ARGUMENTS`. Un dato
   faltante (número de otrosí, valor, fecha de firma) va como `[…]` visible y se
   lista al final. Nunca se rellena con algo plausible.
2. **No enviar nada.** Ni borrador de Gmail, ni msmtp, ni MCP de envío.
   `create_draft` está fuera de `allowed-tools` a propósito.
3. **No escribir archivos del proyecto**, salvo el reporte de Phase 4 en `docs/reports/`.
   Guardar su nota privada en el mismo documento del Gestor forma parte de esa
   publicación; no autoriza escribir ni enviar mensajes por otra vía.
4. **No commitear** — ni el toolkit ni el repo del proyecto.
5. **No prometer fechas ni plazos**, salvo cita textual del operador en esta sesión.
6. **Cero jerga técnica:** nada de branch, commit, hash, endpoint, migración,
   deploy, staging, PR, refactor. Traducción obligatoria ("se subió al ambiente de
   pruebas", no "deploy a staging").
7. **No exponer la trastienda:** errores propios, retrabajos, caídas, causas
   técnicas. Se comunica el estado actual, no cómo se llegó — salvo pedido explícito.
8. **No prometer alcance no acordado** ("y de paso le agregamos X").
9. **No mezclar clientes:** nunca leer ni citar el `clients/<otro>.yml`, ni reportes
   de otro repo.
10. **La fecha SIEMPRE de `date`.** Nunca asumida.
11. **Guardrail MCP:** conector ausente → SALTAR, una línea de constancia, seguir.
    Si el reporte se pidió y el Gestor no está, se escribe igual el `.md` local y se
    avisa `Gestor de Documentos: n/a en esta sesión`.
12. **Nunca crear carpeta ni documento en el Gestor sin confirmación explícita.** Esta
    skill tiene los tools de escritura del Gestor en `allowed-tools`, pero las reglas
    de qué se crea y dónde son de [[client-report]] — no las reinterpretes acá.
13. **`$ARGUMENTS` con tema → no preguntar el tema.** Ni picker, ni confirmación.
14. **Un par por corrida:** un correo y un WhatsApp. Si el tema da para dos avisos
    distintos, elegir el más urgente y decirlo en una línea.
15. **Nunca meter el WhatsApp dentro del correo ni viceversa.**
16. **Sin `[…]` sin declarar:** todo placeholder que quede en el texto aparece en la
    lista final. Con placeholders el veredicto **nunca** es 🟢.
17. **Una sola versión cuando hay reporte:** el asunto, cuerpo y WhatsApp del output
    son exactamente los tres campos enviados al Gestor. Si la publicación fue
    omitida o falló, se devuelven igual pero se declara que no quedaron persistidos.

---

## Output final

Excepción **output-es-el-producto** de [[_output-protocol]] (§2, "Excepción: skills
cuyo output ES el producto"): los dos textos SON el entregable y se le pegan tal cual
a un cliente no técnico. Esta skill cierra **SIN tabla de dimensiones** (§2) y **SIN
Next steps técnicos** (§3) — sólo la línea de veredicto (§1).

Orden exacto de la respuesta. Nada antes del primer encabezado, nada entre los bloques:

````markdown
### Correo

```
Asunto: <…>

<cuerpo completo, texto plano, sin markdown de énfasis>
```

### WhatsApp

```
<mensaje corto, texto plano>
```

— fin de los textos —

<Datos que faltan — SÓLO si quedó algún `[…]`. Máx 3 bullets: qué dato va y en qué parte.>

<Si hubo reporte: UNA línea con la ruta local, el destino en el Gestor y el estado de la nota privada.>

🟢 client-message OK — correo + WhatsApp listos para copiar
````

Veredictos:

- `🟢 client-message OK — correo + WhatsApp listos para copiar` — sin `[…]`
  pendientes y con perfil resuelto.
- `🟡 client-message OK con N dato(s) por completar` — quedó al menos un `[…]`, o el
  perfil no se pudo persistir, o el Gestor no estaba disponible.
- `⏭️ client-message — N/A` — se invocó en modo fleet/headless (no hay a quién
  preguntarle ni a quién entregarle el texto).

**No hay sección `## Acciones disponibles`.** El operador ya tiene el producto; un
menú post-run es exactamente el ruido que la excepción existe para evitar.

---

## Referencias

- Reporte de cambios (se delega ahí en Phase 4): [[client-report]]
- Protocolo de salida y gating de preguntas: [[_output-protocol]] §2 y §4
- Schema del perfil y de los overrides: `config/client-comms/README.md`
- Precedente del diseño de persistencia: `config/qa-memory/README.md`
