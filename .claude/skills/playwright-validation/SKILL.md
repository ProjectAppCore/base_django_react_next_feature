---
name: playwright-validation
description: "Validar/probar/debuggear UI de proyectos del fleet con Playwright MCP. Detecta entorno (staging vs production), valida fake data, reusa sesiones autenticadas, limpia artefactos. Production es read-only por contrato."
argument-hint: "[proyecto] [--url=...] [--user=...] [--viewport=compact|portrait|landscape|desktop|wide]"
allowed-tools: Bash, Read, Edit, Write, WebFetch
---

# Playwright Validation — Skill para el fleet VPS

Esta skill estandariza el uso de **Playwright MCP** (instalado en Claude Code) para validar, probar, debuggear y reproducir bugs sobre cualquier proyecto Django del fleet (`projects.yml`). Aplica reglas distintas según el entorno: staging puede mutar y crear fake data; production es **read-only por contrato**.

> **Autorización del operador (Gustavo):** Playwright MCP queda autorizado a correr lo que necesite sin pedir permiso paso a paso, **excepto** cualquier mutación contra un proyecto production (ver §5).

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): con `$ARGUMENTS` o intención clara en la sesión (los disparadores de §1) → ejecutar directo, PROHIBIDO preguntar el tema (un dato menor faltante se marca en el texto, no se convierte en pregunta). Sin argumentos ni contexto → UNA sola pregunta corta en texto por qué validar y dónde (no picker: el insumo es libre). Nunca en modo fleet/headless/cron.

Sin picker por diseño: los flags son parámetros de la corrida (URL, usuario, viewport); se tipean. El proyecto, si falta y no se infiere del cwd, se pregunta en texto.

---

## 1. Cuándo activarse

Disparadores típicos en lenguaje del usuario:

- "valida el flujo X en `<proyecto>`"
- "self-QA, acabo de cambiar la UI de `<proyecto>`"
- "abre el navegador y prueba el login / checkout / form de `<proyecto>`"
- "reproduce el bug en `<dominio>`" / "no me carga el botón X"
- "regression triage" / "qué se rompió en este deploy"
- "genera tests E2E para `<flujo>` en `<proyecto>`"
- "repara los tests rotos de `<proyecto>`"
- "inspecciona la consola / network requests de `<dominio>`"
- "prueba responsive: mobile / tablet / desktop"
- "valida el menú móvil en 412px"

Si la solicitud encaja en cualquiera de estos, ejecutar el flujo de pre-flight checks (§2) **antes** de tocar `browser_*`.

---

## 2. Pre-flight checks (orden estricto, bloqueantes)

### Paso A — Detectar proyecto y entorno

```bash
# Cargar helpers del fleet (idéntico al patrón que usan server-alerts.sh, backup-mysql-and-media.sh)
OPS_ROOT=/home/ryzepeck/webapps/vps-ops-toolkit
MODE=check
source "${OPS_ROOT}/scripts/lib/bootstrap-common.sh"
source "${OPS_ROOT}/scripts/lib/project-definitions.sh"

PROJ="$1"   # nombre del proyecto en projects.yml (snake_case)

if is_staging "$PROJ"; then
  ENV=staging
else
  ENV=production
fi

DOMAIN="${PROJECT_DOMAINS[$PROJ]}"        # ej. azurita.projectapp.co
DB_TYPE_VAL="${DB_TYPE[$PROJ]}"            # mysql | sqlite | postgres
DB_NAME_VAL="${DB_NAME[$PROJ]:-}"
GUNICORN_SVC_VAL="${GUNICORN_SVC[$PROJ]}"
PROJ_PATH="$(resolve_projects_root)/${PROJ}"   # helper del toolkit — resuelve dev vs VPS

echo "Proyecto: ${PROJ} | Env: ${ENV} | Dominio: ${DOMAIN} | DB: ${DB_TYPE_VAL}"
```

Si `PROJECT_DOMAINS[$PROJ]` está vacío: detener y preguntar al operador (proyecto no registrado en `projects.yml` o nombre mal escrito).

### Paso B — Validar fake data (solo si `ENV=staging`)

En production este paso **se salta completo**.

```bash
"${PROJ_PATH}/backend/venv/bin/python" "${PROJ_PATH}/backend/manage.py" shell -c '
from django.apps import apps
for m in apps.get_models():
    print(f"{m._meta.label}: {m.objects.count()}")
'
```

- Si los modelos relevantes para el flujo a probar tienen `0` registros → refrescar el seed: preferir usar la skill [[fake-data-refresh]] (gate inverso de prod incluido), o directo el comando del proyecto:
  ```bash
  "${PROJ_PATH}/backend/venv/bin/python" "${PROJ_PATH}/backend/manage.py" create_fake_data
  ```
- Si el proyecto no tiene `create_fake_data` (u otro comando equivalente como `seed`, `loaddata`): **detener y avisar al operador**. No improvisar fixtures desde la skill.
- Sanity check adicional: `check --deploy` valida settings de deploy, NO integridad de FKs — para integridad usar los counts por modelo de arriba:
  ```bash
  "${PROJ_PATH}/backend/venv/bin/python" "${PROJ_PATH}/backend/manage.py" check --deploy
  ```

> **Nota DB:** la mayoría del fleet usa **MySQL `localhost:3306`** (con credenciales en `config/credentials/mysql-users.env` por proyecto). Excepciones detectables vía `DB_TYPE[$PROJ]`: `azurita` y `candle_project_staging` usan **SQLite**; Aviation usa PostgreSQL. Para validación vía Django ORM esto es transparente.

### Paso C — Autenticación y storage state (split staging/prod)

Las sesiones se guardan en rutas **separadas por entorno**, jamás mezcladas:

| Entorno | Ruta de sesión |
|---|---|
| Staging | `${XDG_STATE_HOME:-$HOME/.local/state}/vps-ops-toolkit/playwright/<proyecto>/staging/sessions/<username>.json` |
| Production | `${XDG_STATE_HOME:-$HOME/.local/state}/vps-ops-toolkit/playwright/<proyecto>/production/sessions/<username>.json` |

El estado de autenticación vive fuera del checkout vigilado. La validación no
modifica `.gitignore`, ni siquiera en staging:

```bash
STATE_ROOT="${XDG_STATE_HOME:-${HOME}/.local/state}/vps-ops-toolkit/playwright/${PROJ}/${ENV}"
SESSIONS_BASE="${STATE_ROOT}/sessions"
install -d -m 0700 "${STATE_ROOT}" "${SESSIONS_BASE}"
```

**Reglas de uso:**

- Si existe `<username>.json` y `mtime < 7 días`: reusar con `browser_set_storage_state` (cap `storage`). Internamente Playwright expone `setStorageState()` que aplica el state al context activo sin crear uno nuevo — más eficiente que el patrón viejo de `newContext({ storageState })` y compatible con Test Agents.
- Si no existe o expiró: hacer login interactivo en el browser, luego `browser_storage_state` para exportar; persistir con `chmod 600 <username>.json`.
- Si el proyecto guarda tokens en **IndexedDB** (ej. Firebase Auth, algunos SDKs SaaS): pasar `indexedDB: true` al exportar storage state — soportado desde Playwright 1.58. Default es solo cookies + localStorage.
- **Nunca** copiar manualmente un JSON entre `staging/sessions` y `production/sessions`. Son dominios distintos y cookies cruzadas son un bug semántico.
- En production, si el operador no provee `--user=` y no hay sesión válida: detener y preguntar (no auto-loguear con credenciales adivinadas).

### Paso D — URL objetivo

- **Default:** `https://${PROJECT_DOMAINS[$PROJ]}` (dominio público HTTPS del fleet, gunicorn+nginx).
- Override con argumento `--url=...` (ej. `--url=http://localhost:8000` si el operador está corriendo `manage.py runserver` localmente).
- Antes de navegar, smoke-check:
  ```bash
  curl -sf -o /dev/null -w "%{http_code}\n" "https://${DOMAIN}/api/health/" || \
    echo "Aviso: health endpoint no responde 200. Revisar systemctl status ${GUNICORN_SVC_VAL}"
  ```

### Paso E — Output dir para artefactos

Configurar el browser MCP con un output dir único por run, fuera del repo:

```bash
RUN_ID="$(date +%s)-$$"
ARTIFACTS_DIR="/tmp/playwright-mcp-${PROJ}/${RUN_ID}"
mkdir -p "${ARTIFACTS_DIR}/screenshots" "${ARTIFACTS_DIR}/traces" "${ARTIFACTS_DIR}/downloads"
echo "Artifacts: ${ARTIFACTS_DIR}"
```

Pasar a Playwright MCP `--output-dir=${ARTIFACTS_DIR}` cuando se invoque.

---

## 3. Capacidades disponibles (`@playwright/mcp` última + Playwright ≥1.57)

> Piso de versión único: **Playwright ≥1.57 (verificado 2026-07)** — cubre también los Test Agents (Planner/Generator/Healer). La skill no pina versión — usa la instalada en Claude Code.

| Categoría | Tools | Uso típico |
|---|---|---|
| Navegación | `browser_navigate`, `browser_navigate_back`, `browser_close` | Ir a URLs, volver, cerrar |
| Interacción | `browser_click`, `browser_type`, `browser_fill_form`, `browser_hover`, `browser_drag`, `browser_drop`, `browser_press_key`, `browser_select_option`, `browser_file_upload`, `browser_handle_dialog` | Llenar formularios, click, drag&drop, uploads, alerts |
| Snapshot/observación | `browser_snapshot` (a11y tree, **default — preferir éste**), `browser_take_screenshot` (evidencia visual) | Identificar selectores reales del DOM, capturas |
| Inspección | `browser_console_messages`, `browser_network_request`, `browser_network_requests` (con opciones `responseBody`, `responseHeaders` para payloads), `browser_evaluate` (acepta expresiones planas, no solo function bodies — desde MCP 0.0.71), `browser_run_code_unsafe` (renombrado de `browser_run_code` en 0.0.72; **prohibido en production**) | Logs de consola, requests con bodies, ejecutar JS |
| Espera | `browser_wait_for` | Esperar selector/texto/timeout |
| Viewport / responsive | `browser_resize` | Presets (matriz del fleet, `RESPONSIVE_STANDARDS.md` §2): **412x915 (compact · celular)**, **835x1194 (portrait · tableta vertical)**, **1195x835 (landscape · tableta horizontal)**, **1440x900 (desktop · portátil)**, **2560x1440 (wide · monitor)**. Alias legacy: `mobile`=compact, `tablet`=portrait |
| Multi-tab | `browser_tabs` (action: `list` / `open` / `switch` / `close`) | Trabajar con varias pestañas |
| Storage (cap `storage`) | `browser_storage_state`, `browser_set_storage_state`, `browser_cookie_*`, `browser_localstorage_*`, `browser_sessionstorage_*` | Sesiones reutilizables, manipular cookies |
| Network avanzado (cap `network`) | `browser_route`, `browser_unroute`, `browser_network_state_set` | **Prohibido en production** (intercept/mutate requests) |
| Vision (cap `vision`) | `browser_mouse_click_xy`, `browser_mouse_move_xy`, `browser_mouse_drag_xy`, `browser_mouse_down`, `browser_mouse_up`, `browser_mouse_wheel` | Solo si la a11y tree falla |
| Devtools (cap `devtools`) | `browser_start_tracing`, `browser_stop_tracing`, `browser_start_video`, `browser_stop_video`, `browser_video_chapter` (markers), `browser_highlight`, `browser_annotate` | Regression triage, evidencia con anotaciones (Screencast API de Playwright 1.59 permite overlays + frame capture) |
| Testing helpers (cap `testing`) | `browser_generate_locator`, `browser_verify_element_visible`, `browser_verify_text_visible`, `browser_verify_value` | Asserts naturales sin escribir Playwright TS |
| PDF (cap `pdf`) | `browser_pdf_save` | Exportar evidencia |

**Convención:** preferir `browser_snapshot` (a11y tree) para acciones; usar `browser_take_screenshot` solo cuando se necesite evidencia visual (regresiones, pruebas pixel-level, reportes al operador).

Si una cap requerida (`storage`, `testing`) no está habilitada en la config global del MCP server, la skill **lo reporta** y pide al operador habilitarla. No intentar workaround.

---

## 4. Sub-agentes Playwright (Planner / Generator / Healer) — Test Agents 1.57+

Los sub-agentes oficiales se materializan en el repo del proyecto vía:

```bash
cd "${PROJ_PATH}"
if [ ! -d ".github/chatmodes" ]; then
  npx playwright init-agents --loop=claude
  echo "AVISO: revisa los archivos generados en .github/ antes de commitear (puede chocar con CI existente)."
fi
```

| Sub-agente | Qué hace | Cuándo invocar | Restricción |
|---|---|---|---|
| **Planner** | Explora la app vía MCP y escribe `frontend/e2e/specs/<flow>.md` describiendo el plan de tests | "genera plan de tests para X" | Requiere `frontend/e2e/seed.spec.ts` con auth precargada (la skill lo crea apuntando a la sesión del paso C si falta) |
| **Generator** | Consume el spec del Planner y escribe `frontend/e2e/<flow>.spec.ts` (TypeScript Playwright) | "convierte el spec en tests ejecutables" | Después de revisar el spec |
| **Healer** | Re-ejecuta tests fallidos y propone parche o `test.skip()` | "repara los tests rotos" | **Nunca en production** — puede silenciar fallos legítimos. Solo staging y siempre revisar diff antes de aceptar |

**Orden recomendado:** Planner → revisión humana del spec → Generator → primera corrida → Healer (solo staging, solo si rompió algo legítimo).

Los sub-agentes se invocan vía la herramienta `Agent` de Claude Code, no son tools MCP ni slash commands.

---

## 5. Reglas duras production (read-only)

Como Playwright MCP **no tiene un "read-only mode" técnico**, la regla es semántica e imperativa para Claude.

### Prohibido en `ENV=production`

- `browser_evaluate` con código que mute DOM, storage, cookies o localStorage de forma persistente.
- `browser_run_code_unsafe` (cualquier uso — el sufijo `_unsafe` no es decorativo, ejecuta arbitrario en el contexto del browser).
- `browser_route` / `browser_unroute` / `browser_network_state_set` (cap `network`). Si la cap está habilitada globalmente, no usar estas tools sobre dominio production.
- Click/submit en cualquier botón cuyo texto o handler implique mutación: `Eliminar`, `Borrar`, `Crear`, `Guardar`, `Pagar`, `Confirmar pedido`, `Enviar`, `Publicar`, `Cancelar pedido`, etc.
- `browser_file_upload` (escribe en backend).
- Generación de fake data (Paso B se salta).
- Sub-agente Healer.
- `create_fake_data` u otros management commands de mutación.

### Permitido en `ENV=production`

- Navegación, hover, click en links de lectura (`<a href>` que no dispare POST/PUT/DELETE).
- `browser_snapshot`, `browser_take_screenshot`, `browser_console_messages`, `browser_network_request*` (lectura).
- `browser_resize` (viewport responsive).
- `browser_tabs` en modo lectura.
- `browser_verify_*` (asserts).
- Reproducción de bugs **sin** enviar formularios.

### Si la prueba requiere mutar en production

**Detener y avisar al operador**. Sugerir migrar la prueba al proyecto staging equivalente si existe. Mapeo conocido:

- `mimittos_project` → `mimittos` staging (si existe en `projects.yml`)
- `kore_project` → ver staging equivalente
- `tenndalux_project` (si production) → `tenndalux_project_staging`
- General: buscar `<base>_staging` en `projects.yml` antes de proponer.

### Verificación post-run en production

Comparar conteos por modelo Django **antes y después** del run para confirmar 0 deltas:

```bash
# Antes del run
"${PROJ_PATH}/backend/venv/bin/python" "${PROJ_PATH}/backend/manage.py" shell -c '
from django.apps import apps
for m in apps.get_models(): print(f"{m._meta.label}|{m.objects.count()}")
' > /tmp/playwright-mcp-${PROJ}/${RUN_ID}/counts-before.txt

# ... run de Playwright MCP ...

# Después del run
"${PROJ_PATH}/backend/venv/bin/python" "${PROJ_PATH}/backend/manage.py" shell -c '
from django.apps import apps
for m in apps.get_models(): print(f"{m._meta.label}|{m.objects.count()}")
' > /tmp/playwright-mcp-${PROJ}/${RUN_ID}/counts-after.txt

diff /tmp/playwright-mcp-${PROJ}/${RUN_ID}/counts-{before,after}.txt
# Si hay diff: ALERTA al operador. No auto-rollback, sí escalar.
```

---

## 6. Post-flight cleanup

Al terminar la sesión MCP (éxito o error):

### Borrar sin preguntar

```bash
rm -rf "/tmp/playwright-mcp-${PROJ}/${RUN_ID}"
# Si el operador no pidió conservar nada en otra ruta, borrar también runs viejos del mismo proyecto:
find "/tmp/playwright-mcp-${PROJ}" -mindepth 1 -maxdepth 1 -type d -mtime +1 -exec rm -rf {} +
# Un artefacto accidental dentro del checkout es drift: reportarlo, no borrarlo
# ni re-firmarlo desde una skill de validación read-only.
find "${PROJ_PATH}" -maxdepth 1 -type f \( -name 'page-*.png' -o -name 'page-*.jpeg' -o -name 'page-*.pdf' -o -name 'storage-state-*.json' \) -print
```

### Conservar

- `${XDG_STATE_HOME:-$HOME/.local/state}/vps-ops-toolkit/playwright/<proyecto>/<entorno>/sessions/*.json` (0700/0600, fuera del repo)
- `frontend/e2e/*.spec.ts` y `frontend/e2e/specs/*.md` si el operador pidió generación persistente (único home E2E del fleet)
- `.github/chatmodes/` si se ejecutó `init-agents` (avisar al operador para que decida commit)

### Solo si el operador pide conservar evidencia

Mover los archivos relevantes **antes** del `rm -rf` a una ruta explícita que el operador indique. Nunca dejar artefactos sueltos en `/tmp` ni en el repo del proyecto.

---

## 7. Ejemplos completos

### Ejemplo 1 — Self-QA staging

> "Acabo de cambiar el header de azurita, valida que el menú móvil funcione."

```bash
PROJ=azurita
# Paso A: detecta env=staging, DOMAIN=azurita.projectapp.co, DB=sqlite
# Paso B: count de modelos clave; si OK seguir, si vacío correr create_fake_data
# Paso C: reusar /home/ryzepeck/webapps/azurita/.playwright_staging/sessions/admin.json
# Paso D: URL=https://azurita.projectapp.co
# Paso E: ARTIFACTS_DIR=/tmp/playwright-mcp-azurita/<RUN_ID>
```

Acciones MCP:

1. `browser_resize` → 412x915 (compact)
2. `browser_navigate` → `https://azurita.projectapp.co`
3. `browser_set_storage_state` → admin.json
4. `browser_snapshot` → identificar botón hamburger
5. `browser_click` sobre el botón
6. `browser_snapshot` → verificar que el menú aparece
7. `browser_take_screenshot` → evidencia (en ARTIFACTS_DIR/screenshots/)
8. Cleanup: `rm -rf /tmp/playwright-mcp-azurita/<RUN_ID>`

### Ejemplo 2 — Reproducir bug production

> "En mimittos.com el botón 'Agregar al carrito' no responde en mobile."

```bash
PROJ=mimittos_project
# Paso A: env=production → activar reglas §5
# Paso B: SE SALTA (no fake data en prod)
# Paso C: sesión opcional desde .playwright_prod/sessions/ (solo lectura)
# Paso D: URL=https://mimittos.com
```

Acciones MCP (todas read-only):

1. counts-before.txt (snapshot de modelos)
2. `browser_resize` → 412x915
3. `browser_navigate` → `https://mimittos.com`
4. `browser_snapshot` → identificar botón
5. `browser_click` sobre "Agregar al carrito" — **permitido**: el click no muta DB en frontend (solo cambia estado del cart en localStorage del cliente, que es state efímero); pero **no** seguir hasta "Pagar" / "Confirmar pedido".
6. `browser_console_messages` → recuperar errores JS
7. `browser_network_requests` → ver si el POST falla
8. `browser_take_screenshot` → evidencia
9. counts-after.txt + diff → confirmar 0 deltas
10. Cleanup completo

Si el operador pide "ahora completa la compra para verificar el flujo entero" → **detener** y proponer migrar la prueba a staging.

### Ejemplo 3 — Generar suite E2E staging

> "Crea tests E2E para el flujo de checkout de candle_staging_project."

```bash
PROJ=candle_staging_project
# Paso A: env=staging
# Paso B: validar que existen Productos, Carritos, Usuarios; si no, create_fake_data
# Paso C: sesión cliente.json en .playwright_staging/sessions/
```

Flujo:

1. Bootstrap sub-agentes:
   ```bash
   cd /home/ryzepeck/webapps/candle_staging_project
   [ ! -d .github/chatmodes ] && npx playwright init-agents --loop=claude
   ```
2. Crear/actualizar `frontend/e2e/seed.spec.ts` con `storageState: '<ruta a cliente.json>'`.
3. Invocar Planner (Agent tool) → genera `frontend/e2e/specs/checkout.md`.
4. **Pausa para review humano del spec**.
5. Invocar Generator → genera `frontend/e2e/checkout.spec.ts`.
6. Correr `cd frontend && npx playwright test e2e/checkout.spec.ts`.
7. Si rompe: invocar Healer (solo permitido en staging).
8. Cleanup de artefactos `/tmp/`; conservar `frontend/e2e/`, `.github/chatmodes/`.
9. Avisar al operador qué archivos quedaron para revisar/commitear.

---

## 8. Troubleshooting breve

| Síntoma | Causa probable | Acción |
|---|---|---|
| `browser_set_storage_state` falla con "capability not enabled" | Cap `storage` deshabilitada en MCP config global | Pedir al operador habilitarla; no usar workaround manual con cookies |
| Sesión expirada (cookies inválidas, redirect a /login) | JSON con >7d o token revocado | Borrar `<username>.json` y hacer login nuevamente |
| `browser_snapshot` no encuentra elemento | Render lento, JS no terminó, o elemento dentro de iframe | `browser_wait_for` antes; si persiste, fallback a cap `vision` con `browser_mouse_click_xy` |
| Healer "repara" rompiendo intención del test | Healer marcó como `skip` un test que detectaba bug real | Revisar diff antes de aceptar; nunca correr Healer en production |
| Dominio devuelve 5xx | Servicio caído, no bug del test | `systemctl status ${GUNICORN_SVC_VAL}` y `journalctl -u ${GUNICORN_SVC_VAL} -n 100` |
| `git check-ignore` retorna no-match para `.playwright_prod/` | `.gitignore` mal escrito o proyecto sin `.gitignore` | Crear/corregir `.gitignore`; **no escribir sesión prod hasta que git la ignore** |
| Artefactos quedaron en `cwd` (raíz del repo) | MCP corrió sin `--output-dir` | Borrar manualmente; en próximo run pasar `--output-dir=/tmp/playwright-mcp-${PROJ}/${RUN_ID}` |

---

## 9. Handoff validate-pending (desde /qa)

> **Como fase del conductor:** desde 2026-07-25 [[qa]] ejecuta esta sección
> automáticamente como su **Fase 5b** cuando el preflight detecta app viva
> (`app_reachable=local:*|staging:*` — prod jamás). Invocada suelta, esta
> sección sigue siendo el camino manual idéntico.

Cuando la Fase 4 de [[qa]] dejó specs en DRAFT (`blocked: validate-pending` —
la app no corría durante el authoring), esta skill es el paso que los valida:

1. Con la app corriendo (staging o dev), ejecutar cada draft:
   ```bash
   cd "${PROJ_PATH}/frontend" && npx playwright test e2e/<spec>
   ```
2. Reportar pass/fail por spec.
3. En verde, indicar al operador re-correr:
   ```bash
   bash $HOME/webapps/vps-ops-toolkit/scripts/qa/qa-agent.sh --verify <proj> --files=<specs>
   ```
   (limpia el marker `.qa-gate-pending`).

Production sigue read-only: **nunca** correr flujos mutantes contra prod — los
drafts que mutan se validan sólo en staging/dev.

---

## Output final

Sin menú por diseño (§4): la validación visual ES el entregable; acciones mutantes exigen autorización explícita del operador.

Reportar siguiendo [[_output-protocol]]. Plantilla específica de esta skill
(una fila por garantía verificada en el run):

```markdown
🟢 playwright-validation OK — <proyecto> (<env>)
✨ Todo en orden — no hay acciones pendientes.

| Dimensión | Estado | Detalle |
|---|---|---|
| Detección de entorno | ✅ | <proyecto> → <env> vía is_staging |
| Fake data / seed | ✅ | modelos poblados (⏭️ en production) |
| Sesión autenticada | ✅ | storage state reusado <username>.json (<7d) |
| Flujo validado | ✅ | browser_* ejecutados, snapshot/screenshot OK |
| Aislamiento credenciales | ✅ | .playwright_<env>/ gitignored |
| Read-only en production | ✅ | diff counts before/after = 0 (⏭️ en staging) |
| Cleanup de artefactos | ✅ | /tmp/playwright-mcp-<proj>/<RUN_ID> borrado |
```

Casos de veredicto distinto a 🟢:

- 🚫 **REFUSED** — se pidió mutar en production (submit, upload, Healer,
  `create_fake_data`). Detener y sugerir migrar la prueba al
  `<base>_staging` equivalente.
- ⏸️ — requiere login interactivo (sin sesión válida) o review humano del
  spec del Planner antes del Generator.
- ⚠️ — sesión expirada, cap MCP (`storage`/`testing`) no habilitada, o la
  a11y tree no encontró el elemento (fallback a `vision`).
- ❌ — dominio 5xx (servicio caído, no bug del test) o flujo roto real.

## Next steps
- (si 🚫 REFUSED — prod muta) migrar la prueba al `<base>_staging` equivalente
- (si ⚠️ sesión) borrar `<username>.json` y re-login interactivo
- (si ❌ 5xx) `systemctl status <GUNICORN_SVC>` + `journalctl -u <svc> -n 100`
