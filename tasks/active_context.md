# Active Context — Base Django React Next Feature

> Memory Bank · actualizado 2026-10-10. Refrescar al cerrar cada sesión significativa.

## Foco actual

Cerrar la tercera ronda conservadora de mejora del template. El alcance es
hacer obligatorio un quality gate completo en CI: Ruff instalado, docstrings
conformes a las reglas existentes y un validador que rechaza reportes incompletos.
Los PR #20 a #26 de dependencias y las rondas anteriores ya están integrados.

## Decisiones de la ronda

- QA implementa los tests y el validador; el orquestador conserva CI, tooling,
  documentación e integración. Cada archivo tiene un único dueño.
- `python scripts/validate_test_quality_report.py <reporte.json>` exige semántica
  estricta, cero errores, Ruff/ESLint ejecutados y objetivos en las tres capas.
  El código de salida del core por sí solo no acredita esa ejecución.
- Ruff `0.16.4` también queda en `requirements-tools.txt`. No se modifica el
  core distribuido, la baseline, las excepciones ni las reglas para aprobar.
- La revisión completa inicial encontró 153 findings Ruff documentales en
  21 archivos; esta deuda es prerrequisito para habilitar el control existente.
- Las mejoras elegibles de doble carga de productos y diagnóstico de reset se
  posponen hasta cerrar este control; no se descartan por bajo retorno.
- Responsividad sigue sin matriz de cinco tamaños acreditada. La revisión
  defensiva de seguridad fue acotada y no certifica todo el frente.
- La excepción de auditoría npm existente tiene caducidad el 2026-10-24 y está
  restringida a este repositorio. No se renueva ni se amplía en esta ronda.

## Decisiones activas

- Tests backend SIEMPRE con `backend/venv` y sqlite (`db=mysql` del registry es fallback, no dato).
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

## Próximos pasos

1. Cerrar la ronda con CI completo verde, `$merge-queue` y comprobación
   `$all-in-base --check-only`; conservar evidencias del SHA probado.
2. Vigilar soporte upstream de ESLint 10 en los plugins Next y de la API
   TypeScript 7 en Next/typescript-eslint para retirar los puentes.
3. Adoptar Node 26/npm 12/@types 26 como una sola frontera de runtime futura.
4. Migrar `EMAIL_*` a `MAILERS` antes de Django 7.
5. Retomar únicamente mejoras con evidencia: doble carga de productos,
   fallo interno de reset sin señal y detalle de producto que confunde un fallo
   temporal con inexistencia. No añadir refactors cosméticos para llenar una ronda.
6. Registrar `db:`/`branch:` en projects.yml del toolkit.
