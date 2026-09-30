---
name: "improvement-pass"
description: "Coordina security-pass, maintainability-pass, observability-pass, perf-pass y responsive-pass para un proyecto, con qa una sola vez al final. Usar para una ronda de mejora transversal. Default descubre, selecciona hasta tres candidatos globales, aplica los justificados y registra resultados. --check sólo analiza; --refresh actualiza el catálogo; --review3 revisa anteriores. Recomienda parar ante retorno marginal, conservando obligaciones y validación necesaria."
---

# Improvement pass — una ronda, hasta tres causas, un cierre de QA

Orquestar las cinco pasadas de mejora con la política y el motor canónicos en
`$HOME/webapps/vps-ops-toolkit/workflows/improvement/IMPROVEMENT_STANDARDS.md`
y `scripts/improvement/improvement-ledger.sh`. No reimplementar selección,
huellas de contexto ni persistencia. **QA es validación de los cambios, no un
sexto frente que compite por el cupo.**

## Cómo invocar este skill

Sin menú por diseño (§4): el alcance y el modo se resuelven de la invocación y del contexto; la delegación conserva la selección del conductor.

Sin picker por diseño: la invocación sin flags **autoriza descubrir, registrar,
aplicar y validar** hasta tres candidatos globales del proyecto del cwd/contexto.
`--apply` es el mismo modo explícito. `--check` devuelve diagnóstico/selección
sin escribir; `--refresh` descubre y registra, sin aplicar; `--review3` revisa
hasta tres anteriores, sin cambios funcionales salvo `--apply` explícito.
Los modos `--check`, `--refresh` y `--review3` son excluyentes; `--apply` sólo
combina con `--review3`. `--fronts=` restringe a nombres de la descripción;
`--module=` delimita el alcance. No hay modo fleet ni deploy.

Qué NO se pregunta: elegir top3, ejecutar las skills ya autorizadas ni repetir
menús de cada pasada. Un proyecto no identificable o una decisión de negocio
imprescindible sí exige aclaración; continuar análisis independiente mientras
se resuelve. Un aviso de parada no pide permiso para seguir gastando trabajo.

## 0. Contexto y aislamiento

Resolver proyecto/codebase, coordenada, estándares y ledger; obtener fecha del
host, no de memoria. `--check` puede leer un clon/host equivocado y lo declara;
aplicación bloquea `wrong-host`, coordenada ambigua o falta de permiso real.
No tocar ni stashar cambios del clon principal.

En modo aplicación, usar el worktree **propio** de la sesión o crear
`session-worktree.sh create fix improvement-<slug>` antes del primer write de
aplicación. Claude entra con `EnterWorktree`; Codex `cd` y usa ese workdir para
todos los comandos. Declarar paths/cambios iniciales de la sesión para no
atribuirlos a la ronda ni revertirlos. No reutilizar una rama de otra sesión.
Si el worktree propio contiene trabajo autorizado previo, aislarlo en su
commit antes de abrir la ronda; cambios cuya pertenencia no está demostrada
bloquean aplicación, sin stash ni incorporación al commit de esta pasada.

Crear el bloque textual `IMPROVEMENT_CONTEXT` definido en el contrato común y
entregarlo a cada pasada, también a $qa y $vuln-audit cuando participen.
El conductor posee Git y el registro; delegadas no abren ramas, commits o PRs.
El contexto no es un nuevo flag de scripts ni amplía permisos del proyecto.

## 1. Descubrimiento con subagentes de lectura

Inventariar los cinco frentes presentes; backend-only implica `responsive`
N/A, no “suficiente”. Leer los registros antes de buscar para evitar repetir
candidatos diferidos con contexto vigente. No ignorar cambios relevantes:
`--refresh` compara sus huellas e invalida conclusiones obsoletas.

Si hay herramientas de subagentes, despachar un explorador por frente con **un
máximo de cuatro simultáneos**; el quinto espera un slot. Propósito: leer el
módulo/código/estándar y devolver hasta seis hallazgos con el formato común,
paths, causa, evidencia y completitud del alcance. No escribir, hacer commits,
emitir eventos, instalar scanners, registrar al ledger ni invocar QA desde esos
exploradores. No usar `perf-scout` aquí: su permiso de escritura rompería el
writer único. Sin subagentes, recorrer esos mismos frentes secuencialmente;
registrar que se utilizó fallback, sin omitir el frente.

Observabilidad corrobora el contrato ProjectApp vigente, sin implementar un
emisor ni consultar credenciales. Rendimiento usa el perfil real del host que
sirve el proyecto, conforme a $perf-pass. Responsividad usa su estándar y
matriz, con tableta vertical obligatoria, conforme a $responsive-pass.

## 2. Unificar, evaluar y seleccionar

Unificar causas compartidas antes de escribir: una causa lleva un ID y frente
dueño, con otros frentes como efectos a verificar. Ejemplo: retry duplicado
asigna la causa a `observability`; exposición en su log añade validación de
seguridad, no un segundo candidato que consume otro cupo.

Registrar descubrimiento y scopes terminados por `--refresh`; `--check` usa su
preview sin guardar. Seleccionar con `--select`, o `--review3` para la revisión.
El límite es **tres en total**, nunca tres por pasada. La selección prioriza
obligaciones/regresiones, severidad, confianza y esfuerzo según el helper; su
orden sólo se cambia para cumplir dependencias reales.

No rellenar el cupo con cambios cosméticos ni con diferidos. Beneficio
desconocido exige diagnóstico, no aplicación. Un frente omitido por el cupo
queda `pending`; sólo una revisión completa y vigente del alcance puede
declarar `sufficient`. Reportar los motivos de parada conforme al estándar.

Si no hay candidatos elegibles, cerrar diagnóstico/registro sin cambios ni QA
innecesario. Obligación bloqueada o evidencia pendiente siguen abiertas, no
equivalen a un proyecto terminado. `--refresh` y `--check` terminan aquí.

## 3. Aplicación secuencial

Orden topológico por dependencias. Sin dependencias, orden:
$security-pass → $maintainability-pass → $observability-pass →
$perf-pass → $responsive-pass. Entregar a cada una **sólo los IDs elegidos
y paths** con `IMPROVEMENT_CONTEXT`, modo apply y la propuesta/value assessment.
No repetir su picker ni su propia búsqueda top3, commit/PR o QA.

Cambios son secuenciales; al terminar cada candidato, registrar diff/guion y
riesgos. Reexaminar solapamientos y precondiciones del siguiente. Una causa
desaparecida por un cambio anterior se registra con evidencia, no se refactoriza
otra vez. Si falla un guard o aparece trabajo fuera de alcance, bloquear ese
candidato y conservar el resto; no rellenar el cupo ni deshacer trabajo ajeno.

Si una delegada requiere árbol limpio, como el candidato acotado de dependencias
de $vuln-audit, el conductor hace antes un commit selectivo de los cambios
propios ya revisados de la ronda. Esa checkpoint no cierra QA ni permite adoptar
diffs ajenos; la verificación combinada final cubre también esos cambios previos.

No basta con que la skill diga “aplicado”: revisar que el diff satisface la
propuesta y pertenece a los paths acordados. Preservar las reglas de cada
pasada y los límites de $vuln-audit, migraciones/deploy manual y producción.

## 4. QA único y registro de la ronda

Reunir `brief-security`, `brief-maintainability`, `brief-observability`,
`brief-perf` y `brief-e2e` producidos, eliminando pruebas duplicadas por
comportamiento, no por archivo. Ejecutar $qa **una vez** con contexto delegado,
misma rama/worktree y unión de capas/paths afectados. Esa QA sigue su flujo de
Architect/Engineers/Verifier y los guards habituales; no crea rama separada por
encontrar el diff pendiente de esta ronda. Entre autoría/correcciones y la
verificación final, el conductor hace commit selectivo de aplicación y tests
y registra el SHA40/ronda. El Verifier ejecuta los comandos sobre ese contenido
limpio. No incluye deuda ajena discrecional sin evidencia de valor, y nunca
omite pruebas necesarias de los cambios.

Para QA, el conductor amplía `allowed_paths` con los targets conductuales y
archivos de flow-map necesarios que Architect identifica con evidencia. Esa
ampliación habilita sólo test/registro requerido; no abre otros módulos de
aplicación ni elimina las fronteras de escritura de cada rol.

Registrar ronda/commit y evidencia tipada mediante `--record` y `--record-qa`
conforme al contrato común. SHA y candidatos deben corresponder al contenido
final que QA validó; si QA cambia contenido, invalidar evidencia anterior y
comprobar el contenido nuevo. E2E sin app que sirva ese contenido deja
`qa-pending`/`draft-unvalidated`, no `verified` aunque tests/gate estáticos pasen.

Un rojo habilita el fix loop acotado de QA; no se resuelve cambiando requisitos,
aumentando baseline de basura o rebajando severidad. Reportar pausa/bloqueo
cuando no se pueda completar la validación.

## Output final

Conservar un reporte de ronda con evidencias, decisiones, guiones, resultados y
referencias de commits. El ledger guarda decisiones/punteros, no métricas ni
porcentajes. El conductor hace commit selectivo y entrega con $pr-green,
PR abierto + CI verde, sin merge; cerrar con $all-in-base `--check-only`.
Registros del toolkit se commitean sólo por su flujo trunk, sin incluir diffs
ajenos. No afirmar entrega completa si falta publicar un registro propio.

Usar $output-protocol con una fila por frente y QA/Entrega; incluir IDs
seleccionados, pendientes por cupo, bloqueos y paradas explicadas. Distinguir
“no conviene seguir en este alcance con este contexto” de “no se revisó”.
Cerrar con `🟢/🟡/🔴 improvement-pass — <resultado>`; bloque de avance antes de la
última línea. En `--check`, no presentar commits/reportes guardados ni prometer
una recepción ProjectApp que no se ejecutó.
