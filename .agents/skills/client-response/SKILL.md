---
name: "client-response"
description: "Analiza mensajes entrantes de clientes y prepara una respuesta fundamentada, sin mezclar etapas ni ampliar el alcance. El operador elige cómo guardarla en ProjectApp: documento con correo y WhatsApp en sus notas privadas, o solo borradores de comunicaciones. Nunca genera ambas salidas, envía mensajes ni implementa cambios. Para avisos salientes simples usa client-message."
---

# Client Response — responder con contexto, alcance y trazabilidad

Esta skill atiende un **mensaje entrante** del cliente. Reconstruye la conversación,
separa los temas por etapa y contrasta cada afirmación con las fuentes correctas.
Prepara correo y WhatsApp y los guarda de una sola forma, elegida por el operador:
**documento con notas** o **solo comunicaciones**. Son alternativas excluyentes.

No es una skill de implementación ni de envío. Una definición que cambie el sistema
queda pendiente de aceptación expresa del cliente antes de pasar a desarrollo. Si el
operador decide implementarla en la misma ronda (corrección, cortesía o excepción),
la respuesta se redacta como entregada; ver «Redacción según el momento del envío»
(Fase 6).

> **Enrutamiento:**
> - Mensaje entrante que exige análisis, respuesta, alcance o decisión → esta skill.
> - Aviso saliente simple sobre una entrega, documento o aprobación ya resuelta →
>   $client-message.
> - Reporte de cambios ya implementados y guía para validarlos → $client-report.

## Cómo invocarla

- `$client-response --email 1234` → abre ese UID y reconstruye su hilo.
- `$client-response --email "asunto o texto"` → busca el mensaje en las carpetas
  configuradas para el cliente y abre el hilo completo.
- `$client-response --whatsapp "<mensaje pegado>"` → usa el texto literal como
  entrada; no intenta buscarlo en correo.
- `$client-response` → usa el mensaje entrante inequívoco que el operador acaba de
  pegar o mencionar. Si no existe, busca el correo reciente del contacto configurado.

Con argumentos explícitos no pregunta cuál mensaje atender. Sin argumentos, si hay
varios candidatos plausibles, muestra remitente, fecha y asunto y pregunta una sola
vez cuál corresponde. Nunca elige entre conversaciones ambiguas.

## Fase 0 — identidad y perfil (read-only)

La skill se ejecuta dentro del repo del cliente. Resuelve la fecha desde el sistema,
el `codebase` desde `remote.origin.url`, y lee:

- `config/client-comms/profile.yml` del toolkit;
- `config/client-comms/clients/<codebase>.yml`;
- `projects.yml` para el nombre canónico, entorno y coordenada de trabajo.

El perfil puede declarar remitentes, carpetas IMAP, contextos, carpetas del Gestor,
`client_id`, `project_id` y `thread_id`. Todos son datos de ayuda: antes de escribir
en ProjectApp se confirma su vigencia con los MCP read-only disponibles.

Si no existe un perfil per-cliente, la skill sigue con los datos verificables del
hilo y propone guardar únicamente la configuración no sensible que haya resuelto.
No mezcla perfiles de otros clientes.

## Fase 1 — reconstruir la conversación completa

### Correo

1. Busca primero en las carpetas configuradas del cliente; no barre buzones ajenos.
2. Abre el mensaje completo, incluidos `Message-ID`, `In-Reply-To`, `References`,
   remitente, destinatarios y fecha.
3. Recorre mensajes relacionados en entrada y enviados hasta reconstruir el hilo.
4. Conserva el asunto existente. La respuesta usa `Re: <asunto>` sin duplicar un
   prefijo `Re:` ya presente.

### WhatsApp

El texto pegado es la fuente primaria. Si el operador incluyó fecha, remitente o
mensajes anteriores, se preservan como contexto; lo que no fue pegado no se inventa.
Si el mensaje alude a «lo anterior» y falta ese antecedente, se pide en una sola
pregunta de texto antes de redactar.

### Hilos previos de ProjectApp

Cuando está disponible el Gestor de Comunicaciones, localiza el cliente y abre los
hilos del mismo contexto. Los usa para evitar repetir respuestas, contradecir una
aprobación anterior o volver a pedir algo ya recibido. Un borrador no enviado nunca
cuenta como comunicación al cliente.

## Fase 2 — expediente mínimo y dos ejes de verdad

Antes de concluir, consulta sólo las fuentes necesarias para los puntos del mensaje:

- levantamiento y versiones aceptadas de requerimientos;
- propuesta económica y sus exclusiones;
- Otrosí y contrato firmado;
- documentos de Fase 1, Fase 1.5, Fase 2 u otras fases nombradas;
- respuestas, actas, correos y WhatsApp anteriores;
- código, tests y estado real del sistema para saber qué existe hoy.

Mantén separados estos dos ejes:

| Pregunta | Precedencia |
|---|---|
| ¿Qué se acordó? | contrato/Otrosí firmado → propuesta o requerimiento aceptado → aprobación fechada en hilo → borrador |
| ¿Qué hace hoy el sistema? | estado real → código y tests → documentación técnica vigente |

El código prueba comportamiento, no alcance contractual. Un documento comercial
prueba alcance, no que algo esté implementado. Si discrepan, la respuesta explica
ambos hechos sin corregirlos en silencio.

Para cada afirmación que llegará al cliente conserva una referencia concreta:
documento e ID/versión, mensaje y fecha, archivo/ruta de código, prueba o estado real.
En modo documento, la referencia detallada va en una nota privada. En modo solo
comunicaciones, va en el inventario de estado para el operador; no crea un documento
ni modifica sus notas para guardarla. No introduce esas referencias en el texto comercial.

## Fase 3 — separar por contexto e inventariar estado

Identifica la fase, etapa, módulo o hilo activo del mensaje. Luego clasifica cada
punto en uno de estos grupos:

1. **Pertenece al contexto activo:** se responde aquí.
2. **Depende del contexto activo:** se aclara sólo la dependencia necesaria.
3. **Pertenece a otra etapa o asunto:** se reconoce y se redirige a su hilo, sin
   resolverlo ni reabrir decisiones en esta respuesta.
4. **Contexto incierto:** se pregunta al operador; no se adivina.

Construye además un inventario fechado:

- **Hecho e implementado:** evidencia de código/estado real.
- **Aprobado:** quién aprobó, qué versión y fecha exacta.
- **Pendiente del cliente:** información, prueba, firma o aceptación.
- **Pendiente nuestro:** análisis o trabajo ya incluido y todavía no cerrado.
- **No acordado / fuera de alcance:** fundamento contractual o de requerimientos.

Una aprobación exige evidencia explícita. El silencio, una reunión sin acta o un
borrador compartido no se convierten en aprobación.

## Fase 4 — clasificar cada punto y decidir la respuesta

| Clase | Respuesta obligatoria |
|---|---|
| Pregunta | Responder de forma directa y justificar con la fuente adecuada. |
| Bug contra comportamiento acordado | Reconocerlo, indicar estado y siguiente validación; no llamarlo requerimiento nuevo. |
| Cambio ya acordado | Resumir la definición vigente y pedir aceptación si la nueva precisión altera la implementación. |
| Cambio menor posiblemente de cortesía | Detenerse y preguntar al operador si se incluye como cortesía. |
| Cambio material o fuera de alcance | Explicar el límite y encauzarlo por paquete de horas, estimación o propuesta. |
| Duda nuestra | Formularla antes de prometer, estimar o redactar una conclusión falsa. |

### Gate de cortesía

Sólo se ofrece al operador la decisión de cortesía cuando la evidencia indica un
ajuste pequeño, localizado, sin nueva vista, flujo, rol, integración, modelo de datos,
regla transversal ni riesgo relevante. Muestra:

- qué pidió exactamente el cliente;
- por qué parece menor;
- impacto observable y riesgo conocido;
- qué se respondería si se acepta o se rechaza la cortesía.

Pregunta: **«¿Lo incluimos como cortesía, dejando claro que no crea precedente?»**
No le menciona al cliente la posibilidad hasta recibir la decisión del operador.

Si el cambio es material, no fuerza una falsa decisión de cortesía: explica que debe
estimarse y consumirse del paquete de horas o cotizarse por separado, de acuerdo con
la fuente comercial aplicable. Nunca inventa horas, precio ni fecha.

## Fase 5 — elegir cómo guardar la respuesta

Resuelve la salida antes de preparar cualquier escritura en ProjectApp. Si el
operador ya eligió en el mensaje o en un turno anterior de esta tarea, respeta esa
elección sin volver a preguntar. «No crees documento, solo comunicación» elige
**Solo comunicaciones**; pedir un documento con los textos en sus notas elige
**Documento con notas**. Cambiar de salida requiere una nueva decisión del operador.

Si no hay elección explícita, usa el sistema de preguntas disponible:
**AskUserQuestion en Claude Code; request_user_input o request_user_input_async
en Codex**, según las herramientas habilitadas. Si ninguna está disponible, pregunta
en texto. Presenta una sola pregunta, con dos opciones excluyentes:

**«¿Cómo desea guardar esta respuesta en ProjectApp?»**

| Opción | Resultado |
|---|---|
| Documento con notas | Crear o actualizar el documento formal y guardar asunto, correo y WhatsApp en sus campos privados, junto con las notas de trazabilidad y pendientes. No crear registros en el Gestor de Comunicaciones, tampoco el entrante. |
| Solo comunicaciones | Guardar los borradores de correo y WhatsApp en el hilo correspondiente. Registrar el entrante solo si hay una fuente real y todavía no existe. No crear ni actualizar documentos o sus notas. |

Pon primero y marca como recomendada la opción que corresponda al caso. Recomienda
documento cuando hay varios puntos sustantivos, alcance, cortesía, costo, una nueva
definición o una decisión que requiere trazabilidad formal. Recomienda comunicaciones
para una aclaración o un cierre breve. Son criterios para recomendar, nunca para
elegir por el operador ni para sustituir su instrucción explícita.

La opción preseleccionada no es una respuesta. Sin respuesta, puedes completar
el análisis y los textos, pero deja pendientes las escrituras externas. No combines
las dos salidas ni cambies de salida porque falte un conector.

La elección define qué artefactos se guardan; no autoriza envíos ni operaciones
adicionales. La Fase 7 verifica que el lote concreto esté autorizado.

El documento formal vive directamente en el Gestor de Documentos. Esta skill no crea
`docs/reports/` ni otro archivo de respuesta dentro del repo.

### Estructura del documento

```markdown
# Respuesta — <etapa y tema>

**Cliente:** <nombre>
**Contacto:** <contacto>
**Fecha:** <fecha del sistema>
**Contexto:** <fase / etapa / hilo>
**Mensaje respondido:** <canal, fecha y asunto o referencia>

## Respuesta ejecutiva
<qué queda aclarado o decidido, centrado en el contexto activo>

## Respuesta por puntos
### 1. <tema del punto> (*<cita o paráfrasis del cliente>*)
**Respuesta:** <respuesta directa y justificada, sin jerga interna>
**Estado:** <implementado y publicado / hecho / aprobado / pendiente / fuera de alcance>
**Cómo validarlo:** <ambiente, ruta del menú, cuenta o rol y resultado esperado — solo cambios entregados>
**Siguiente paso:** <una acción o decisión concreta>

## Temas que corresponden a otro contexto
- <tema>: se atenderá en <fase/etapa/hilo>; no se redefine aquí.

## Estado consolidado
### Hecho y aprobado
- <ítem, versión y fecha de aprobación>

### Pendiente
- <ítem, responsable y condición de cierre>

## Confirmación solicitada
<definiciones que el cliente debe aceptar expresamente antes de implementar; no incluye lo que el operador ya decidió implementar>
```

Omite secciones vacías. No expone hashes, rutas internas, IDs MCP ni discusión
operativa. Sí incluye nombres de documentos/versiones que el cliente reconoce.

## Fase 6 — redactar correo y WhatsApp

El correo es la respuesta completa en lenguaje no técnico y enlaza/nombra el
documento cuando existe. Reglas:

- noticia o respuesta principal en el primer párrafo;
- un bloque por punto del contexto activo;
- los temas externos se redirigen en una sola sección breve;
- fuera de alcance siempre lleva fundamento y vía de atención;
- si cambia una definición que aún depende de la decisión del cliente, termina
  pidiendo aceptación expresa antes de implementar;
- no promete plazo, costo, trabajo ni cortesía no autorizados;
- conserva el asunto del hilo con un solo `Re:`.

El WhatsApp tiene entre 35 y 80 palabras. Indica que la respuesta quedó en el correo,
nombra el tema activo y pide revisar o confirmar. No resume toda la discusión, no
abre otro alcance y no incluye firma formal.

Correo y WhatsApp se conservan idénticos entre el output y el destino elegido:
los campos privados del documento **o** los borradores del Gestor de Comunicaciones.
No se guardan en ambos destinos.

### Citas del mensaje del cliente

Cada vez que el documento, el correo o el WhatsApp retoman un fragmento del
mensaje del cliente —cita textual o paráfrasis, larga o corta—, lo marcan
**siempre entre paréntesis** y, cuando el canal lo permite, **en cursiva**:

- **Cita textual:** las palabras exactas, con su ortografía original, entre
  comillas latinas dentro del paréntesis:
  (*«Referencia y Grupo siguen tocando/excediendo el borde derecho»*). Las
  omisiones se marcan con […]; el texto citado no se corrige ni se completa.
- **Paráfrasis:** sin comillas, porque no reproduce palabras literales, y sin
  atribuirle al cliente algo que no dijo:
  (*usted indica que el precio no aparece en la etiqueta física*).
- **Cursiva según el canal:** documento en markdown con `*…*`; WhatsApp con
  `_…_`; correo en texto plano sin marcas de formato, solo el paréntesis y, si
  es cita textual, las comillas.
- Se cita solo el fragmento necesario para ubicar el punto. Si no es evidente de
  qué mensaje proviene, se indica el canal y la fecha fuera del paréntesis
  (p. ej., «en su correo del 25 de septiembre»).

### Redacción según el momento del envío

El operador envía la respuesta cuando corresponde, no cuando la skill la prepara. Si
en esta ronda decidió implementar un cambio (corrección, cortesía o excepción) y va a
enviar la respuesta después de desplegarlo, redacta **en estado entregado**:

- Documento, correo y WhatsApp describen el cambio como hecho y publicado en el
  ambiente de pruebas: pretérito o presente («implementamos», «ya no solicita»,
  «quedó publicado»), nunca futuro («implementaremos», «le avisaremos cuando esté
  publicado»).
- Cada cambio entregado incluye cómo validarlo: ambiente (URL), ruta del menú, cuenta
  o rol sugerido y resultado esperado.
- En el documento, **Estado** = «Implementado y publicado en el ambiente de pruebas»
  y **Siguiente paso** = la validación del cliente. En el estado consolidado el cambio
  va en «Hecho»; en «Pendiente» solo queda esa validación.
- No se pide aceptación previa de lo que ya se decidió implementar; «Confirmación
  solicitada» queda para lo que sigue esperando la decisión del cliente.
- Las notas privadas registran la condición de envío («enviar solo después de
  desplegar en <ambiente>») sin afirmar un despliegue que aún no ocurrió.

Si el operador va a enviar antes de implementar, o el cambio sigue sujeto a la
aceptación del cliente, usa redacción condicional y pide la confirmación expresa. Si
no está claro cuándo se enviará, pregúntalo una sola vez antes de redactar.

### Información sensible → enlace seguro de un solo uso

Contraseñas, credenciales, llaves API/tokens, accesos a servidor o base de datos,
`.env`, datos bancarios, códigos 2FA o un comunicado confidencial **nunca** se
pegan en el correo, el WhatsApp, el documento formal ni las notas privadas. Van en
un enlace seguro de ProjectApp (se abre una sola vez, vence y el equipo puede
reactivarlo):

- Si la respuesta debe **entregar** un secreto y el operador ya lo dio en la
  conversación, propón en el lote de Fase 7 un `create_secure_link` con ese
  contenido exacto (tipo del catálogo `list_secure_link_types`). Nunca inventes,
  completes ni deduzcas un valor secreto.
- Si el secreto **no** está en la conversación, pídeselo al operador antes de
  cerrar la propuesta de mutación; no crees el enlace vacío ni con marcadores.
- Si el **cliente** debe enviarnos algo sensible, incluye la página pública
  `https://projectapp.co/es-co/secure-link` (en inglés: `/en-us/secure-link`) y
  pídele que nos mande el enlace que genere; sólo el equipo podrá abrirlo.
- El texto al cliente dice que el enlace se abre **una sola vez**, que copie la
  información al abrirlo y que, si lo abre por error, nos avise para
  reactivarlo. En los textos del output el enlace aparece como
  `[ENLACE SEGURO: <título>]` hasta que el lote confirmado devuelva la URL real;
  los borradores persistidos llevan la URL real.

## Fase 7 — persistencia en ProjectApp

Primero ejecuta **todo el descubrimiento read-only**. Muestra el lote concreto con
la salida elegida, IDs/nombres resueltos, contenido y operaciones necesarias:

| Operación | Documento con notas | Solo comunicaciones |
|---|---|---|
| Crear cliente si falta | Solo con datos y autorización suficientes | Solo con datos y autorización suficientes |
| Crear carpeta documental si falta | Solo en el destino autorizado | No |
| Crear o actualizar documento y notas | Sí | No |
| Crear hilo si falta | No | Solo para el contexto confirmado |
| Registrar entrante real que falta | No | Sí, si hay fuente verificable |
| Crear borradores de correo y WhatsApp | No; los textos quedan en el documento | Sí, en el hilo confirmado |
| Crear enlaces seguros necesarios | Cuando estén autorizados | Cuando estén autorizados |

Si el operador ya autorizó ese destino, contenido y operaciones en esta tarea,
ejecuta sin repetir la confirmación. Si el lote incluye algo no autorizado, muestra
el delta y pide confirmación antes de esa escritura. Elegir una salida no autoriza
por sí solo crear un cliente, carpeta, hilo o enlace que no se haya resuelto.

Una confirmación cubre ese lote exacto. No duplica la aprobación ya concedida ni
autoriza cambios posteriores de cliente, destino o contenido fuera de ese lote.

### Cliente e hilo

- Busca por empresa, contacto y correo. No crea duplicados por diferencias de
  mayúsculas, tildes o abreviaturas.
- Si falta el cliente, propone `create_client` con los datos verificables; los datos
  desconocidos se omiten.
- Las escrituras de hilo y entrante siguientes aplican únicamente a
  **Solo comunicaciones**; en **Documento con notas**, los hilos son solo fuentes
  de lectura.
- Reutiliza un hilo del mismo cliente y contexto. Un título recomendado es
  `<Cliente> — <Fase/Etapa>`; no acumula todas las fases en un hilo genérico.
- Antes de registrar el entrante compara canal, fecha, asunto y contenido con el hilo
  completo. Si ya existe, reutiliza su `message_id` como `reply_to_id`.

### Documento formal

- Aplica únicamente a **Documento con notas**. No escribe en el Gestor de
  Comunicaciones, ni registra el mensaje entrante.
- Resuelve la carpeta desde `respuestas.contextos` del perfil. Ante contexto o
  documento ambiguo pregunta; no usa automáticamente la carpeta general.
- Busca una respuesta anterior del mismo hilo. Actualiza sólo si realmente es una
  revisión de ese documento; de lo contrario crea uno nuevo.
- Asocia `client_id` y, si existe y pertenece al cliente, `project_id`.
- Guarda el asunto, cuerpo de email y WhatsApp en los campos privados estándar.
- Estos tres campos son la persistencia del correo y WhatsApp; no crea borradores
  adicionales en Comunicaciones.
- Guarda exactamente dos `client_custom_notes`, en este orden:
  1. **Índice de trazabilidad:** punto → mensaje/fecha → documento/versión o
     código/estado → clasificación.
  2. **Inventario de estado:** hecho/aprobado con fechas, pendientes por actor y
     asuntos fuera de alcance.

### Comunicaciones

- Aplica únicamente a **Solo comunicaciones**. No crea ni actualiza documentos
  o notas privadas, aunque haya documentos anteriores relacionados.
- El mensaje entrante queda `incoming` y se registra como recibido.
- Si solo se conoce la aprobación por lo informado por el operador, no inventa
  palabras ni fecha del cliente y no crea un entrante; los borradores usan
  `reply_to_id=null` hasta contar con un mensaje real pertinente.
- Email y WhatsApp salientes se crean con `direction=outgoing`; ProjectApp los deja
  en estado `draft` y no los entrega.
- Puede referenciar documentos existentes pertinentes, sin modificarlos ni
  convertirlos en una segunda salida. Si no corresponden, omite los vínculos.
- Ambos borradores responden al mensaje entrante pertinente cuando existe
  `message_id`; no los vincula a otra aprobación solo porque sea la más reciente.
- Antes de crear, compara canal, asunto, contenido y contexto con los mensajes
  existentes. Si el borrador ya existe, reutiliza su ID; actualiza solo un borrador
  del mismo contexto cuando esa revisión esté autorizada. Nunca altera uno enviado.
- **Nunca** llama `mark_message_sent` durante la preparación. Sólo puede usarla en
  un turno posterior si el operador afirma expresamente que ese mensaje exacto ya se
  envió por fuera de ProjectApp; registra el hecho, no envía nada.

### Enlaces seguros

- `create_secure_link` recibe `secret_type`, `title` (etiqueta interna, sin el
  secreto), `fields` con el contenido exacto que dio el operador, `client_id`,
  `project_id` si pertenece al cliente, `language` del cliente y
  `validity_days` (7 por defecto; 1, 3, 7 o 30).
- La URL se entrega **una sola vez** en esa respuesta: reemplaza el marcador
  `[ENLACE SEGURO: <título>]` por esa URL en ambos borradores antes de crearlos.
  `list_secure_links`/`get_secure_link` nunca la devuelven; si se pierde, el
  equipo la copia desde `/panel/secure-links`.
- El contenido del secreto no se repite en el output, el documento, las notas
  privadas ni el resumen final: sólo título, tipo, id y vencimiento.
- Reactivar un enlace es una decisión del equipo desde el panel; esta skill sólo
  la recomienda cuando el cliente dice que lo abrió por error.

### Degradación segura

- En **Documento con notas**, sin Gestor de Documentos devuelve el markdown y los
  textos, y declara que no quedaron persistidos. No cambia a Comunicaciones.
- En **Solo comunicaciones**, sin Gestor de Comunicaciones devuelve los textos y
  declara qué borradores no se crearon. No crea un documento como reemplazo.
- La ausencia del conector no usado por la salida elegida no impide guardarla.
  Solo requiere Gestor de Clientes si debe resolver o crear un cliente.
- Sin IMAP: para correo pide que el operador pegue el mensaje/hilo; para WhatsApp
  sigue normalmente.
- Sin `create_secure_link`: deja `[ENLACE SEGURO: <título>]` en los textos, indica
  que el equipo debe crearlo en `/panel/secure-links` y el veredicto es 🟡. Nunca
  pega el secreto como alternativa.
- Nunca afirma «creado», «actualizado», «guardado» o «enviado» sin resultado MCP.

## Guardrails

1. No implementar, editar código ni abrir una tarea de desarrollo desde esta skill.
2. No enviar correo ni WhatsApp; sólo preparar borradores.
3. No mezclar etapas para «aprovechar» una respuesta.
4. No convertir una idea, cortesía o borrador en alcance aprobado.
5. No marcar una aprobación sin actor, objeto/versionado y fecha.
6. No declarar fuera de alcance sin citar el fundamento en la nota privada del
   documento elegido o en el inventario de estado para el operador.
7. No prometer fechas, horas o precios no confirmados por el operador o una fuente.
8. No exponer al cliente la trastienda técnica ni datos privados del expediente.
9. No crear ni actualizar nada por MCP sin autorización del lote concreto. Respeta
   la autorización ya concedida; pide confirmación solo para lo que no cubre.
10. No duplicar mensajes, clientes, hilos o documentos existentes.
11. No escribir secretos en correos, WhatsApp, documentos ni notas: van sólo en un
    enlace seguro creado con el contenido que dio el operador.
12. No redactar en futuro un cambio que el operador decidió implementar y enviará
    después de desplegar: se describe como entregado y con sus pasos de validación.
13. No citar ni parafrasear al cliente sin marcarlo entre paréntesis (en cursiva
    cuando el canal lo permita), ni alterar el texto citado.
14. Guardar una sola salida: documento con sus textos privados o comunicaciones.
    Una elección explícita del operador prevalece sobre la recomendación.

## Output final

Excepción **output-es-el-producto** de $output-protocol: muestra los textos y,
solo en modo documento, el documento completo. El estado de persistencia distingue
la salida elegida y las operaciones realizadas; no agregues un menú post-run.

Orden:

1. `### Documento de respuesta` con markdown en **Documento con notas**, o
   `Documento: no creado — salida elegida: Solo comunicaciones`.
2. `### Correo` en bloque de texto plano, incluido `Asunto:`.
3. `### WhatsApp` en bloque de texto plano.
4. `### Inventario de estado` con hecho/aprobado y pendiente.
5. Tabla breve de la salida elegida: cliente, documento y campos privados en modo
   documento; cliente/hilo y IDs de borradores en modo comunicaciones. Indica la
   otra salida como `No creada — alternativa excluyente`, no como error. Incluye
   enlaces seguros solo cuando existan (id, tipo, vence; nunca el contenido).
6. Veredicto:
   - `🟢 client-response OK — documento y textos privados guardados` cuando se
     completó **Documento con notas**;
   - `🟢 client-response OK — borradores de correo y WhatsApp registrados` cuando
     se completó **Solo comunicaciones**;
   - `🟡 client-response OK — textos listos; persistencia parcial o no disponible`;
   - `⏸️ client-response — decisión del operador pendiente` para cortesía, duda
     material o confirmación MCP todavía no resuelta.

Cuando la respuesta se redactó en estado entregado, cierra con
`Condición de envío: enviar solo después de desplegar <cambio> en <ambiente>`,
siempre fuera de los textos al cliente.

## Notas de fleet

- Fuente canónica: `vps-ops-toolkit/workflows/.claude/client-response.md`.
- Mirror Codex: generado en `workflows/.agents/skills/client-response/`.
- Perfil y rutas: `config/client-comms/README.md`.
- Distribución inicial: Vástago; el diseño es fleet-wide y puede sincronizarse a
  cualquier proyecto elegible mediante $sync-ai-ecosystems.
