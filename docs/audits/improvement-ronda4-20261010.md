# Ronda 4 de mejora — decisiones y validación

Fecha: 2026-10-10. Estado: registro del snapshot de aplicación previo a integrar estos documentos; aceptación combinada y CI finales se acreditan en los artefactos ignorados y PRs de esta ronda. Este registro no certifica todo el template.

## Coordenadas y alcance

Diagnóstico único: `361cf35cbd2e61351ab790405f9c747cef12973c`, árbol `6a53a26d55043ace3602da423aa9c2066d12e091`. Código combinado revisado: `162d91be73ec83bc265c7de22c7fc9c17e44a270`. Incluye migración `8fabd093539af6056dfeb4200aa6cd6337442996`, seguridad `af3d6aabb70677f7b4843f47aa91b0c0ce00818f` y producto `a85e09a97feab9e7c7b8635289728391e2f06673`. Seguridad añadió después el caso E2E de envío500/reintento y el selector accesible en `0707a6b32e4a5c2df11a199163aec904e955cb06`; están incluidos en el combinado.

Solo tres causas: recuperación fuerte, logs saneados de correo y producto recuperable. Seguridad conserva backend/auth/formulario de reset y sus tests; observabilidad conserva producto y sus tests; QA conserva mapas/documentación y coordina una validación; el orquestador conserva la migración y la integración. No hay modificaciones del toolkit.

## Decisiones de los seis frentes

| Frente | Decisión | Evidencia y límite |
|---|---|---|
| Seguridad | VALE LA PENA | Seis dígitos acumulables, intentos sin presupuesto y consumo individual en el snapshot (`models/password_code.py:21-40`, `views/auth.py:267-344`). Token estándar fuerte, ligados a contraseña, invalidación de filas pendientes y consumo transaccional implementados. No hay cuotas persistentes ni certificación global. |
| Observabilidad | VALE LA PENA | Excepciones de correo exponían su texto y producto convertía cualquier fallo en ausencia. Señales fijas con clase de excepción, retorno `False`, y estados 404/temporal/Retry implementados; el guard de reset saneado es parte del nuevo flujo. |
| Mantenibilidad | NO VALE LA PENA | Duplicación menor de auth/CRUD sin bloqueo demostrado. Se coordinó el consumidor de `fetchProduct` para evitar loading permanente al propagar rechazos; sin refactor adicional. |
| Rendimiento | VALE LA PENA, pendiente por cupo | Home y carrusel invocan listado; reproducción en memoria del snapshot: dos llamadas simultáneas producen dos GET (`app/page.tsx:15-17`, `ProductCarousel.tsx:15-17`, `productStore.ts:21-28`). No implementado en esta ronda. |
| Responsividad | NO VALE LA PENA cambiar sin medición | No hay medición en la matriz de cinco tamaños. Desktop Chrome no acredita overflow, targets o tablet vertical. Pendiente, sin certificación. |
| QA | VALE LA PENA validar las causas elegidas | El E2E de producto exigía `Product not found.` ante 500 (`products.spec.ts:37-54` del snapshot). Expectativa reemplazada; tokens íntegros y locks requieren evidencia real por capa. Sin cobertura inventada ni limpieza ajena. |

## Calificación de las causas seleccionadas

| Causa | Impacto | Esfuerzo | Riesgo de regresión | Retorno |
|---|---|---|---|---|
| Token fuerte, reemplazo/consumo y compatibilidad del formulario | ALTO | MEDIO | MEDIO | Elimina el espacio de búsqueda de seis dígitos y protege el consumo; cambia el formato que se pega |
| Diagnóstico saneado de correo | MEDIO | BAJO | BAJO | Excepciones del transporte dejan de exponer dirección/token y conservan el contrato |
| Producto: 404 frente a fallo temporal y Retry | MEDIO | BAJO | BAJO | El usuario puede recuperarse de un fallo de red/servidor en lugar de asumir inexistencia |

## Comportamiento y pruebas necesarias

- Recuperación: token completo con máximo 64 caracteres, vigencia estricta menor a 15 minutos, marca usadas las filas anteriores al emitir y al cambiar password, password débil no consume el token, email fallido invalida solo su desafío, replay rechazado y señales saneadas. Frontend conserva rutas y campo `code`, permite pegar letras/separadores y mantiene el valor ante rechazo.
- Concurrencia MySQL: dos resets del mismo token permiten exactamente un éxito, dos emisiones dejan un único desafío activo, fallo al consumir revierte el cambio de password. Conexiones independientes y barrera antes del request; ninguna sustitución de locks, modelos o reglas.
- Correo: ambas funciones fallidas devuelven `False`; logger incluye operación fija y clase de excepción, excluye dirección/token/texto sensible/traceback; stdout vacío. Mock solamente `send_mail`.
- Producto: API404 devuelve ausencia; API500/red conserva fallo recuperable; Retry éxito/fallo/404 termina loading y presenta el resultado; respuestas anteriores no modifican la nueva ruta. Store real en tests de página, mock únicamente HTTP.
- Flow-map: recuperación y producto declaran `display/error/failure/success`; prioridad y helpers existentes conservados. E2E final debe navegar e interactuar en una app real del SHA probado. Respuestas interceptadas prueban la UI, no acreditan el backend ni los locks.

## Evidencia real disponible al redactar

| Comprobación | SHA / entorno | Resultado | Artefacto |
|---|---|---|---|
| Migración histórica 0005→0006 | `8fabd093539af6056dfeb4200aa6cd6337442996`, SQLite `:memory:` | PASS: campo64, fila usada conservada, pendiente invalidada, `IrreversibleError` antes de reducción | `/tmp/improvement-20261010-ronda4-evidence/migration-independent.json` y script `.py` |
| Aislamiento MySQL 8.4.11 | Daemon nuevo, datadir/socket/PID propios, sin networking/MySQLX | PASS | `/tmp/improvement-20261010-ronda4-evidence/mysql84-scratch/isolation-proof.json` |
| Django 6.1.1/mysqlclient al socket propio | DB/cuenta sintéticas, correo memoria | PASS | `/tmp/improvement-20261010-ronda4-evidence/mysql84-scratch/django-connection-proof.json` |
| Concurrencia MySQL: dos resets, dos emisiones, rollback del consumo | `af3d6aabb70677f7b4843f47aa91b0c0ce00818f`, MySQL 8.4.11 scratch | PASS: JUnit leído por QA, 3 casos, cero fallos/errores/skips; tiempo JUnit 155,861 s (comando 159,86 s). Ejecución combinada final por separado | WT `seguridad-ronda4`, `backend/.pytest_cache/seguridad-ronda4-mysql.xml` y `.log`; copia `/tmp/improvement-20261010-ronda4-evidence/seguridad-ronda4-mysql.xml` |
| Backend, unit, MySQL concurrente, E2E y gate combinados | SHA final aún no fijado | PENDIENTE; no se acredita mediante autoría, smoke ni resultados de otro commit | Se guardarán dentro de carpeta ignorada del worktree probado y se copiarán a `/tmp` |
| CI final | A cargo del orquestador | PENDIENTE | PR/checks del cierre externo |

El entorno 8.0.46 anterior se detuvo limpiamente: Django 6.1.1 exige MySQL≥8.4. No se falseó la versión ni se usó la DB compartida. SQLite no acredita `select_for_update`.

## Protocolo de QA final

El Auditor detectó un caso nuevo de fallo SQL con diez aserciones frente al máximo de siete y dos contratos observables. El orquestador ordenó al dueño seguridad separar únicamente respuesta/rollback y diagnóstico saneado, conservando todas las comprobaciones. Es cumplimiento de las reglas existentes en tests nuevos; no se amplía a deuda previa ni se añade una causa. El caso E2E de fallo de red de producto recibió interacción Retry y recuperación observable en `55a56f1a414bb0c3229cf6c294a81ed86dc6ec26`, resolviendo `no_user_interaction` sin excepciones de calidad.

Una sola ronda QA combinada, con Analyst/Architect/Auditor/Verifier lectores; seguridad y observabilidad ya son dueños de sus tests. Venv `/tmp/base-template-ronda2-venv`; Node24.20.0/npm11.19.0. Archivos/casos explícitos, máximo veinte casos por ejecución, tres comandos por ciclo, dos specs E2E; ninguna suite completa local. `PYTHON_DOTENV_DISABLED=1`, DBs sintéticas, correo memoria, puertos exclusivos y sin `manage.py migrate`.

Los comandos `qa-agent.sh --check/--verify` escriben reportes bajo el toolkit. La instrucción del operador lo prohíbe: se conserva `--preflight` de lectura y se usan las mismas herramientas subyacentes de flow audit, gate y validación tipada, con artefactos del proyecto. No se modifica el helper para esconder esa adaptación.

El manifiesto tendrá `schema:1`, `kind:improvement-qa`, SHA40 exacto, tres IDs de causa y ejecuciones reales con capa/comando/exit/artifact/format; E2E `live:true` solo contra la app aislada acreditada. Reportes/artefactos serán archivos regulares, sin symlinks, dentro del worktree probado. No se declara verified por una captura, test draft o gate sin ejecución.

## Descartes y pendientes

- Tradeoff explícito de recuperación: se conserva `django.contrib.auth.tokens.PasswordResetTokenGenerator` estándar. Para un usuario/estado/segundo idénticos puede repetir el texto. Se invalidan filas anteriores, queda una activa y hay un solo consumo transaccional; no se promete valor único por emisión ni validez diferente para dos cadenas idénticas. La nueva contraseña invalida el token anterior. Se rechazó añadir nonce, subclase o generador propio sin un camino de ataque adicional demostrado; el hallazgo del Auditor se resolvió precisando el contrato documental, sin ampliar código ni tests.

- Deduplicación de `fetchProducts`: MEDIO/BAJO/BAJO; elegible pero fuera del cupo. Se conserva el guion de concurrencia, recarga y Retry para otra ronda; no se amplía a blogs.
- Refactors CRUD, galería y persistencia auth por estilo: BAJO/BAJO/MEDIO; descartados sin un problema concreto.
- Cachés, índices y tuning: sin mediciones de un cuello de botella; no propuestos.
- Tracing, telemetría externa y reintentos automáticos: sin necesidad operativa demostrada; no propuestos.
- Responsividad: medir 835×1194, 412×915, 1195×835, 1440×900 y 2560×1440 antes de decidir; acciones, overflow y targets siguen sin certificación.
- Cuotas persistentes de emisión/verificación y abuso de correo: no implementadas ni acreditadas por el token fuerte.
- Gate ronda3: Ruff/ESLint ejecutados, cero errores/infraerrores, baseline vacía, 61 advertencias preexistentes y 55 casos CLI aprobados son evidencia anterior; no se purga deuda ajena ni se reabre esa causa.
- CI y aceptación final: pendientes hasta el SHA limpio combinado y sus artefactos.

## Solicitudes al orquestador

Integrar los seis documentos (los tres casos E2E de recuperación ya están incluidos), proporcionar el SHA limpio exacto para la validación final y conducir el cierre Git/CI externo. QA no publica ni mergea PRs.
