---
name: new-feature-checklist
description: "Checklist for new features — ensures fake data creation follows business rules and test coverage is complete across backend, frontend unit, and E2E layers."
---

# New Feature Checklist

> **La forma canónica de ejecutar los pasos 1-3 es invocar [[qa]]** — el
> conductor corre flow-map → cobertura (backend/unit/e2e) → gate → test-audit
> como fases ordenadas con las guardas de producción ya cableadas (y salta
> fake-data en prod solo). Esta checklist queda como la vía granular manual.
>
> **Rendimiento del requerimiento (paso 5):** antes de `/qa`, [[perf-pass]] modo A declara el
> perfil de cómputo del host y los presupuestos del camino nuevo, aplica lo acotado en el mismo
> worktree y deja el guion `brief-perf`; `/qa` escribe los tests de presupuesto.

## Cómo invocar este skill

Gating ([[_output-protocol]] §4): con `$ARGUMENTS` o intención clara en la sesión (la feature recién implementada) → ejecutar directo, PROHIBIDO preguntar el tema (un dato menor faltante se marca en el texto, no se convierte en pregunta). Sin argumentos ni contexto → UNA sola pregunta corta en texto por la feature a cubrir (no picker: el insumo es libre). Nunca en modo fleet/headless/cron.

Sin picker por diseño: no hay flags de modo — el argumento es la feature cuya fake data y cobertura se cierran.

## 1. Fake Data Creation / Validation (Backend)

Before creating test data, verify that fake data complies with:
- **Business rules**: Data reflects valid real-world scenarios
- **Model validations**: Constraints, types, ranges, formats
- **Expected exceptions**: Error cases and edge cases
- **Model dependencies**: FK relationships, referential integrity, creation order

> Do not generate random data without context. Each factory/fixture must represent a valid system state.

### Post-implementation refresh

After completing this implementation or fix, the previously-created fake data may have become incoherent: new model fields default to null/empty in old records, new FK relationships have no backing data, business rules added in this change are not reflected. Re-validate and refresh.

**Trigger refresh whenever this implementation/fix changed any of:**
- Model fields (new field, new constraint, modified validator)
- Foreign keys / relations (new FK, removed model, restructured M2M)
- Business logic (new validation, new domain rule, status transitions)
- Serializers/forms with required fields not previously enforced

**Quality target — "many records that make sense":**
- Multiple records per model (not 1–2 placeholders) so flows can be exercised with realistic permutations.
- FK chains populated end-to-end (e.g. for an Order: User → Cart → Items → Payment → StatusHistory all coherent).
- Edge cases represented: empty strings where allowed, max-length values, nullable fields exercised both filled and null, expected-error states.

**To execute the refresh:** invoke the `fake-data-refresh` skill on this project. It runs the project's own `delete_fake_data` then `create_fake_data` management commands and refuses on production environments.

## 2. Test Coverage

### Create tests for the new functionality:

| Layer | Test Types |
|-------|-----------|
| Backend | Unit, Integration, Contract, Edge Cases |
| Frontend | Unit |
| Frontend | E2E (user flows) |

### Quality Standards Reference

Before writing any test, consult: `docs/TESTING_QUALITY_STANDARDS.md`

### Backend Tests
Cover: happy paths, edge cases, error handling.
Per-test: ONE behavior, no conditionals, observable assertions, deterministic, isolated, AAA pattern.

### Frontend Unit Tests
Cover: happy paths, edge cases, error handling, all branches.
Per-test: ONE behavior, sin acceder a internals del componente (`wrapper.vm.*` en Vue, instancias internas en React), stable selectors, one mount, timers restored.

### Frontend E2E Tests
Cover: happy paths, error states, edge cases, contract validation.
Per-test: `@flow:` + `@outcome:<success|error|failure|display>` tags (un spec sin ambos tags no gana crédito de cobertura), role-based selectors, no `waitForTimeout()`, real user interactions only.

## 3. Update User Flow Map

Update the flow registry if new user flows are created — o invocar [[e2e-user-flows-check]], que lo mantiene en el layout del repo (sharded: un JSON por flow + doc por flow, agregados regenerados con `generate_flow_registry.py`; monolito: `docs/USER_FLOW_MAP.md` + `frontend/e2e/flow-definitions.json`).

## 4. MCP contract parity

Only for projects that expose MCP connectors — skip this section entirely when
the project has no MCP contract registry. If the changed model, serializer,
service, lifecycle or relation belongs to a module listed in that registry (in
projectapp, `backend/content/mcp/contracts.py`), the same delivery MUST:

- classify every added or changed field as read-only, read/write, or
  deliberately excluded with a concrete reason;
- compare tool descriptions, input schemas, handlers, filters and response
  payloads against the panel's current serializer/service contract;
- preserve the shared token auth, actor attribution, audit and throttle pattern;
- update the project's MCP validation runbook (in projectapp,
  `docs/MCP_VALIDATION_RUNBOOK.md`) and run the focused MCP contract tests plus
  the create/read/update/error cases.

An unclassified model field, or a tool that advertises data it silently drops,
is a failed checklist even when the ordinary panel tests are green.

## 5. Presupuesto de rendimiento (perf-pass)

Si la feature agregó vistas, listados, serializers, tareas o páginas, correr [[perf-pass]] en
modo A con el requerimiento como argumento (`/perf-pass <requerimiento>`): imprime el perfil
de cómputo del host real, contrasta el camino nuevo contra `docs/PERFORMANCE_STANDARDS.md`
(queries por request constantes, filas materializables, presupuesto de tarea, bundle) y aplica
sólo cambios acotados dentro de LÍMITES en el mismo worktree. Su salida es el guion
`brief-perf` que `/qa` convierte en tests de presupuesto (`CaptureQueriesContext`,
`MAX_*_QUERIES`, `toHaveBeenCalledTimes`; nunca tiempo). Sin camino de datos nuevo: ⏭️.

## 6. Paridad del Mapa de vistas

Sólo para proyectos con Mapa de vistas — saltear esta sección entera si el repo
no tiene `frontend/config/viewCatalog.js` o si la skill [[view-map-update]] no
está instalada para este runtime (en projectapp, `/panel/views`). Si la feature
agregó, quitó, renombró o cambió de propósito una página, pestaña, modal o
capacidad visible, la misma entrega DEBE correr [[view-map-update]] con
`--apply --diff` (nunca pregunta: hereda el gating de esta checklist), para que
catálogo, Explorador, contratos acoplados y conteos fijados en tests y docs
queden al día en el mismo PR. Si [[implement]] o [[qa]] ya la corrieron sobre
este mismo diff, citar esa corrida en vez de repetirla.

Una página nueva sin entrada, o una capacidad nueva que el Explorador no
describe, es un checklist fallido aunque `npm run check:view-catalog` y los
tests del panel estén verdes.

## Execution Order

1. **First**: Run only the new tests → Must pass
2. **Then**: Run only regression tests
3. **Never**: Run the full test suite

### Limits
- Frontend E2E: max 20 tests per batch, 3 commands per cycle
- Backend: activate venv first (`source venv/bin/activate`); for `db: mysql` projects run tests with `DJANGO_ENV=production`

---

## Output final

Sin menú por diseño (§4): es un checklist-guía; la ejecución canónica es /qa.

Reportar siguiendo [[_output-protocol]]. Plantilla específica de
`/new-feature-checklist`:

```markdown
🟢 new-feature-checklist OK — <feature-name>
✨ Todo en orden — no hay acciones pendientes.

| Dimensión | Estado | Detalle |
|---|---|---|
| 1.a Fake data — business rules | ✅ | factories respetan validators + edge cases |
| 1.b Fake data — refresh post-impl | ✅ | fake-data-refresh corrido si tocó modelos/FK |
| 2.a Backend tests | ✅ | unit + integration + contract + edge |
| 2.b Frontend unit tests | ✅ | happy + edge + branches, selectores estables |
| 2.c Frontend E2E tests | ✅ | @flow:<id> + @outcome:<clase>, real-user interactions, sin shortcuts |
| 3 USER_FLOW_MAP.md | ✅ | nuevos flows registrados (si aplica) |
| 4 Paridad MCP | ✅ | campos clasificados, tools/schemas/runbook al día — o n/a si el proyecto no expone MCP |
| 6 Mapa de vistas | ✅ | catálogo + Explorador + conteos al día — o n/a si no hay mapa de vistas |
| Suite no completa | ✅ | solo nuevos + regresión, batch ≤20, ciclos ≤3 |
```

Si la skill detecta que el feature tocó modelos/FK pero no se corrió
`fake-data-refresh`, o algún layer de tests no fue cubierto, reemplazar el ✅
correspondiente por ⚠️/❌, omitir la línea ✨ y agregar `## Next steps` con la
skill o el comando exacto a invocar (ej. `/fake-data-refresh <proyecto>`,
`pytest <path>`, etc.).
