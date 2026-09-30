---
name: "deploy-and-check"
description: "VPS-only — Deploy de un proyecto desde la rama exacta de projects.yml: dump, stage, build y ensayo antes de migrar la base real; publicación corta con recuperación automática de código, artefactos y servicios ante fallos. La DB requiere evaluación del operador. Con Integrity y verificación posterior; sólo invocación manual."
---

# Deploy & Check

Skill manual-only. Sólo el operador puede invocarla y sólo corre en el VPS que
sirve el proyecto. El deploy completo se ejecuta en **un único proceso**; no
copies sus fases como bloques shell independientes.

**Protección del despliegue:** el build del frontend, `collectstatic` y el
ensayo de migraciones ocurren antes de migrar la base real y publicar el código.
Si falla esa preparación, el ejecutor descarta el stage y aborta la operación,
revirtiendo las dependencias por el broker. Si falla la publicación, intenta
recuperar código, artefactos, dependencias y servicios, y comprueba la salud de
la generación anterior.

La recuperación tiene límites: la base de datos nunca se restaura sola; una
migración real puede quedar aplicada o incompleta y ser incompatible con el
código anterior. El rollback también puede fallar. Sólo el resultado del
ejecutor y sus comprobaciones permiten afirmar qué quedó recuperado; nunca
prometas que cualquier fallo deja toda la aplicación idéntica y sana.

## Cómo invocar este skill

Sin picker por diseño: la coordenada canónica (`branch:` de `projects.yml`)
decide la rama, `--apply` está fijo en el comando y los flags restantes son
opt-outs de verificación o un modo de vista previa. Ningún flag amplía alcance.

## Ejecución

Desde la raíz del clon desplegado:

```bash
bash "$HOME/webapps/vps-ops-toolkit/scripts/deployment/deploy-project.sh" \
  --apply $ARGUMENTS
```

Vista previa read-only (no abre operación, no toma dump, no construye nada):

```bash
bash "$HOME/webapps/vps-ops-toolkit/scripts/deployment/deploy-project.sh" --check
```

Sin argumento despliega `branch:` de `projects.yml`. Un argumento de rama sólo
puede repetir exactamente ese valor; una rama ad-hoc se rechaza. Flags:

- `--prepare-only`: corre la fase de preparación completa (dump, staging,
  dependencias, build, `collectstatic`, ensayo de migraciones), imprime los
  artefactos que produjo el build (`DEPLOY-ARTIFACTS[<proyecto>]:`), descarta el
  staging y aborta la operación. Nada de lo que sirve el proyecto cambia. Es la
  forma de descubrir el valor de `build_artifacts:` de un proyecto nuevo.
- `--skip-deps`: omite únicamente el análisis advisory de dependencias del
  `post-deploy-check`; no omite la instalación requerida por el deploy.
- `--no-diagnostic`: omite el diagnóstico read-only final del servidor.

Si el bloque «Servidor» del cierre trae la FASE 2 (RAM/workers) o la FASE 11 (queries
lentas) en 🟡/🔴, o un servicio con RSS/peak ≥ 90 % de `MemoryMax`, el Next step es
`$perf-pass <proyecto> --top3` en el repo de trabajo (texto; nunca auto-run): el código se
optimiza antes de tocar `memory_max` o workers ($perf-pass, `docs/capacity-runbook.md`).

Para cambiar la rama de deploy primero corrige `projects.yml` mediante el flujo
de coordenada correspondiente.

## Garantías del ejecutor

El script valida host, proyecto activo, clon exacto, árbol limpio, nombres de
units, rama canónica y el `.env` canónico `backend/.env` antes de mutar. Para
MySQL/PostgreSQL liga engine, DB name y DB user efectivos (incluidos los alias
legacy `DJANGO_DB_*` y, sólo para PostgreSQL, `POSTGRES_*`) a la generación
root-owned; rechaza alias duplicados, endpoints no locales y puertos no
canónicos sin exponer el password. Para SQLite liga en cambio la ruta absoluta
sellada por esa generación y nunca reutiliza el `sqlite_path` del YAML mutable
del caller. Luego realiza esta única transacción en dos fases:

```text
PREPARE — antes de publicar; un fallo intenta descartar y abortar
  preflight root-owned de runtime/current, destinos, host, origin y DB
  → ls-remote del target exacto → fetch del objeto sin refs ni FETCH_HEAD
  → validar manage.py/requirements y fast-forward HEAD→target
  → operation-begin(type=deploy, target=<SHA completo>) + ledger 0600
  → dump pre-deploy SIEMPRE (MySQL/PostgreSQL/SQLite)
  → checkout del target en un STAGE fuera del árbol vivo (mismo filesystem,
    sin tocar .git); node_modules se copia por hardlinks, .env se enlaza
  → pip + npm por los brokers (publican en los venv/node_modules vivos, atómico)
  → build del frontend + collectstatic DENTRO del stage, con guards:
    nada escrito en el árbol vivo, nada fuera de build_artifacts, STATIC_ROOT
    bajo el stage, ningún archivo trackeado modificado
  → ensayo de migraciones sobre <db>_rehearsal, copia real cargada desde el dump
COMMIT — ventana corta; un fallo de publicación dispara el rollback
  → migrate real desde el stage (el árbol vivo sigue intacto)
  → merge --ff-only al target + revalidación de identidad env/DB
  → intercambio atómico (renameat2) de cada build_artifacts: vivo ↔ stage
  → restart completo → health gate con reintentos (units activas + /api/health/)
  → operation-end y baseline autenticado
  → post-deploy-check + diagnóstico read-only
```

El prefetch, posterior al plan root-owned y anterior al `operation-begin`, usa
`--no-write-fetch-head` y un SHA anunciado por `ls-remote`; sólo carga objetos
Git, que son `noise`. Las refs, hooks, `HEAD` y demás `gitmeta` vigilados se
modifican únicamente en la fase de commit, después del ensayo. Así un deploy
normal no fabrica su propio drift.

Las migraciones usan el `DJANGO_ENV` efectivo del unit root-owned o del `.env`
canónico (con `production` sólo como fallback) y cargan el módulo real de
`manage.py` desde el stage. El script introspecta `settings.DATABASES['default']`
y vuelve a comparar engine, name/user y endpoint —o la ruta sellada de SQLite—
sin leer ni imprimir el password. El ensayo exporta `DB_NAME` (y sus alias) al
nombre de la copia y **prueba con el mismo preflight** que la configuración lo
honró antes de correr nada; después compara las pendientes de la copia con las
de la base viva, avisa si `makemigrations --check` reporta modelos sin migrar y
ejecuta `migrate` sobre la copia. El ensayo se salta (nunca bloquea) cuando el
proyecto declara `migration_rehearsal: off`, cuando no hay migraciones
pendientes, cuando el motor no es MySQL o cuando el motor Integrity del host no
tiene el verbo `rehearsal-*`; el motivo queda en el reporte.

`build_artifacts:` en `projects.yml` es una aserción: los directorios o archivos
que produjo el build en el stage deben ser exactamente esos. Un proyecto sin
declaración cuyo build produce algo se detiene antes de la fase de commit e
imprime la lista para declararla. El restart queda ligado al SHA de toolkit
devuelto por el preflight; si `current` cambia en medio del deploy, el broker
falla cerrado. Ya no existe restart temprano: con los builds listos antes de
migrar, la ventana "base migrada con código viejo" dura segundos.

## Qué pasa si falla

| Dónde falla | Efecto en la app | Acción automática | Acción del operador |
|---|---|---|---|
| Preflight, dump, staging, dependencias, build, `collectstatic`, guards | Sin nueva generación publicada; las dependencias vivas pasan por el broker | Intenta descartar el stage, dropear la copia de ensayo y `operation-abort` (revierte venv/node_modules) | Corregir la causa y repetir; si el abort falla, conservar receipt y revisar el recovery |
| Ensayo de migraciones | La base real no se tocó | Igual que arriba; el log queda en `~/.local/state/vps-ops-toolkit/deploy-ledger/logs/` | Arreglar la migración y comprobar el abort |
| `migrate` real | Sólo la DB (MySQL no tiene DDL transaccional) | Aborta la operación; código, artefactos y servicios intactos; reporta el dump | Triage de la migración; restaurar el dump **sólo** tras evaluar (`docs/deploy-transaction.md`) |
| ff-merge, intercambio, restart, health gate | Transitorio | Escalera de rollback: artefactos previos ↔, `reset --hard` a `head_at_open`, dependencias por el broker, restart del código anterior, health, `operation-abort`, `verify` | Leer `DEPLOY[…]: ROLLED-BACK`; la DB queda migrada: decidir con el dump |
| Rollback que no consigue restaurar | Puede ser visible | Preserva receipt+escrow, ledger `needs-operator` | `INTEGRITY_OPERATION_RECOVERY=abort` o intervención manual |
| `operation-end` | Ninguno (ya sano) | Preserva receipt+escrow (cierre ambiguo) | `finish-close`, nunca `abort` |
| Verificación posterior o limpieza del stage, después de un cierre confirmado | La generación nueva sigue publicada | No revierte un deploy ya cerrado; conserva el resultado y reporta salida de error | Revisar la comprobación fallida o el residuo; no ejecutar rollback por un `COMPLETE` con salida no cero |

Un diagnóstico final no disponible es una advertencia. Una verificación
post-deploy fallida sí hace terminar el proceso con error. En ambos casos hay
que distinguir la generación publicada de la verificación posterior.

## Fallos y recuperación

El receipt bearer se publica atómicamente fuera del checkout, modo `0600`. A su
lado vive el **ledger del deploy**
(`~/.local/state/vps-ops-toolkit/deploy-ledger/<proyecto>.json`, `0600`): fase
alcanzada, dump, stage, artefactos intercambiados, ensayo y resultado. Un ledger
terminado se archiva en `history/`; un ledger en vuelo bloquea un deploy nuevo
hasta resolverlo con `resume`, `abort` o `finish-close`, según la fase y la
evidencia terminal; no elijas recovery sólo por el exit del comando.

El escrow es un documento cerrado que conserva juntos el bearer, el
`target_commit` completo y la rama original. `resume` despliega exactamente ese
target: si `origin` avanzó por fast-forward se permite terminar el commit
original (el tip nuevo queda para otro deploy); si el target dejó de ser ancestro
por un force-push, falla antes de renovar la operación o mutar el árbol. Un
tracked dirty posterior también bloquea antes de renovar o instalar dependencias
y conserva intacto el escrow.

- `resume` con el ledger en una fase de preparación reconstruye el stage desde
  cero (nuevo dump incluido). Con el ledger en la fase de commit continúa desde
  la fase registrada: no vuelve a construir ni a intercambiar lo ya
  intercambiado; si el stage desapareció, falla cerrado.
- `abort` con el ledger en la fase de commit **ejecuta la escalera de rollback**
  (necesita el clon y el bearer vivo para el restart). Sin ledger, o con el
  ledger en preparación, es el abort terminal de siempre: autentica el escrow y
  no consulta Git ni el remoto.
- `finish-close` completa el cierre existente. Por defecto usa
  `operation-end --resume-only`, sin iniciar otro cierre. Si el ledger de
  **esa misma operación** está en fase `closed` (escrita después del health
  gate) y coincide su bearer con el escrow, el ejecutor permite reintentar el
  `operation-end` completo: también recupera un cierre rechazado antes de
  comprometer el baseline.

Reintentos explícitos sobre el mismo comando:

```bash
# Continuar una operación propia interrumpida (crash, corte de sesión)
INTEGRITY_OPERATION_RECOVERY=resume \
  bash "$HOME/webapps/vps-ops-toolkit/scripts/deployment/deploy-project.sh" --apply $ARGUMENTS

# Completar el cierre de la misma operación; el ledger autentica el modo permitido
INTEGRITY_OPERATION_RECOVERY=finish-close \
  bash "$HOME/webapps/vps-ops-toolkit/scripts/deployment/deploy-project.sh" --apply $ARGUMENTS

# Abortar: con ledger en commit = rollback completo; si no, abort terminal sin firmar
INTEGRITY_OPERATION_RECOVERY=abort \
  bash "$HOME/webapps/vps-ops-toolkit/scripts/deployment/deploy-project.sh" --apply $ARGUMENTS
```

`finish-close` y `abort` terminan esa invocación y piden ejecutar de nuevo sin
la variable. Ante duda sobre si el commit del baseline ocurrió, usa
`finish-close`, nunca `abort`. El reintento completo sólo se habilita con la
coincidencia de ledger y escrow descrita arriba; con otra operación o sin esa
evidencia sigue restringido a `--resume-only`. Un abort que encuentra evidencia exacta de que la misma
operación ya comprometió baseline, tombstone y receipts de dependencias responde
`already-closed`; si la evidencia está mezclada, no modifica nada y deriva a
`finish-close`. El escrow local sólo se retira tras validar el JSON terminal del
mismo proyecto y bearer. Estos modos pueden terminar con exit `2` aun tras
recuperar: leer el resultado terminal, no interpretar ese exit como un deploy
nuevo fallido. Si se confirmó el cierre, comprobar la generación publicada
antes de decidir otro deploy. `status` no muestra el bearer.

Los modos terminales sin ledger de commit se despachan antes de validar
lifecycle, rama, clon u objeto Git actuales. Por eso siguen disponibles si el
proyecto fue suspendido, la rama rotó o el checkout desapareció.

## Límites de autoridad

Esta skill nunca ejecuta `accept`, `restore`, `policy`, `quarantine purge` ni
`baseline --force`, y nunca restaura una base de datos. Una anomalía previa o
final bloquea el deploy y se deriva a `$integrity`; cualquier mutación de
respuesta la introduce personalmente el operador detrás de la frontera de
contraseña.

El despliegue puede producir cambios esperados, pero sólo se resuelven si el
target, el actor, los sensores, el event trail, los scanners y el delta final
superan todos los gates del cierre. Abrir una operación no constituye una
aceptación genérica. Tras un rollback el baseline vigente sigue siendo el
anterior. Si el rollback terminó, los artefactos vuelven a sus inodos originales
y las dependencias por el broker. `verify` puede responder `ok` o `stale`, o
mostrar sólo archivos `touched` con hashes iguales tras recuperar el código:
`ROLLED-BACK … verify=touched:<n>` deja un **baseline pendiente**, aunque la
generación anterior esté sana. Ninguna otra forma de drift se considera
recuperada; termina en `NEEDS-OPERATOR` y conserva el stage. Nunca ejecutar
`accept` para ocultar ese estado.

En un VPS, que falte `vps-integrity-watch.service` es un fallo duro tanto al
abrir como al cerrar: nunca se interpreta como entorno dev. Sólo el bridge
root-owned puede declarar explícitamente dev/CI y omitir el sensor runtime.

## Acciones disponibles

Sin menú por diseño (§4): skill manual-only y el reporte es el producto; los
únicos caminos posteriores son los comandos de recovery de arriba, que se tipean.

## Output final

Reportar siguiendo $output-protocol. Plantilla específica de esta skill:

| Dimensión | Estado | Detalle |
|---|---|---|
| Preparación | ✅/❌ | dump `<ruta>`, stage `<sha12>`, deps pip/npm, build, collectstatic |
| Ensayo de migraciones | ✅/⏭️/❌ | `passed` (N migraciones sobre copia) · `skipped (<motivo>)` · `failed` |
| Migración real | ✅/⏭️/❌ | N aplicadas · sin pendientes · falló: dump reportado |
| Árbol y artefactos | ✅/❌ | `head → target`, artefactos intercambiados |
| Servicios y health | ✅/⚠️/❌ | units activas, `/api/health/` HTTP <code> en N intentos |
| Integrity | ✅/⏸️/❌ | operation-end firmado · preservado (finish-close) · abortado |
| post-deploy-check | ✅/⚠️/❌ | `RESULTS: …`, `INTEGRITY[…]`, `DEPS[…]` |
| Diagnóstico | ✅/⏭️ | bloque «Servidor» de `diagnostic-brief.sh` |

Informar el exit del proceso junto al veredicto y separar en el cierre:
generación publicada, salud comprobada, base migrada/no tocada/incierta,
Integrity y verificación posterior. Una dimensión no ejecutada lleva `⏭️`;
no completar la plantilla con éxitos supuestos.

La línea `DEPLOY[<proyecto>]: COMPLETE|PREPARE-ONLY|ABORTED|ROLLED-BACK|ROLLED-BACK-UNHEALTHY|NEEDS-OPERATOR target=… head=… dump=… rehearsal=…`
es el veredicto machine-readable y se copia tal cual. `ROLLED-BACK` es 🟡 (la app
sirve la generación anterior; la DB puede haber migrado); `NEEDS-OPERATOR` y
`ROLLED-BACK-UNHEALTHY` son 🔴. `COMPLETE` confirma la publicación y el cierre,
pero con exit no cero la entrega tiene una comprobación o limpieza pendiente y
no se presenta como completamente verificada. `verify=touched:<n>` se informa
como baseline pendiente; no se omite por haber recuperado la salud.

## Next steps (si aplica)

- Tras `ROLLED-BACK` o `NEEDS-OPERATOR` con migraciones aplicadas: leer
  `docs/deploy-transaction.md` §Recuperación y decidir sobre el dump reportado.
- Tras un `ABORTED` por `build_artifacts` sin declarar: copiar la lista de
  `DEPLOY-ARTIFACTS[<proyecto>]:` a `projects.yml` y repetir.
- Tras un cierre ambiguo: `INTEGRITY_OPERATION_RECOVERY=finish-close …` (arriba).
