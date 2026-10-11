# Active Context — Base Django React Next Feature

> Memory Bank · actualizado 2026-10-11. Refrescar al cerrar cada sesión significativa.

## Foco actual

La quinta ronda conservadora implementó identidad Google validada, limpieza de adjuntos después del commit y reanudación de pruebas ligada a la invocación efectiva. Base de diagnóstico: `65f2585e79d2361210dc5d422625b0708f0354e9`. Snapshots revisados: seguridad `14796e538d85ee845a82ebf8eea8acf6b398d27a`, media/admin `739c8b1d147b9f3d7d1341f62ec99d29913fada5` y runner `2d97e9afc0d3a40c149fb781c8b9b63cb2059638`. Snapshot combinado actualizado antes del último refresh documental: `0595e5fc6bf081ec6182456633de68a40867fbeb`, integrado sin conflictos. Los autores ejecutaron 131 casos: 34 Google, 52 runner y 45 media (37 sobre `b286e2300410cf43375b14e2793eb15baa3663a3` y ocho administrativos sobre `739c8b1d147b9f3d7d1341f62ec99d29913fada5`), con JUnit leído por QA y cero fallos/errores/skips. Esa evidencia no sustituye la aceptación conjunta con documentación; el resultado definitivo del SHA combinado se conserva en artefactos ignorados y PRs de esta ronda.

## Decisiones de la ronda

- Seguridad conserva Google y sus tests; observabilidad conserva adjuntos y sus tests; mantenibilidad conserva runner, README y sus tests. QA escribe únicamente el reporte de ronda, active context, tasks plan y arquitectura, y coordina una única aceptación. El orquestador conserva integración/publicación/CI.
- Google exige cliente configurado, audiencia permitida y email verificado del payload. DEBUG no permite fallback al email del request. JWT e identidad proceden del payload validado.
- Adjuntos se limpian mediante `on_commit` del alias correcto; rollback conserva archivos y thumbnails. Un solo dueño de limpieza, descriptor anterior capturado y referencias del mismo alias protegidas. Fallos posteriores al commit se contienen y registran operación/clase; reattachment concurrente y almacenamiento compartido entre aliases quedan fuera de la garantía.
- El test del borrado administrativo de los últimos dueños ejecuta callbacks pendientes y comprueba el archivo antes/después; mantiene las cuatro aserciones finales. Los dos fallos de CI se reprodujeron y los ocho casos focalizados pasaron, sin cambiar producción. Las pruebas del combinado anterior `62abfa1` son preliminares archivadas, no aceptación final.
- Resume compara argv ordenado, cwd resuelto y SHA-256 del entorno efectivo; legacy sin identidad vuelve a ejecutar. No guarda valores del entorno ni acredita frescura del código/dependencias/datos/servicios con invocación idéntica.
- El vendor conserva el cambio mínimo de imports/setup temporal/callback de borrado. Está fuera del AST gate por ubicación preexistente; Ruff complementario muestra 15 hallazgos anteriores y cero nuevos, sin afirmar limpieza global ni modificar baseline/config.
- Las tres causas no cambian frontend, flow map, settings globales ni migraciones. Backend y gate son las capas de aceptación requeridas; CI conserva pruebas frontend/E2E existentes.
- Se conservan las decisiones previas de recuperación: token estándar ligado a contraseña, una fila activa y un consumo transaccional; valores repetidos en el mismo segundo son un tradeoff aprobado. La migración 0006 sigue irreversible. El detalle de producto sigue distinguiendo 404 de fallo temporal y permite Retry.
- Dos causas de rendimiento elegibles quedan fuera del cupo. Responsividad sigue `needs-evidence`; MySQL CI queda diferido MEDIO/MEDIO/BAJO. Persistencia temporal de sesión se descarta MEDIO/MEDIO/MEDIO.
- No se añaden cuotas SMTP ni se certifica protección contra abuso de correo. La excepción npm vigente vence el 2026-10-24; no se renueva ni amplía.

## Decisiones activas

- Tests backend con venv explícito y DB aislada; SQLite para reglas, MySQL 8.4 o posterior para locks concurrentes. La ronda usa `/tmp/base-template-ronda2-venv`; nunca el venv compartido ni `.env`.
- Autochequeo de gate SIEMPRE con `--junk-severity=error --external-lint run` (paridad con hook/CI).
- Jest: paths con corchetes vía `--runTestsByPath` (los args posicionales son regex).
- Sin condicionales en bodies de tests (Regla 7): la fake data seedeada es contrato del entorno; un test sin data debe fallar, no saltearse.
- Excepciones de calidad SOLO con markers documentados (`// quality: allow-...` con razón).
- Dependencias: nunca usar `npm audit fix --force`; aplicar majors de forma
  secuencial, en commits aislados, esperando CI verde entre fronteras.
- Backend: `requirements.in` es fuente y `requirements.txt` lock con hashes;
  CI recompila, compara, instala con hashes y audita.
- Frontend: pins exactos, Node 24/npm 11, TypeScript 7 + API compatible 6,
  ESLint 10 vía `@eslint/compat` y `allowScripts` pineado por versión.
- Backend auditado en `.venv` aislado dentro del worktree; no modificar el venv
  ni el checkout del clon principal.

## Histórico de dependencias (rama chore/27082026-dependency-refresh)

- Actions actualizadas y fijadas por SHA; CI incorpora drift del lock,
  `pip-audit`, `npm audit`, lint, TypeScript 7/6 y build.
- Python 3.14.7, pip 26.2.1, Node 24.20.0 LTS y npm 11.19.0 alineados.
- Backend completamente pineado y auditado: sqlparse 0.6, Gunicorn 26.2 y Ruff
  0.16 incluidos; `pip-audit` 40→0 y `pip list --outdated` devuelve `[]`.
- Frontend completamente pineado: jest-dom 7, ESLint 10 y TypeScript 7 incluidos;
  `npm audit` 10→0 y ncu sólo propone el runtime Node 26 fuera de alcance.
- Cada uno de los 13 commits funcionales esperó los cinco checks verdes antes
  del siguiente.

## Seguimiento

La implementación y pruebas de autor de las tres causas están completas en los snapshots indicados. La aceptación de una sola QA sobre el SHA combinado limpio y el resultado de CI se registran en `test-results/improvement/ronda5/` y los PRs del cierre externo; este documento no anticipa ese resultado ni lo convierte en deuda funcional del template. Contratos, IDs y límites: `docs/audits/improvement-ronda5-20261011.md`. QA no publica ni modifica el toolkit.

Pendientes propios del template, fuera del alcance de ronda 5:

1. Retomar las dos causas de rendimiento elegibles en otra ronda; deduplicación de productos conserva el presupuesto de un GET por solicitud concurrente, sin ampliar a blogs.
2. Medir la matriz responsive de cinco tamaños antes de proponer cambios; sigue sin certificación.
3. Vigilar la excepción npm que vence el 2026-10-24 y el abuso SMTP sin cuotas acreditadas.
4. Reevaluar MySQL CI al cambiar emisión/consumo/locks; los tests concurrentes requieren invocación explícita contra MySQL 8.4+ y SQLite no los valida.
5. Vigilar soporte upstream de ESLint 10 y TypeScript 7; migrar `EMAIL_*` a `MAILERS` antes de Django 7. Estos pendientes no se amplían en esta ronda.
