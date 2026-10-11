# Ronda 5 — identidad Google, limpieza de adjuntos y reanudación de pruebas

Fecha: 2026-10-11. Proyecto: `base_django_react_next_feature`, template sin despliegue. Base de diagnóstico: `65f2585e79d2361210dc5d422625b0708f0354e9`. Snapshot combinado de aplicación: `0595e5fc6bf081ec6182456633de68a40867fbeb`, integrado sin conflictos; no constituye aún la aceptación final con documentación.

## Selección y propietarios

Se aprobaron tres causas con beneficio demostrado. Cada dueño implementó aplicación y tests en su rama; QA revisa, documenta y coordina una sola aceptación conjunta. El orquestador conserva integración, publicación y CI. No se modifican frontend, mapa de flujos, configuración global ni migraciones.

| Causa e ID oficial | Retorno / esfuerzo / riesgo | Dueño y snapshot revisado |
|---|---|---|
| Impedir JWT de una identidad aportada por el request sin validación Google — `I-S-6b24d6daacb6` | ALTO / BAJO / MEDIO | Seguridad: `14796e538d85ee845a82ebf8eea8acf6b398d27a` |
| Conservar archivos referenciados cuando se revierte una operación — `I-O-dca4a3ae558d` | ALTO / MEDIO / MEDIO | Observabilidad: `739c8b1d147b9f3d7d1341f62ec99d29913fada5` |
| No heredar el éxito de otra selección o entorno al reanudar pruebas — `I-M-bbefb9ec8008` | MEDIO / BAJO / BAJO | Mantenibilidad: `2d97e9afc0d3a40c149fb781c8b9b63cb2059638` |

## Contratos definitivos

### Google

`backend/base_feature_app/views/auth.py` acepta `credential` o `id_token`. Exige cliente configurado, payload objeto validado por Google, audiencia permitida, email no vacío y `email_verified` exactamente `True` o `'true'`. Email y nombres proceden exclusivamente del payload. DEBUG no habilita un fallback. Un rechazo no emite JWT ni crea o modifica la cuenta solicitada; las respuestas y logs conservan el diagnóstico sin credenciales ni texto privado del proveedor.

Los tests de `backend/base_feature_app/tests/views/test_auth_endpoints.py` reemplazan las expectativas que legitimaban el fallback y ejercitan el rechazo contra una cuenta staff existente. El caso positivo decodifica el JWT real y comprueba que pertenece al email validado, aunque el request mencione otra cuenta. La única frontera simulada nueva es HTTP hacia Google.

### Adjuntos

`backend/django_attachments/cleanup.py` captura el archivo anterior antes del guardado y agenda su limpieza únicamente después de un guardado exitoso o borrado, mediante `transaction.on_commit` sobre el alias de la operación. Rollbacks completos o de savepoint conservan originales y thumbnails. El callback captura el descriptor anterior, respeta referencias confirmadas en el mismo alias y conserva el archivo nuevo. `Attachment` queda excluido de `django_cleanup` para mantener un solo dueño de esta limpieza.

La limpieza posterior al commit es best effort: un fallo de consulta o almacenamiento registra únicamente operación y clase de excepción, conserva el resultado confirmado en DB y permite continuar callbacks posteriores. No garantiza exclusión contra reattachment concurrente ni protege archivos compartidos entre aliases diferentes. No se incorpora una cola persistente de reintentos.

Los tests nuevos están en `backend/base_feature_app/tests/models/test_attachment_cleanup.py`. Los casos existentes de producto/blog y admin ejecutan explícitamente los callbacks que sus transacciones de prueba dejan pendientes. El borrado administrativo de los últimos dueños comprueba el archivo presente antes del callback y ausente después, conservando las cuatro aserciones finales sobre filas y archivo (`backend/base_feature_app/tests/utils/test_admin.py`). No requirió cambiar producción. En `backend/django_attachments/tests.py`, el cambio queda limitado a imports, almacenamiento temporal en setup y ejecución del callback de borrado; se conserva el resto del archivo histórico, sin reformateo general.

### Reanudación

`scripts/run-tests-all-suites.py` prepara una sola invocación efectiva por suite. El éxito anterior solo permite omitirla cuando coinciden argv ordenado, cwd resuelto y SHA-256 del entorno efectivo. El subprocess recibe ese mismo entorno capturado. Fallos previos, identidad ausente o inválida y cambios de selección o entorno fuerzan ejecución; cambiar `PLAYWRIGHT_BASE_URL` ya no hereda un resultado de otra app.

La metadata conserva el digest del entorno, nunca sus valores. Directorio de reportes, rutas de logs, run ID, timestamps y modo de salida del runner no forman parte de la identidad; los argumentos reenviados al runner de tests sí se comparan exactamente. La reanudación no acredita frescura del código, dependencias, datos o servicios cuando la invocación permanece igual. Para obtener resultados nuevos se ejecuta sin `--resume`. El contrato está documentado también en `README.md` y se verifica en `backend/base_feature_app/tests/utils/test_run_tests_suites.py`, con el subprocess como frontera simulada nueva.

## Evidencia de los autores y aceptación conjunta

QA leyó los JUnit regulares de los tres dueños: 131 casos, cero fallos, errores o skips en los siguientes lotes. Estos resultados pertenecen a sus implementaciones; no sustituyen la aceptación del commit combinado. Media conserva 37 casos ejecutados sobre `b286e2300410cf43375b14e2793eb15baa3663a3` y añade ocho administrativos sobre `739c8b1d147b9f3d7d1341f62ec99d29913fada5`; no se atribuyen los 45 a una ejecución única de autor.

| Dueño | Casos ejecutados | Artefactos dentro de su worktree, bajo `test-results/improvement/ronda5/` |
|---|---|---|
| Seguridad | 34: 11 + 16 + 7 | `google-existing.xml`, `google-invalid-identity.xml`, `google-boundaries.xml` |
| Mantenibilidad | 52: 18 + 18 + 16 | `resume-batch-1.xml`, `resume-batch-2.xml`, `resume-batch-3.xml` |
| Observabilidad | 45: 17 + 20 + 8 | `media-regression-scoped.xml`, `media-existing-scoped.xml`, `media-admin-fixed.xml` |

El CI detectó dos expectativas administrativas anteriores al commit. El dueño reprodujo ambos fallos y ajustó solo el test que verifica los últimos dueños; los ocho casos focalizados del admin pasaron sin quitar aserciones. Evidencia: `media-admin-reproduce.xml` (2 fallos) y `media-admin-evidence.json`. Las 34 pruebas Google ya iniciadas sobre el combinado `62abfa1ef02a5d6855b55bbb0a3971720fd10d42` quedaron únicamente como preliminares, archivadas bajo `test-results/improvement/ronda5/preliminary-62abfa/`; ese SHA no fue aceptado ni sus resultados se mezclan con el manifest final.

El Ruff complementario del vendor conserva 15 hallazgos preexistentes y cero nuevos; no se declara limpio globalmente. Los brutos y comparación están en `media-ruff-vendor-{base,scoped}.json` y `media-scoped-evidence.json`. Ese archivo no entra al AST gate por su ubicación y glob preexistentes: ejecución real y Ruff complementario no equivalen al gate semántico. No se debilitan reglas, config ni baseline para ocultar el límite.

La aceptación final se registra una sola vez sobre el SHA40 combinado limpio, en archivos regulares ignorados bajo `test-results/improvement/ronda5/` y en los PRs/checks del cierre. El manifest usa `schema:1`, `kind:improvement-qa` y los tres IDs oficiales. Requiere backend ejecutado y gate; E2E no es requerido por este alcance backend/tooling, aunque CI conserva su baseline frontend/E2E. El validator del proyecto requiere Ruff/ESLint y archivos/tests en las tres capas: un gate focalizado backend no se presenta como aceptación completa del proyecto.

La validación local usa `/tmp/base-template-ronda2-venv`, Node 24.20.0/npm 11.19.0, dotenv deshabilitado, SQLite y almacenamiento sintéticos. Solo archivos/casos explícitos, máximo 20 casos por comando y tres comandos por ciclo; no se ejecuta la suite local completa ni se usan DB, correo o `.env` reales. Este documento se fija antes de esa aceptación y no afirma CI combinado verde. El resultado externo se conserva en artefactos/PRs, sin convertir el cierre de sesión en deuda funcional permanente ni añadir referencias autorreferenciales de commit.

## Pendientes y descartes

- Dos causas de rendimiento siguen elegibles fuera del cupo de tres; no se certifica suficiencia del frente ni se amplía su implementación en esta ronda.
- Responsividad permanece `needs-evidence`: falta medir 835×1194, 412×915, 1195×835, 1440×900 y 2560×1440. No se certifica ningún ancho.
- MySQL CI queda diferido, MEDIO/MEDIO/BAJO: los tres tests concurrentes existentes necesitan ejecución explícita contra MySQL 8.4+; SQLite no acredita locks. No se modifica recuperación de contraseña en esta ronda ni se mueve su test para aparentar validación.
- No se añaden cuotas SMTP ni se acredita protección contra abuso de correo. La excepción npm existente vence el 2026-10-24 y no se renueva ni amplía aquí.
- Persistencia de sesión temporal: MEDIO/MEDIO/MEDIO, descartada por retorno insuficiente frente al coste y riesgo.
- Se conservan las decisiones previas sobre token fuerte, migración irreversible y recuperación del detalle de producto; esta ronda no reabre esos frentes ni adopta su verde histórico como evidencia actual.

## Solicitudes al orquestador

Proporcionar el árbol combinado limpio y su SHA40 para la única QA final; conducir publicación, CI y cierre externo. No se solicita ampliar aplicación, tests, mapa, configuración ni toolkit.
