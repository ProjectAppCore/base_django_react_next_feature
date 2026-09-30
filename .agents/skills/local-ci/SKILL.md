---
name: "local-ci"
description: "Reproduce el CI de un proyecto localmente cuando GitHub Actions no está disponible o se pide validar toda la suite sin saturar el host. Descubre controles, ejecuta backend, frontend, build y E2E por lotes, corrige fallos con fix-broken-tests y conserva evidencia reanudable. No optimiza workflows ni certifica el CI remoto."
---

# CI local con recursos controlados

Sin menú por diseño (§4): el pedido de CI local define el alcance. Vacío significa
ejecutar y reparar; `--check-only` ejecuta sin cambiar código; `--resume` continúa
una ejecución compatible. No se encadena automáticamente a cada edición ni a $qa.
El usuario que pide esta validación integral autoriza recorrer la suite completa
en lotes; conserva los límites por invocación del proyecto. No impongas el límite
de una regresión puntual al inventario total solicitado.

## 1. Ubicar y definir qué significa CI completo

- Lee las instrucciones del repo y resuelve referencia, SHA y cambios de la sesión.
  Una referencia explícita se verifica como commit; nunca evalúes texto como shell.
  Trabaja en tu worktree. Conserva intactos el checkout desplegado y trabajo ajeno.
- Sin referencia, valida el estado de tu sesión; al validar una release remota,
  fija su SHA actual. No confundas una copia local atrasada con la release.
- Lee **todos** los workflows, scripts llamados, locks, configuraciones de runners
  y servicios. El gate de PR/push es el alcance por defecto. Los workflows sólo
  programados/manuales quedan listados fuera del alcance; no cambies su activación.
- Construye la correspondencia job/step → control local. Conserva las variantes
  reales de runtime, navegador, base de datos y matriz; los shards sólo reparten
  el mismo inventario. Incluye build, tipos, lint, calidad y umbrales cuando el CI
  los exige. No añadas auditorías de cobertura nueva, dependencias o performance.
- Separa transporte de artifacts/comentarios de su contenido: consolida localmente
  los reportes equivalentes, sin publicar comentarios ni estados de GitHub.
  Un job omitido o una variante no reproducida es una brecha, nunca un aprobado.
- En el toolkit, usa su ejecutor especializado `scripts/ci/run-validation-locally.sh`
  para acreditación; esta skill no reemplaza sus controles de host y SHA.

## 2. Preparar recursos y aislamiento

Motor compartido: `~/webapps/vps-ops-toolkit/scripts/ci/local_ci.py`.
Lee `~/webapps/vps-ops-toolkit/docs/local-ci.md` antes de generar el plan del motor.
Los helpers son versionados; si el toolkit falta, informa la dependencia y usa
su fuente autorizada para instalarlo, sin inventar un ejecutor distinto por sesión.

1. `python3 <motor> resources --path <directorio-existente>` mide afinidad, cuotas
   cgroup v1/v2 y ancestros, RAM disponible, disco y carga. El perfil productivo de
   $perf-pass no reemplaza la capacidad del host que ejecutará las pruebas.
2. Una ejecución pesada a la vez, un worker inicialmente. Aumenta como máximo a
   dos sólo con consumo medido, capacidad disponible y reglas del proyecto que
   lo permitan. Preserva las reservas calculadas; no modifiques servicios o cuotas
   ajenas para hacer espacio. Si no alcanza, conserva el checkpoint y explica qué falta.
3. Usa dependencias del lockfile, runtimes equivalentes al CI y servicios temporales.
   No sustituyas MySQL/PostgreSQL por SQLite para pasar tests. Si faltan herramientas
   o privilegios necesarios, declara la limitación sin relajar el control.
4. El `.env` enlazado del worktree puede apuntar a datos reales. No lo cargues para
   pruebas. Prepara variables privadas y comprueba los settings efectivos: motor,
   nombre/usuario de base temporal, correo de pruebas y proveedor externo controlado.
   Ninguna migración, semilla o limpieza se ejecuta contra datos del cliente.
5. Si el protocolo prohíbe migraciones desde worktrees, prepara la base usando una
   copia temporal del código fuera del worktree, con el mismo fingerprint y entorno
   exclusivo verificado. No conviertas esa excepción de preparación en un deploy.
6. Para E2E usa el build de producción si así lo hace CI. Puertos y procesos propios;
   reutilizar requiere comprobar propietario, SHA, configuración y datos aislados.
   `E2E_REUSE_SERVER` no es universal: lee la configuración real del proyecto.

## 3. Inventariar y ejecutar

- Obtén casos expandidos con el runner real: nodeids de pytest; títulos/ocurrencias
  de Jest conservando jsdom/node por archivo; proyectos, parámetros y repeticiones
  de Playwright. El descubrimiento no ejecuta cuerpos de tests, pero sus imports
  y configuraciones requieren ya el entorno aislado. Rechaza `.only` y colección
  incompleta. Nunca cuentes declaraciones estáticas como casos ejecutados.
- El motor normaliza inventarios y arma lotes. Máximo 20 casos por comando, dos
  archivos E2E y tres comandos por ciclo; aplica un límite menor si el repo lo exige.
  Selectores ambiguos viajan juntos y nunca pueden exceder el límite. Cualquier
  exceso requiere refinar el selector, no ejecutar un grupo mayor en silencio.
- Orden: preparación → backend → frontend unitario → build → E2E → consolidación
  y gates. Declara dependencias entre controles; un fallo permite continuar controles
  independientes. No lances capas o lotes en paralelo, tampoco desde subagentes.
- Genera un plan privado con cada inventario, comando literal, reporte esperado,
  relación con jobs CI, estimación de memoria y probes de runtime/servicios.
  Guarda configuración resuelta y hashes de dependencias externas al repo: un
  lockfile no prueba que el entorno instalado lo cumpla.
- `init` fija el fingerprint; `run --max-batches 3` ejecuta un ciclo y devuelve
  resultados. Revisa el progreso y recursos antes del siguiente ciclo. No uses
  pipes que oculten exit codes, `|| true` ni reintentos que conviertan flaky en verde.
- Preserva cobertura cruda por lote y denomina correctamente los archivos sin
  ejecutar. Evalúa los umbrales **originales sobre el agregado**, nunca porcentajes
  promediados ni un umbral global sobre un solo lote. Los helpers usan coverage.py
  e Istanbul; umbrales por ruta requieren el adaptador nativo, no ignorarlos.
- Consolida también los reportes/flows E2E exigidos por CI. Un test de navegador
  con API simulada no acredita el backend real; identifica la cobertura integrada.

## 4. Resolver fallos

Clasifica: aplicación, test incorrecto, flaky, dependencias, infraestructura o
recursos. Conserva primer error y todos los intentos. Para tests, entrega a
$fix-broken-tests lista exacta, capa, traceback, contrato esperado y autorización
de reparación de esta sesión. El hijo sólo ejecuta fallos y regresión del módulo.

Sin `--check-only`, corrige defectos demostrados con cambios mínimos, incluido
código de aplicación cuando corresponda. No cambies la funcionalidad acordada
para satisfacer un test equivocado. Con autorización existente no vuelvas a pedirla.
Sin ella, prepara diagnóstico y diff propuesto antes de solicitar la decisión.
Gates de lint/build/config se corrigen según su causa; no los fuerces dentro de un
test ficticio. No rediseñes el CI ni reduzcas sus umbrales.

Máximo tres intentos por fallo. Si persiste, registra bloqueo y lo probado; sigue
sólo con controles independientes. Un reintento aprobado no cura un flaky.
Tras cambios, recolección e inicialización de una ejecución nueva. El cierre
requiere **una pasada completa por lotes del estado final**, con todas las
dependencias y build correspondientes; los resultados anteriores son históricos.

## 5. Evidencia, reanudación y cierre

Historial en `~/.local/state/local-ci/`, directorios 0700 y archivos 0600, fuera
del repo. Conserva plan, identidad de código/entorno/helpers, fuentes CI, logs,
casos esperados/observados, cobertura, consumo, intentos y reporte legible.
No guardes valores secretos en planes, comandos, commits o reportes compartibles;
el entorno es un JSON privado separado. Revisa logs antes de compartirlos.

`--resume` valida fingerprints y hashes de evidencia. Código, configuración,
dependencias, helpers o entorno distintos invalidan la reanudación. Un reporte
incompleto/interrumpido nunca se convierte en aprobado por existir en disco.
El lock del host evita dos ejecuciones de esta herramienta a la vez; la medición
continua también observa carga ajena. Detén sólo procesos/servicios de tu ejecución.

| Veredicto | Condición |
|---|---|
| APROBADO | Todos los controles obligatorios, casos únicos y umbrales del estado final pasaron; sin brechas. |
| FALLIDO | Al menos un control o caso falla; conservar las brechas adicionales. |
| INCOMPLETO | Falta evidencia, hay omitidos/skips, cambió la identidad, recursos insuficientes o alcance de ensayo. |

Los skips se muestran individualmente; no cuentan como aprobados. Si CI excluye
un conjunto deliberadamente, documenta la exclusión en el inventario antes de
ejecutar, sin retirar un fallo de esta ronda para conseguir verde.

Si hubo cambios: aplica el protocolo Git del repo y entrega el PR con evidencia
local, sin merge. Cuando GitHub esté bloqueado por billing, informa ese estado;
no esperes indefinidamente $pr-green ni publiques checks remotos ficticios.
Sin cambios: no crees commits/PRs sólo por haber ejecutado pruebas. Limpia servicios
temporales y conserva evidencia antes de retirar un worktree propio.

## Output final

Resultado, repo/revisión/fingerprint, controles ejecutados, casos distintos por
capa, fallos corregidos, skips/brechas, pico de recursos y enlace al reporte.
Di explícitamente «CI local» y el estado remoto conocido. Un ensayo parcial valida
la herramienta, no la salud completa del release. No inventes porcentajes de avance.
