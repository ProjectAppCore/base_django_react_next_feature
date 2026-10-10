# Technical — Base Django React Next Feature

> Memory Bank · actualizado 2026-10-10 (control de calidad de CI). Las mediciones históricas mantienen su fecha.

## Stack

| Capa | Tecnología | Versión pineada |
|---|---|---|
| Runtime backend | Python / pip | 3.14.7 / 26.2.1 |
| Backend | Django / DRF / simplejwt | 6.1 / 3.18.0 / 5.5.1 |
| Tareas | Huey + Redis | 3.3.4 / 8.1.0 |
| DB dev/test | sqlite3 (default `DJANGO_DB_ENGINE`) | — |
| DB prod | MySQL (mysqlclient 2.2.8, settings_prod) | — |
| Runtime frontend | Node.js / npm | 24.20.0 LTS / 11.19.0 |
| Frontend | Next.js (App Router) / React | 16.3.8 / 19.2.8 |
| Estado | Zustand | 5.0.15 |
| i18n | next-intl | 4.14.0 |
| HTTP | axios | 1.20.0 |
| Tipado | TypeScript nativo / API compatible | 7.0.2 / 6.0.2 |
| Lint frontend | ESLint / @eslint/compat | 10.9.1 / 2.1.0 |
| Testing backend | pytest / pytest-django / freezegun / factory-boy | 9.1.1 / 4.14.0 / 1.5.5 / 3.3.3 |
| Testing unit | Jest 30 + Testing Library (jsdom) | 30.4.2 / jest-dom 7.0.1 |
| Testing E2E | Playwright | 1.62.1 |
| Estilos | Tailwind CSS | 4.3.3 |

## Selección de settings (¡no es DJANGO_ENV!)

- **`DJANGO_SETTINGS_MODULE` elige el módulo**: `manage.py` → default `base_feature_project.settings_dev` (sqlite hardcoded); `wsgi.py`/`asgi.py` → default `settings_prod` (mysql); `pytest.ini` fija `base_feature_project.settings`.
- `DJANGO_ENV` es una variable LEÍDA POR settings (default `development`) que sólo controla `IS_PRODUCTION` y lo que reporta `api/health/`.
- `settings.py` toma la DB de `DJANGO_DB_ENGINE` (default sqlite3) — sin `backend/.env`, los tests corren en sqlite.

## Setup dev local

```bash
# Backend
cd backend && python3.14 -m venv venv
venv/bin/python -m pip install --upgrade pip==26.2.1
venv/bin/python -m pip install --require-hashes -r requirements.txt
venv/bin/python manage.py migrate
venv/bin/python manage.py create_fake_data 5

# Frontend
cd frontend && npm ci
npm run dev            # Next en :3000

# E2E (Playwright levanta ambos webServers solo; requiere backend/venv)
cd frontend && npx playwright test
```

## Patrones de diseño

- **Vistas FBV delgadas** (`@api_view`) por módulo en `base_feature_app/views/` (10 módulos); lógica de negocio en `services/` (hoy: `email_service.py`) y modelos.
- **Serializers por operación**: `*_list`, `*_detail`, `*_create_update` separados (16 archivos) — nunca `fields = '__all__'`.
- **URLs como paquete**: `base_feature_app/urls/` con un módulo por dominio (auth 7, blog 3, captcha 2, product 3, sale 3, staging_phase_banner 1, user 2 = 21 rutas API + 5 de proyecto). ⚠️ existe un `urls.py` legacy shadowed por el paquete (residuo, ver tasks_plan).
- **Stores Zustand por dominio**: `frontend/lib/stores/` (auth, blog, cart, locale, product, stagingBanner).
- **Custom User** (`AbstractBaseUser` + manager propio); galería de imágenes vía app vendorizada `django_attachments`.

## Estrategia de testing (medida 2026-08-13)

| Layer | Runner | Ubicación | Volumen |
|---|---|---|---|
| Backend | pytest (sqlite, `pytest.ini`) | `backend/base_feature_app/tests/` + `django_attachments` | 26 archivos / 197 tests |
| Frontend unit | Jest 30 (`**/__tests__/**/*.test.ts(x)`, threshold 50%) | colocalizados en `app/`, `components/`, `lib/` | 29 archivos / 184 tests |
| E2E | Playwright (project "Desktop Chrome") | `frontend/e2e/` (8 specs / 40 tests) | flow map: `e2e/flow-definitions.json` (33 flows) |

- Quality gate: `scripts/test_quality_gate.py` + `.testquality.yml` (≤50 líneas/test, ≤7 asserts, timeout ≤100ms). La baseline `.junk-baseline.json` conserva cero entradas; no se amplía para aprobar cambios.
- CI (`.github/workflows/`): `ci.yml` valida drift del lock Python, instalación
  con hashes, `pip-audit`, `pip check`, WSGI/Gunicorn, `npm audit`, ESLint,
  allowlist de scripts npm, TypeScript 7 + compatibilidad TypeScript 6, build,
  backend sqlite, unit y e2e con fake data + coverage summary;
  `test-quality-gate.yml` instala tooling fijado, comprueba Ruff y ESLint y ejecuta
  `--junk-severity=error --external-lint run --semantic-rules strict`.
  Después, `scripts/validate_test_quality_report.py <reporte.json>` exige cero
  errores, ambos linters ejecutados y archivos/tests positivos en backend,
  frontend unit y E2E. El CLI canónico conserva sus modos tolerantes locales;
  su salida cero por sí sola no reemplaza esta comprobación del reporte completo.
- Reglas de ejecución: ≤20 tests por batch, ≤3 comandos por ciclo, e2e ≤2 archivos por invocación, `E2E_REUSE_SERVER=1` si el dev server ya corre.

## Constraints técnicos

- Django 6.1 todavía acepta los settings `EMAIL_*`, pero emite
  `RemovedInDjango70Warning`; migrar a `MAILERS` antes de Django 7.
- `backend/requirements.in` es la fuente humana; `requirements.txt` se genera
  con `pip-compile`, hashes y versiones exactas. `requirements-tools.txt` fija
  pip/pip-tools/pip-audit/Ruff y CI rechaza drift. Ruff está fijado a `0.16.4`,
  igual que en el lock de aplicación.
- TypeScript 7 es el typecheck principal. Next y typescript-eslint usan la API
  TypeScript 6 mediante el alias oficial hasta que la API nativa esté soportada.
- ESLint 10 necesita `@eslint/compat` para los plugins legacy anidados por
  `eslint-config-next`; sus peers todavía declaran ESLint ≤9 pese a pasar lint.
- npm `allowScripts` autoriza por versión sólo `@parcel/watcher`, `@swc/core` y
  `unrs-resolver`; cualquier bump exige una revisión nueva y
  `check:install-scripts` hace fallar CI si queda alguno pendiente.
- Los tags E2E viven como constantes en `e2e/helpers/flow-tags.ts` (`@flow:`/`@module:`/`@priority:`; `@outcome:` inline) — specs nuevos reutilizan ese idioma.
- Sin `data-testid` en el source de producción (salvo `components/staging/`): selectores por rol/label; el copy es bilingüe, evitar `getByText` con strings hardcodeados.
- Playwright projects Mobile/Tablet están comentados; los scripts `e2e:mobile`/`e2e:tablet` de package.json fallan si se invocan.
