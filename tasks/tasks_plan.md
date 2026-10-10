# Tasks Plan — Base Django React Next Feature

> Memory Bank · actualizado 2026-10-10 (ronda de calidad del template). Los conteos históricos conservan la fecha de su medición.

## Ronda de calidad 2026-10-10

- Ronda 3 centrada en un control de CI fiable: instalar Ruff, comprobar tooling
  y rechazar reportes que no acrediten lint estricto completo en las tres capas.
- Diagnóstico inicial reproducible: 153 findings Ruff, todos de docstrings o
  espaciado, en 21 archivos. Se conserva el comportamiento de los tests.
- `.junk-baseline.json` tiene cero entradas y no se modifica. No se agregan
  excepciones ni se rebajan reglas o severidad para habilitar el control.
- Pendientes elegibles tras ese prerrequisito: deduplicar la petición de productos
  en curso; registrar de forma saneada fallos internos de reset; distinguir
  indisponibilidad temporal de producto inexistente y permitir reintento manual.
- Sin evidencia suficiente: matriz responsive de cinco tamaños y presupuestos
  defensivos de recuperación. No equivalen a validación completada.
- Bajo retorno descartado: abstracción CRUD, persistencia de auth unificada por
  estilo, serializers de galería compartidos, telemetría sin necesidad operativa
  y tuning sin mediciones. Reabrir solo ante un fallo o requisito concreto.

## Estado por feature (template)

| Feature | Estado | Nota |
|---|---|---|
| Auth (JWT + Google + passcode reset) | ✅ estable | 7 rutas API |
| Blog público + CRUD | ✅ estable | |
| Catálogo/Producto + galería | ✅ estable | django_attachments |
| Carrito + checkout + ventas | ✅ estable | SoldProduct snapshot |
| Backoffice/dashboard | ✅ estable | |
| Staging banner/overlay | ✅ estable | único uso de data-testid |
| i18n EN/ES | ✅ estable | next-intl |

## Estado de testing (cierre de la corrida /qa 2026-08-13, rama qa/13082026)

| Layer | Volumen | Estado |
|---|---|---|
| Backend (pytest, sqlite) | 26 archivos / 197 tests | gate 0 errores (clock congelado con freezegun; contrato del banner pinneado a 9 claves) |
| Frontend unit (Jest 30) | 29 archivos / 179 tests | gate 0 errores; 6 tests no-subject borrados; excepciones documentadas con markers |
| E2E (Playwright) | 8 specs / 48 tests | gate 0 errores; cero condicionales en bodies (Regla 7); 48/48 verdes en vivo |
| Flow map | 36 flows | **36 covered · 0 partial · 0 missing · 0 junk-only** |

`.junk-baseline.json`: **0 entradas** (era 15; 14 sanadas + 1 convertida en excepción documentada `allow-mock-only`).

Gaps cerrados por la corrida 2026-08-13: los 6 partial (auth-sign-up-form, catalog-browse, catalog-product-detail, blog-list-view, home-product-carousel, purchase-loading-state), los 3 módulos sin clases negativas (flows nuevos: checkout-submit-failure P1, cart-quantity-zero-removes-item P2, navigation-unknown-route P3), y 12 false-greens e2e cuyas aserciones vivían tras guards condicionales.

## Known issues (residuos y drift detectados 2026-08-13)

1. `backend/base_feature_app/urls.py` (271 B) quedó **shadowed** por el paquete `urls/` — código muerto, candidato a repo-cleanup.
2. `docs/USER_FLOW_MAP.md` stale (2026-02-24, anterior al staging banner); `flow-definitions.json` sí está fresco (2026-07-27).
3. `.junk-baseline.json`: las 15 entradas históricas fueron retiradas; la lectura
   del archivo el 2026-10-10 confirma cero. No re-freezear para ocultar deuda.
4. Scripts `e2e:mobile` / `e2e:tablet` huérfanos: los projects Mobile/Tablet están comentados en `playwright.config.ts`.
5. `CLAUDE.md` (raíz) describe una app `content/` que no existe — la app real es `base_feature_app` (drift del template).
6. pytest instalado a nivel usuario (8.3.2) difiere del pin (9.0.3); usar SIEMPRE `backend/venv`.
7. **BlogDetailPage sin rama not-found** (bug de producto): con un blogId inválido el usuario queda en "Loading..." para siempre — a diferencia de ProductDetailPage. El test unit correspondiente quedó KEEP con marker `allow-mock-only` hasta ese fix.
8. **Footer.tsx huérfano**: `components/layout/Footer.tsx` no se monta en ningún lado (`app/layout.tsx` inlinea su propio footer). Decisión de producto pendiente: cablearlo o borrarlo (su test `layout.test.tsx::renders footer copy` testea código muerto).
9. **Selectores muertos**: `selectBlogs*`/`selectProducts*` (blogStore.ts:44-46, productStore.ts:44-46) no tienen consumidores — candidatos a remoción de producto.
10. **Deuda pydocstyle corregida en ronda 3**: la medición completa confirmó
    153 findings D en 21 archivos; se corrigieron conservando su comportamiento.
    CI instala Ruff y valida el reporte para impedir el antiguo falso verde
    por herramienta ausente.
11. **~19 selectores posicionales e2e bounded**: seleccionar cards de listas seedeadas requiere un hook estable (`data-testid` per-card en ProductCard/BlogCard) — cambio de producto que destrabaría los warnings fragile_locator restantes.
12. **Django 7 compatibility**: Django 6.1 emite `RemovedInDjango70Warning` por
    los settings legacy `EMAIL_*`; migrar la configuración a `MAILERS` antes del
    próximo major.
13. **Puentes frontend upstream**: ESLint 10 necesita `@eslint/compat` hasta que
    los plugins Next amplíen sus peers; TypeScript 7 necesita la API compatible
    6 hasta que Next/typescript-eslint soporten la nueva API programática.

## Backlog

- [x] Documentar `allow-negation-only` en el estándar canónico para mantenerlo
  alineado con el quality gate compartido.
- [x] Corrida /qa --apply 2026-08-13: partial flows + clases negativas + purga de junk (25 rewrites, 6 deletes, 2 merges) + baseline a 0 — COMPLETADA (rama qa/13082026).
- [x] Corrida vuln-audit 2026-08-27: frontend 10→0 vulnerabilidades; backend
  40→11 en la primera fase patch/minor.
- [x] Dependency refresh integral 2026-08-27 (PR #20): Python/Node/npm/pip,
  Actions, locks, majors y fronteras 0.x; backend 11→0 vulnerabilidades,
  frontend permanece en 0, cero pins backend atrasados.
- [x] Actualizar sqlparse 0.6, Gunicorn 26, Ruff 0.16, jest-dom 7, ESLint 10 y
  TypeScript 7 en commits secuenciales con CI verde.
- [ ] Producto: rama not-found en BlogDetailPage (issue 7) → habilita rewrite del test marcado.
- [ ] Producto: decidir destino de Footer.tsx (issue 8) y remover selectores muertos (issue 9).
- [ ] Producto: `data-testid` per-card en ProductCard/BlogCard (issue 11).
- [x] Burn-down de docstrings backend (issue 10) — patrón D212: summary en la línea de apertura; sin cambios de comportamiento ni reglas.
- [ ] Refrescar `docs/USER_FLOW_MAP.md` desde el código real (qa-analyst) cuando el flow map se toque.
- [ ] repo-cleanup: eliminar `base_feature_app/urls.py` shadowed y scripts e2e huérfanos.
- [ ] Corregir la sección Directory Structure de `CLAUDE.md` (content/ → base_feature_app/).
- [ ] Registrar `db:` y `branch:` de este proyecto en `projects.yml` del toolkit.
- [ ] Migrar settings de email a `MAILERS` antes de Django 7.
- [ ] Retirar `@eslint/compat` y el alias TypeScript 6 cuando el soporte upstream
  permita mantener lint, Next build y typecheck sin puentes.
- [ ] Adoptar Node 26 + npm 12 + `@types/node` 26 juntos en la próxima decisión
  explícita de runtime; Node 24.20.0 sigue siendo el LTS fijado actual.
