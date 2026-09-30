---
name: observability-pass
description: "Pasada de observabilidad y tolerancia a fallos de UN proyecto: logs, métricas, errores, correlación/tracing, alertas, diagnóstico, timeouts, retries, idempotencia y concurrencia. Diagnostica hasta 3 candidatos; --apply corrige instrumentación o fallos acotados y prepara /qa. Evalúa beneficio antes de cambiar y registra decisiones. Diseña futuras entregas de eventos a ProjectApp conforme a su API v1 existente; no instala un emisor, activa monitoreo ni genera tokens automáticamente."
argument-hint: "[proyecto] [--apply|--check|--refresh|--review3] [--module=<alcance>]"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Agent, AskUserQuestion, EnterWorktree
---

# Observability pass

Poder detectar y explicar un fallo real, y limitar sus efectos cuando una
dependencia externa, retry o carrera interviene. Leer
`$HOME/webapps/vps-ops-toolkit/workflows/improvement/IMPROVEMENT_STANDARDS.md`.
Para integración con ProjectApp, leer también
`workflows/improvement/PROJECTAPP_EVENT_CONTRACT.md` en ese mismo toolkit y
corroborar la versión vigente de la API antes de proponer un payload.

## Cómo invocar este skill

Sin menú por diseño (§4): el alcance y el modo se resuelven de la invocación y del contexto; la delegación conserva la selección del conductor.

Sin picker por diseño: default diagnostica hasta tres candidatos nuevos y
registra hallazgos; `--apply` cambia sólo candidatos elegibles; `--check` no
escribe nada; `--refresh` sólo descubre/registra; `--review3` revisa hasta tres
anteriores. Modos excluyentes. Hereda contexto delegado de [[improvement-pass]]
sin preguntar modo ni crear otra rama.

Qué NO se pregunta: instalar telemetría, comprar servicios, emitir tokens o
activar integración como paso rutinario. Esos cambios requieren alcance y
operación propios; no se infieren de esta pasada.

## 1. Preflight e inventario

Resolver proyecto/coordenada. Aplicar en el worktree actual o crear
`session-worktree.sh create fix observability-<slug>`; Claude `EnterWorktree`,
Codex `cd` y comandos con ese workdir. Identificar procesos críticos y sus
interfaces externas; no inspeccionar logs con secretos sin un filtro seguro.

| Frente | Pregunta que guía la evidencia |
|---|---|
| Logs/errores | ¿Se distingue éxito, fallo y degradación con contexto suficiente y saneado? |
| Métricas/alertas | ¿La señal detecta una obligación del proceso y tiene dueño/acción, sin spam? |
| Tracing/correlación | ¿Se puede relacionar una operación con su tarea/llamada sin usar datos privados? |
| Diagnóstico | ¿Un fallo silenciado o mensaje genérico impide encontrar su causa concreta? |
| Timeouts/retries | ¿Hay límites completos y un retry de un efecto produce una repetición peligrosa? |
| Idempotencia/concurrencia | ¿Duplicados o carreras alteran datos, estados o efectos externos? |

Seguir código de inicio, errores, recuperación y cancelación. Usar fallos
simulados/fixtures; no provocar outages, correos o pagos reales. Una señal
ausente sólo se convierte en candidato al nombrar qué fallo quedaría invisible
y qué decisión permitiría tomar. Más logs/traces por sí solos no son mejora.

## 2. Selección y aplicación acotada

Registrar candidatos `observability` según el contrato común; pérdida de datos,
efectos duplicados comprobados o regresiones obligatorias no se difieren por
economía. No inventar una observación exitosa donde faltan ejecución o datos.

Aplicar sólo cambios con beneficio: contexto/error estable y saneado, timeout
en la frontera, retry limitado para operaciones que permiten repetición,
deduplicación/atomicidad requerida o diagnóstico de un fallo silenciado.
Conservar contratos de errores y límites del host. Backoff/jitter, límites de
intentos y mecanismo de idempotencia deben salir de las necesidades del proceso;
no añadir un retry genérico a pagos, notificaciones o escrituras no idempotentes.
No registrar argumentos, SQL completo, bodies, tokens ni identificadores de
usuarios como dimensiones de métricas.

Instrumentación acotada de aplicación puede formar parte de `--apply`. Una
reorganización de colas, nueva plataforma APM o política de alertas operativas
fuera de alcance queda como propuesta. Seguridad del saneamiento pertenece a
[[security-pass]]; coste de la instrumentación a [[perf-pass]]; el conductor
asigna una causa única y evita aplicar dos cambios que compitan.

## 3. Integración futura con ProjectApp

El contrato común de eventos reutiliza `POST /api/monitoring/v1/ingest/` versión
1 con `Bearer`, recurso/fuente autorizados y claves admitidas. Esta entrega de
la skill define instrucciones: **no construye ni instala un emisor, cambia
ProjectApp, registra fuentes, genera tokens o envía HTTP**.

Si un proyecto carece de emisor/fuente autorizados, producir propuesta y marcar
“integración pendiente”; no declarar recepción verificada. Si ya tiene
integración, auditarla por sus límites y recibos sin enviar eventos reales.
Un futuro emisor escribirá eventos saneados a una cola acotada local,
desacoplada del flujo de negocio, y sólo confirmará entrega tras ACK válido.

`external_id` identifica la entrega y persiste en todos sus retries;
`fingerprint` identifica el problema dentro de una fuente/recurso. No usar el
request ID efímero como fingerprint. La recuperación técnica no cierra un caso
manualmente. Trace/span IDs y evidencia anidada **no están admitidos en v1**;
proponer una extensión versionada separada si resultan necesarios, sin enviar
campos inventados ni esconderlos dentro de un string.

## 4. Guion, registro y cierre

Entregar `brief-observability` a [[qa]]: entrada/fallo simulado, resultado y
estado concretos, capa dueña, test existente, `file:line` y bug. Para retries,
usar reloj simulado y asertar número de intentos/límite/cancelación, no tiempos
de pared. Para concurrencia, probar la carrera y el resultado persistente, no
sólo presencia de locks. Para saneamiento, asertar campos/valores permitidos y
estado útil además de ausencia de datos sensibles.

Si se implementa un emisor en una tarea futura autorizada, su QA deberá cubrir
duplicados, 409 por contenido distinto, rechazo/saneamiento, timeout/red/429/5xx,
cola llena, credencial revocada, ACK inválido, recuperación y carreras. La skill
no autoriza ejecutar ahora esos escenarios contra el API real.

Guardar reporte y registro; applied espera QA. Independiente: handoff [[qa]],
sin inline QA. Delegada: devolver IDs, diff, guion, contrato/eventos propuestos
y pendientes; no abrir PR/commit propios.

## Output final

Usar [[_output-protocol]]: Señales · Diagnóstico · Resiliencia · Privacidad ·
ProjectApp · Valor · QA. Separar recepción demostrada de propuesta pendiente y
alcance suficiente de ausencia de evidencia. Cerrar con
`🟢/🟡/🔴 observability-pass — <resultado>` según evidencia; bloque de avance
antes de esa última línea.
