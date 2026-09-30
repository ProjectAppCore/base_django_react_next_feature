---
name: "debug"
description: "Agentic debug mode — diagnose and analyze bugs without modifying code. Read-only 4-phase workflow producing diagnosis and recommended fix. Use when the user reports a bug, error, or unexpected behavior."
---

# Debug Mode

Act as an expert debugger. Your job is to **analyze and diagnose only**. Follow these phases sequentially. Do not skip phases. Do not guess — gather evidence first.

> **STRICT RULE — READ-ONLY WORKFLOW**
> You must **NEVER** modify, edit, create, or delete any file during this workflow.
> You may: search code, read files, run read-only terminal commands (`git log`, `git diff`, `grep`) — reproducing the bug with a test or a read-only command IS allowed.
> You must NOT: write code, apply fixes, create files, or run anything that MUTATES state (writes, migrations, deploys) — no changes to the codebase.
> Your deliverable is a **diagnosis + recommended fix** — the user decides when and how to apply it.

## Cómo invocar este skill

Gating ($output-protocol §4): con `$ARGUMENTS` o intención clara en la sesión → ejecutar directo, PROHIBIDO preguntar el tema (un dato menor faltante se marca en el texto, no se convierte en pregunta). Sin argumentos ni contexto → UNA sola pregunta corta en texto por el bug a diagnosticar (no picker: el insumo es libre). Nunca en modo fleet/headless/cron.

Sin picker por diseño: no hay flags de modo — el argumento es el bug: mensaje de error, stack trace o comportamiento inesperado.

---

## Phase 1 — Error Capture & Context Gathering

1. If the user provided an error message or stack trace, read it carefully. If not, **ask for it** before proceeding. Request:
   - The full error message or unexpected behavior description.
   - The complete stack trace (if applicable).
   - The file and line where it occurs.
   - What changed recently before the error appeared.

2. Read the failing file and its direct dependencies (imports, called functions, referenced modules).

3. Check recent changes that may have introduced the bug:
```bash
git log --oneline -10
```
```bash
git diff $(git merge-base HEAD origin/HEAD 2>/dev/null || echo HEAD~1)..HEAD --stat
```

4. If the project maintains error documentation, check `docs/methodology/error-documentation.md` for previously resolved similar issues.

---

## Phase 2 — Root Cause Analysis

Analyze the error using structured reasoning. Present findings in this exact format:

### OBSERVATIONS
- What the error message says literally.
- Where it occurs (file, line, function).
- What the data/state looks like at the point of failure.
- Any patterns in the stack trace.

### HYPOTHESIS
- The most likely root cause, stated as a single sentence.
- If multiple causes are possible, rank them by probability and explain why.

### EVIDENCE
- Specific code lines (with file path and line numbers) that confirm the hypothesis.
- Variable states, data flow, or execution paths that lead to the failure.
- If applicable, the specific git commit or diff that introduced the bug.

**Rules for this phase:**
- If you are **not confident** in the hypothesis, do NOT proceed to Phase 3. Go back to Phase 1 and gather more context.
- Always identify the **root cause**, not symptoms. Think upstream, not downstream.

---

## Phase 3 — Recommended Fix

Present the recommended fix **without applying it**:

### 3.1 Root Cause Summary
One paragraph explaining why the bug exists.

### 3.2 Proposed Change
Show **before/after** code snippets with exact file paths and line numbers.

### 3.3 Why This Works
Explain why this change addresses the root cause, not just the symptom.

### 3.4 Risk Assessment
- Side effects or areas that could be affected.
- Edge cases to manually verify.
- Whether this change could break other functionality.

### 3.5 Prevention
How to avoid this class of bug in the future.

> **Reminder: do NOT apply the fix.** The user will apply it manually or in a separate session.

---

## Phase 4 — Verification Plan

1. **Reproduce** — The exact steps or command to trigger the original bug.
2. **Validate** — The specific test(s) or command(s) to run after applying the fix.
3. **Regression** — Which related tests, modules, or flows should be checked.

---

## Iteration Protocol

If the user reports the recommended fix did not work:
1. Read the new error output carefully.
2. Return to **Phase 2** with additional context.
3. Recommend **reverting** the failed fix before trying a different approach.
4. After **2 failed recommendations**, pause and ask the user for runtime logs, exact code state, and any additional context.

---

## Output final

Sin menú por diseño (§4): read-only por diseño; el diagnóstico ES el entregable y el fix se decide fuera.

Reportar siguiendo $output-protocol. Plantilla específica de esta skill (read-only: diagnostica, NO aplica el fix):

🟢 debug OK   (🟡 si la hipótesis no alcanzó confianza alta; 🔴 si no se pudo reunir evidencia)

| Dimensión | Estado | Detalle |
|---|---|---|
| Causa raíz | ✅ | identificada, con evidencia (archivo:línea) |
| Fix recomendado | ✅ | before/after propuesto — NO aplicado (read-only) |
| Riesgo de regresión | ✅ | side-effects + edge cases a verificar anotados |
| Plan de verificación | ✅ | repro + validate + tests de regresión listados |
| Iteraciones | ✅ | ≤2 recomendaciones; ⏸️ pausado tras 2 fallos (pedir logs/estado exacto) |

## Next steps
- (manual, operador) aplicar el fix before/after propuesto — esta skill no modifica archivos
- tras aplicar: correr el comando de "Plan de verificación" para validar + chequear regresión
- si la causa raíz es de rendimiento (lentitud, N+1, timeout, memoria por request, cola de tareas bloqueada): `$perf-pass <requerimiento>` — modo A de $perf-pass: declara el perfil de cómputo del host, aplica en el worktree de la sesión y deja el guion a $qa, en lugar de un fix a mano
