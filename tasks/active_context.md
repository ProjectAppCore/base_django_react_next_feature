# Active Context — Base Django React Next Feature

> Memory Bank · actualizado 2026-10-10. Refrescar al cerrar cada sesión significativa.

## Foco actual

La cuarta ronda conservadora implementó tres causas: reset mediante token fuerte, diagnóstico saneado de correo y detalle de producto recuperable. Snapshot de aplicación combinado revisado: `162d91be73ec83bc265c7de22c7fc9c17e44a270` (compartido `8fabd09`, seguridad `0707a6b`, producto `a85e09a`). Los tres casos E2E de recuperación ya están implementados. El resultado final de aceptación e integración se conserva en los artefactos ignorados y los PRs de esta ronda, sin convertir el cierre de sesión en deuda funcional del template.

## Decisiones de la ronda

- Seguridad es dueña de modelos/auth, correo, formulario de recuperación y sus tests; observabilidad es dueña del detalle de producto y sus tests. QA coordina una única validación y los seis documentos aprobados; el orquestador conserva integración y Git externo.
- Se mantiene `PasswordCode` y las APIs existentes; `code` pasa a 64 caracteres. El token estándar de Django está ligado a la contraseña y dura menos de 15 minutos. Emisión/reset marcan usadas las filas pendientes bajo lock de la cuenta; no se añaden cuatro campos de cuotas a User.
- La migración 0006 invalida códigos antiguos pendientes y es irreversible. La comprobación histórica independiente pasó en SQLite en memoria sobre `8fabd093539af6056dfeb4200aa6cd6337442996`: columna 64 e `IrreversibleError` antes de reducirla.
- Errores de correo conservan retorno `False` y registran únicamente operación y clase de excepción. El guard del reset conserva su respuesta genérica y emite una señal saneada; no se añade telemetría adicional.
- Producto distingue 404 de fallo temporal, permite Retry manual y descarta respuestas de una ruta anterior. El test que exigía inexistencia ante un 500 fue reemplazado.
- Deduplicar `fetchProducts` sigue siendo elegible, pero pendiente por el límite de tres causas. No se amplía a blogs. Responsividad permanece sin certificación de cinco tamaños.
- El gate previo ya acreditó Ruff/ESLint, cero errores e infraerrores, baseline vacía, 61 advertencias preexistentes y 55 casos CLI; esa causa no se reabre.
- MySQL 8.0.46 fue rechazado por Django 6.1.1. Se preparó un scratch nuevo 8.4.11, sin red ni MySQLX, con conexión Django/mysqlclient y correo en memoria verificados. Los tres tests concurrentes pasaron en MySQL sobre `af3d6aa` (3 casos, 159,86 s); no sustituyen la ejecución combinada del SHA final. El E2E final sigue pendiente.
- Tradeoff aprobado: el generador estándar puede producir el mismo texto para usuario/estado/segundo idénticos. Se garantiza una fila activa y un consumo, sin prometer valores únicos por emisión. Cambiar la contraseña invalida el token; no se incorpora nonce, subclase ni generador propio.
- No se introducen límites persistentes de emisión/verificación ni se certifica protección contra abuso de correo. La excepción npm existente no se renueva ni amplía.

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

La implementación de las tres causas y sus tests está completa en el snapshot indicado. La migración histórica y los tres casos concurrentes MySQL focalizados ya pasaron; el veredicto de QA/CI sobre el SHA final se registra en los reportes ignorados y PRs de esta ronda. El orquestador conduce el cierre externo; QA no publica ni modifica el toolkit.

Pendientes propios del template, fuera del cupo de ronda 4:

1. Retomar deduplicación de productos solo en una ronda posterior, con presupuesto de un GET por solicitud concurrente; no ampliar a blogs.
2. Medir la matriz responsive de cinco tamaños antes de proponer cambios; sigue sin certificación.
3. Vigilar soporte upstream de ESLint 10 y TypeScript 7; migrar `EMAIL_*` a `MAILERS` antes de Django 7. Estos pendientes no se amplían en esta ronda.
