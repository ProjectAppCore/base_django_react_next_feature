---
name: "output-protocol"
description: "Contrato compartido del bloque final de respuesta de toda skill operacional del fleet. Importado por las skills bajo workflows/.claude/. No invocable directamente."
---

# Output protocol — bloque final estándar

> Este archivo NO es una skill invocable. Es la fuente canónica del formato
> final con el que toda skill operacional del fleet cierra su ejecución. Las
> skills lo referencian con `$output-protocol` en su sección "Output final".

## Por qué existe

El operador corre la misma skill (`$init-fleet`, `$full-audit`, `$server-diagnostic`,
`$git-status-report`, etc.) en múltiples hosts a lo largo del día. Si cada
skill cierra de forma distinta, leer "qué OK / qué falta" tarda más y se
escapan signals. El protocolo unifica:

- **Veredicto** en una línea — captable en <1 segundo
- **Tabla** de dimensiones con emoji por estado — escaneable
- **Next steps** con comando exacto — copy-paste sin interpretación

## Estructura obligatoria

Toda skill cierra con estas tres secciones, en este orden:

### 1. Veredicto (una línea)

Un solo emoji + frase corta. Umbrales **derivados de la tabla** (sección 2):

| Veredicto | Cuándo (regla exacta) |
|---|---|
| `🟢 <skill> OK` | Todas las celdas de la tabla son ✅ (cero ⚠️, cero ❌) |
| `🟡 <skill> OK con N warning(s)` | ≥1 celda ⚠️, cero ❌ — completó, no bloquea |
| `🔴 <skill> — N error(es), revisar arriba` | ≥1 celda ❌ — algo falló inesperadamente |
| `⏸️ <skill> — pausa manual pendiente` | Flujo normal pero requiere operador (OAuth, admin console, otra dev) |
| `🚫 <skill> — REFUSED (<razón>)` | Safety gate intencional rechazó la operación (prod detectada, intent peligroso) — **no es error**, es decisión segura |
| `⏭️ <skill> — N/A o saltado` | No aplica al contexto (skip-flag pasado, ya en estado correcto) |

Cuando TODAS las celdas son ✅ (veredicto 🟢) y no queda ningún pendiente,
puede añadirse debajo del veredicto la línea opcional — convención ya en uso
amplio en el catálogo:

```markdown
✨ Todo en orden — no hay acciones pendientes.
```

En ese caso la sección `## Next steps` se omite (§3).

### 2. Tabla de dimensiones

```markdown
| Dimensión | Estado | Detalle |
|---|---|---|
| <fase / aspecto> | <emoji> | <una frase, ≤80 chars> |
```

Códigos de emoji (para celdas de la tabla):

| Emoji | Significado |
|---|---|
| ✅ | done — completado correctamente |
| ⚠️ | warning — completado con observaciones, no bloquea |
| ❌ | error — falló, requiere acción |
| ⏭️ | skipped — saltado por flag o no-aplica |
| ℹ️ | info — informativo, sin estado binario |
| 🚫 | refused — bloqueado por safety gate (decisión segura, no fue error) |
| ⏸️ | paused — esperando intervención manual del operador (OAuth, admin console) |
| 🟢🟡🔴 | reservados para el VEREDICTO; **nunca** en celdas individuales |

Regla de longitud: **≤80 chars por celda** (no por tabla). Una tabla puede
tener N filas mientras cada celda cumpla la regla.

Si la skill corrió en múltiples hosts/proyectos, agregar columna `host` o
`proyecto` ANTES de `Dimensión`.

**Si la tabla supera 15 filas**, agregar sección `### Top 3 acciones prioritarias`
ENTRE el veredicto y la tabla — listando los 3 items más críticos con su
comando exacto. El operador lee el Top 3 primero; la tabla queda como detalle
profundizable.

### Excepción: skills cuyo output ES el producto

Skills donde la respuesta misma es el entregable para un humano — a veces no
técnico — (hoy: `human`, `user-walkthrough`, `where-are-we`): una tabla de dimensiones al
final sólo mete ruido sobre el producto. Estas skills cierran SÓLO con la
línea de veredicto (§1), sin tabla §2 ni Next steps técnicos, y deben
declarar la excepción en su propio `## Output final`.

### 3. Pendientes / next steps (omitir si no aplica)

```markdown
## Next steps
- `<comando exacto a copiar>` — qué hace
- (manual, operador) <instrucción concreta>
- (otro VPS / cron / otra dev) <instrucción + dónde se ejecuta>
```

Cada bullet debe ser **accionable sin interpretación**: comando exacto + dónde
correrlo + qué actor lo hace.

### 4. Acciones disponibles y picker de invocación (menú interactivo)

Dos posiciones, un mismo esquema de fila:

- **Pre-run (picker de invocación) — OBLIGATORIO** para toda skill cuyo
  `argument-hint` incluya un flag de modo mutante o de alcance (`--apply`,
  `--all-*`, `--cutover`, `--revoke`, selectores `--check|--apply`…). Se
  declara en una sección propia **`## Cómo invocar este skill`** (tras el
  intro, antes de las fases) con: (a) las reglas de gating de abajo
  instanciadas para la skill, (b) las Q-specs en formato tabla
  `label · description · preview` — la misma forma del menú post-run —,
  (c) el párrafo **"Qué NO se pregunta"** (flags que se tipean a propósito:
  overrides del blocklist, defaults simétricos). Una skill cuyos flags son
  sólo tuning aditivo (puertos, filtros, `--records=N`) puede eximirse con la
  línea literal `Sin picker por diseño: <razón>` dentro de esa sección —
  picker O waiver, nunca silencio (así el lint es decidible). Referencias
  canónicas: $sync-ai-ecosystems (Q1/Q2/Q3, targets gateados) e
  `init-fleet` (probe de entorno antes de armar opciones; multiSelect para
  add-ons; documenta qué flags quedan fuera del picker).
- **Post-run (escalaciones):** skills con default mínimo/read-only. DESPUÉS del
  reporte (§1-§3), UNA sola `AskUserQuestion` que ofrezca las demás acciones de
  la skill, para que el operador descubra capacidades sin memorizar flags.

**Gating obligatorio (ambas posiciones):**

1. El operador pasó flags/argumentos explícitos → ejecutar directo, **sin menú**.
2. La intención es clara por el contexto de la sesión → proponer el comando en
   texto y esperar confirmación, sin picker.
3. Sin argumentos / intención difusa → disparar la pregunta.
4. **Nunca** en modo fleet/headless/cron ni dentro de un barrido — sólo en
   sesión interactiva single-target.
5. Máx **4 opciones** ("Other" ya existe siempre); lo que no entra se nombra en
   `## Next steps`.
6. **multiSelect cuando las opciones combinan** (`multiSelect: true` para
   add-ons, listas de targets, capas — opciones no excluyentes entre sí);
   selección única sólo para modos excluyentes.
7. **Una sola llamada:** todas las preguntas aplicables se fusionan en UNA
   `AskUserQuestion` (Q1+Q2+Q3 juntas, estilo $client-message). Un dato
   faltante posterior se pide en texto plano una única vez (≤3 bullets) —
   nunca un segundo picker.
8. **Runtimes sin `AskUserQuestion`** (Codex/`.agents`): renderizar
   las mismas filas como lista numerada en texto y esperar la respuesta
   tipeada — la spec es la misma, sólo cambia el medio.

**Esquema de fila:** `label` corto (sufijo `(Recommended)` sólo si la acción es
segura y reversible) · `description` de 1 línea que incluya costo/efecto real
("envía email real, cooldown 1h") · `preview` = **el comando exacto** que se
ejecutaría.

**Blocklist — filas que NINGUNA skill puede ofrecer como opción clickeable:**

- `$deploy-and-check` o `post-deploy-check.sh` (manual-only por política — sólo
  como texto en Next steps).
- Merge de una rama release: no se ofrece ni se tipea — lo decide
  `release_merge:` en projects.yml (fuente de verdad, consultada por
  $merge-when-green en cada invocación).
- Merge del PR de la sesión (`gh pr merge`, `$merge-when-green`): ninguna
  skill lo ofrece como fila — el DoD de sesión es PR abierto + CI verde; el
  merge es de `$merge-queue` o del operador (sólo como texto `(operador)` en
  Next steps).
- `migrate-project --cutover` (exige `--confirm-downtime` TIPEADO — un click no
  es una confirmación de downtime).
- `--include-projects` de bootstrap/init-fleet como Recommended (es
  deploy-equivalente).
- Git destructivo: `reset --hard`, `push --force`, `stash drop` masivo
  (per-stash sólo si la skill lo clasificó OBSOLETO/VIEJO, con evidencia).
- Revocaciones que commitean (`--revoke=<id>`) sin su fila `--dry-run` previa.
- Flags retirados o error-by-design (`git-sync --all`, `git-commit --all-vps`).
- Restarts/acciones de servicio antes de leer el journal (regla de incident).
- Deletes no evidenciados: siempre por lote, con lista y evidencia visibles.

**Cómo lo declara una skill:** el picker pre-run vive en `## Cómo invocar este
skill`; el menú post-run en una sección `## Acciones disponibles` con su tabla
de filas (label · description · preview) ANTES del `## Output final`. Los alias
heredan ambos de su skill base (regla de `## Skills alias`). Una skill exenta
del menú post-run lo declara con la línea literal `Sin menú por diseño (§4):
<razón>` (p. ej. las output-es-el-producto de §2) — así se distingue excepción
de drift.

## Reglas

- **Idioma:** español. Términos técnicos en inglés cuando son canónicos
  (`commit`, `rebase`, `chmod`, `staging`, `lifecycle`).
- **Sin prosa redundante** después de la tabla. Nada de "En resumen, todo
  está OK excepto..." — la tabla ya lo dice.
- **Línea de avance teórico:** la respuesta cierra con la línea `📊 Avance …` que
  exige la regla fleet-base «Avance teórico en cada respuesta» (`CLAUDE.md` /
  `AGENTS.md`): va después de Next steps y no cuenta como prosa redundante. En las
  skills que fijan su última línea (el veredicto de las de output-es-el-producto,
  `Report path:`) va justo antes de esa línea. Si el reporte de la skill ya es la
  línea de avance —la línea «Global» de $where-are-we—, no se duplica.
- **Sin headers tipo "Phase 1", "Step 2"** en el reporte final — categorizar
  por **tema**, no por orden de ejecución.
- **Cada celda de estado** se navega en <1 segundo: un emoji + ≤80 chars de
  detalle. Si necesitas más texto, partir en filas.
- **Comandos exactos**, no parafraseados. `bash scripts/foo.sh --apply` sí;
  "correr el script de foo en modo apply" no.
- **No repetir info** que ya está en la tabla. Next steps son acciones, no
  resúmenes.
- **Máx. 3 comandos de verificación por ciclo** — nunca una suite completa
  como verificación de un cambio puntual.

## Ejemplo (skill $init-fleet, modo apply, dev)

```markdown
🟡 init-fleet OK con 2 warning(s)

| Dimensión | Estado | Detalle |
|---|---|---|
| setup-dev-machine | ✅ | git alias, prompt, statusline OK |
| tailscale install/enable | ✅ | tailscaled enabled, versión 1.78.1 |
| tailscale auth | ⏸️ | requiere `sudo tailscale up --ssh` (browser OAuth) |
| add-self registry | ⏭️ | depende de auth previa |
| ssh-fleet backup | ⏭️ | flag --include-ssh no pasado |
| ssh-fleet-check | ⚠️ | 1 VPS no responde Tailscale (vps-gym) |

## Next steps
- `sudo tailscale up --ssh` — completar OAuth en browser de la dev
- `bash scripts/bootstrap/init-fleet.sh --apply` — re-correr tras auth
- (admin console) Disable key expiry para esta dev en https://login.tailscale.com/admin/machines

📊 Avance ▰▰▰▰▰▰▰▱▱▱ 70 % — falta: OAuth de Tailscale y re-correr init-fleet
```

## Cómo referenciar este protocolo desde una skill

Al final de cada skill `.md`:

```markdown
## Output final

Reportar siguiendo $output-protocol. Plantilla específica de esta skill:

| Dimensión | Estado | Detalle |
|---|---|---|
| <fase específica> | ✅/⚠️/❌ | ... |
| ... | | |

## Next steps (si aplica)
- <comando exacto>
```

Skills que ya tienen tablas ricas (server-diagnostic, repo-cleanup,
fix-broken-tests) conservan su estructura — solo se aseguran de:
1. Usar el set canónico de emojis (✅⚠️❌⏭️ℹ️🚫⏸️ + 🟢🟡🔴 solo para veredicto).
2. Cerrar con veredicto en una línea.
3. Listar next steps con comando exacto.

Si la skill ofrece menú interactivo (§4), lo declara así (antes del Output final):

```markdown
## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos
(reglas de gating de $output-protocol §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| ... (Recommended) | ... | `bash …` |
```

## Skills alias

Una skill que es wrapper/alias de otra (ej. `debugme` → `debug`, `plan-task` →
`plan`) **NO duplica** la plantilla del Output final. Su sección final dice:

```markdown
## Output final

Reportar siguiendo $output-protocol. Misma plantilla que `/<skill-base>`.
```

Eso evita drift entre la skill base y el alias: si la base cambia su tabla,
el alias hereda el cambio automáticamente sin re-edición.
