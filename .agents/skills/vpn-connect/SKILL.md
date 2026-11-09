---
name: "vpn-connect"
description: "Conecta ESTE host a la VPN del fleet de punta a punta y verifica que el fleet sea REALMENTE alcanzable: instala/enablea el daemon de la VPN si falta, corre `<cli-vpn> up --ssh` (con --hostname en VPS), captura la URL de login y te la muestra en la respuesta para que la autorices en el browser, verifica el nodo (status + IP 100.x + ssh cap) y además sondea una sesión `<cli-vpn> ssh` real contra un peer para detectar el *check mode* — la re-auth por browser que NO se ve en `<cli-vpn> status` y que frena la primera operación cross-VPS. Nodo conectado con check mode pendiente NO es verde: devuelve el link. Idempotente: si el nodo ya está conectado no re-autentica, pero el probe corre igual. Complementa a $bootstrap-vpn-fleet (onboarding/audit/registry)."
---

# Tailscale Connect

Conecta **el host actual** al tailnet del fleet de punta a punta y **te devuelve
el link de login en la respuesta** para que lo autorices en el browser, luego
verifica que la conexión quedó arriba. Es el complemento operativo de
$bootstrap-vpn-fleet: aquél *imprime* el comando `tailscale up` y delega
el OAuth; **este skill lo corre, scrapea la URL, espera tu aprobación y verifica**.

> **⚠️ Cómo invocar**:
> - `$vpn-connect` → conecta este host (o, si el nodo ya está conectado,
>   salta directo al probe de alcance al fleet).
> - `$vpn-connect --check` → diagnóstico read-only (Phase 0 + Phase 4), no
>   conecta ni re-autentica, pero SÍ sondea el *check mode*.
> - `$vpn-connect --no-ssh-probe` → sólo el estado local del nodo; el
>   alcance al fleet queda sin verificar (y se dice en el reporte).
> - Opera **siempre sobre el host donde corre la sesión** (identificado por
>   `hostname -s`). No corre trabajo en otros VPS; el único contacto con un peer
>   es el probe read-only de Phase 4 (`tailscale ssh <peer> true`).

## Cómo invocar este skill

Gating ($output-protocol §4): (1) flag explícito (`--check`) → directo, sin menú;
(2) intención clara por contexto ("conectá este host al tailnet") → proponer el comando
en una línea y esperar confirmación; (3) sin args → UNA AskUserQuestion (Q1); (4) nunca
en fleet/headless/cron — el OAuth exige al operador en el browser.

**Q1 — Modo** (`multiSelect: false`):

| label | description | preview |
|---|---|---|
| Conectar este host (Recommended) | conecta el nodo si hace falta y verifica el alcance real al fleet; si el nodo ya está conectado no re-autentica, sólo sondea | `$vpn-connect` |
| --check | verificar sin mutar nada: estado local + probe del *check mode* | `$vpn-connect --check` |

**Qué NO se pregunta:** el `--hostname` del `tailscale up` lo decide Phase 0 según el
host, nunca el operador. **Tampoco se pregunta si sondear el fleet**: el probe es el
dato que motiva la skill y corre siempre — `--no-ssh-probe` existe para offline y se
tipea, no se ofrece.

## Cuándo usarla

- Workstation nueva o VPS recién provisionado que todavía no está en el tailnet.
- Tras un `tailscale down` / logout / expiración de key: reconectar rápido.
- Cuando querés el link de auth servido en la respuesta en vez de tipear el
  `tailscale up` a mano y copiar la URL de la terminal.

Para **auditar** el tailnet, **registrar** el nodo en `expected-nodes.yml`, o el
onboarding completo bimodal, usá $bootstrap-vpn-fleet / $init-fleet.

## Diferencia con $bootstrap-vpn-fleet

| Aspecto | vpn-connect (este) | bootstrap-vpn-fleet |
|---|---|---|
| Corre `tailscale up` | **Sí** (background + captura URL) | No, sólo lo imprime |
| Muestra el link en la respuesta | **Sí** | No |
| Espera aprobación + verifica | **Sí** | No (delega al operador) |
| Toca el registry / admin console | No | Sí (`--add-self`, `--audit`) |
| Alcance | Sólo el host local | Bimodal dev/VPS + fleet |

## Procedimiento (lo que Claude ejecuta)

### Phase 0 — Identificar host + preflight (read-only)

1. `hostname -s` → mapear a alias: `srv571894`→vps-projectapp-staging,
   `srv1681495`→vps-projectapp-prod, `srv614758`→vps-gym. Dev machine si
   `is_dev_machine` (helper de `scripts/lib/bootstrap-common.sh`).
2. Decidir el flag de conexión: **dev** → `tailscale up --ssh`; **VPS** →
   `tailscale up --ssh --hostname=$(hostname -s)`.
3. Preflight:
   - Instalado? `command -v tailscale`
   - Daemon? `systemctl is-active --quiet tailscaled`
   - **Ya conectado?** `tailscale status >/dev/null 2>&1`
4. **Corto-circuito idempotente**: si ya está conectado, **saltar Phases 1-3**
   (no re-autentica el nodo) y **seguir en Phase 4** — el probe de sesión SSH.
   ⚠️ **NO terminar acá.** Cortar en este punto es lo que producía el falso
   «🟢 ya conectado» que después se frenaba pidiendo el link en la primera
   operación cross-VPS: `tailscale status` sólo prueba que el NODO está en el
   tailnet, nunca que la sesión SSH esté autorizada (*check mode*).
   Con `--check` vale lo mismo: se saltan las fases mutantes, pero Phase 4 corre
   igual — es read-only y es el dato que el operador vino a buscar.

### Phase 1 — Install + enable (sólo si falta)

```bash
curl -fsSL https://tailscale.com/install.sh | sh     # si no está instalado
sudo systemctl enable --now tailscaled                # si el daemon no corre
```

### Phase 2 — Conectar + capturar el enlace

`tailscale up` **bloquea** hasta que autorices en el browser, así que se corre en
**background** y se le scrapea la URL:

1. Lanzar en background (Bash `run_in_background`), redirigiendo a un logfile en
   el scratchpad, el comando decidido en Phase 0:
   ```bash
   sudo tailscale up --ssh [--hostname=$(hostname -s)]   # > <scratch>/tsup.log 2>&1
   ```
2. Detectar el prompt de auth y extraer la URL del logfile (mismo patrón que
   `scripts/maintenance/propagate-toolkit-commit.sh`):
   - prompt: `grep -qiE 'to authenticate, visit|requires an additional check'`
   - URL: `grep -oE 'https://login\.tailscale\.com/[A-Za-z0-9/._-]+' <log> | head -1`
   - usar un `until grep ... <log>` en background (o `Monitor`) para detectar la
     URL apenas aparece (~1-2s).
3. **Mostrar la URL en la respuesta** (esto es el "me lo da en su respuesta"):
   > Abrí este link en el browser y autorizá con la cuenta Google del fleet
   > (`core.paginaswebscolombia@gmail.com`): **`<URL>`**
   > (En un VPS: abrilo en el browser de tu **dev**, no en el del VPS.)

**Caveat sudo**: si `sudo` pide password y no es passwordless, el comando en
background cuelga. Fallback: mostrar el comando exacto para que lo corras vos con
el prefijo `! sudo tailscale up …` en el prompt, y continuar en Phase 3. (En los
hosts del fleet sudo suele ser passwordless — los scripts de bootstrap lo asumen.)

### Phase 3 — Esperar aprobación + verificar

1. El operador abre el link y autoriza. Al autorizar, el `tailscale up` en
   background **sale 0** → llega la notificación de completion del harness (ese es
   el "wait" natural). Como red de seguridad, poll acotado:
   `until tailscale status >/dev/null 2>&1; do sleep 3; done` (tope ~3 min).
2. Verificar (triada de `scripts/diagnostics/tailscale-fleet-check.sh`):
   - `tailscale status` sale 0
   - `tailscale ip -4 | head -1` devuelve una IP `100.x`
   - nodo: `tailscale status --json | jq -r '.Self.DNSName // "" | split(".")[0]'`
   - (VPS) ssh cap habilitado:
     `tailscale status --self --json | grep -q '"https://tailscale.com/cap/ssh"'`
3. Next steps a sugerir:
   - Si el nodo **no** está en `config/tailscale/expected-nodes.yml`:
     `$bootstrap-vpn-fleet --add-self` para registrarlo.
   - (VPS) recordatorio manual: *Disable key expiry* en el admin console
     (https://login.tailscale.com/admin/machines) — el Free plan no expone API.

### Phase 4 — Probe de sesión SSH (*check mode*) — read-only, SIEMPRE

**Por qué existe (no la saltes):** «nodo conectado» y «puedo hacer `tailscale
ssh` al fleet» son **dos autorizaciones distintas**. La triada de Phase 3 mide
la primera: el nodo está registrado y online (`Online: true`). La segunda es el
*check mode* de Tailscale SSH — una re-auth por browser, **por operador y con
ventana de tiempo**, definida en la ACL del tailnet, que sólo se materializa
cuando intentás una sesión SSH real. Ningún campo de `tailscale status` la
expone.

Sin esta fase el skill reporta 🟢 «conectado» y minutos después la primera
operación cross-VPS (propagación, barrido, hop a otro clon) se frena pidiendo el
link — que es exactamente lo que el operador quería saber al principio.
**Preferimos entregar el link ahora y reconectar, antes que un verde que no
habilita lo que el operador va a hacer.** Caso real 2026-08-18: `$vpn-connect`
dio 🟢 al inicio de la sesión y `propagate-toolkit-commit.sh` salió 75 una hora
después.

1. Elegir **UN peer online que NO sea este host** de `tailscale status`
   (columna de estado sin `offline`). Contra el host local `tailscale ssh` falla
   con `Host key verification failed` (exit 255) — es una llamada sin sentido,
   no un problema de auth (`config/tailscale/README.md` §Host local vs remoto).
   Sin peers online ⇒ saltar la fase, reportar `⏭️ sin peers online`.
2. Sondear con un comando **no-mutante** y capturar la salida (nunca a
   `/dev/null`: ahí vive el link). Timeout **≥60s** — el prompt de *check mode*
   tarda ~40s en aparecer, un `timeout 15` lo corta antes y lo disfraza de host
   caído:
   ```bash
   PEER="<peer online ≠ self>"
   OUT="$(timeout 60 tailscale ssh "ryzepeck@$PEER" true 2>&1)"; RC=$?
   ```
3. Clasificar por el CONTENIDO, no sólo por el `rc` (mismo patrón que
   `propagate-toolkit-commit.sh`, que ya lo hace bien):
   | Señal | Veredicto |
   |---|---|
   | `RC=0` | ✅ auth SSH caliente — el fleet es alcanzable AHORA |
   | `OUT` matchea `to authenticate, visit\|requires an additional check` | ⏸️ **auth pendiente** — extraer el link y mostrarlo (paso 4) |
   | timeout / otro error | ⚠️ reportar `OUT` crudo; NO afirmar que el fleet está alcanzable |
4. Si hay link, **mostralo en la respuesta** igual que en Phase 2:
   ```bash
   echo "$OUT" | grep -oE 'https://login\.tailscale\.com/[A-Za-z0-9/._-]+' | head -1
   ```
   > Abrí este link y autorizá con la cuenta del fleet: **`<URL>`**
   > Una sola autorización habilita TODOS los VPS de la ventana.

   Cada intento emite un link NUEVO e invalida el anterior: mostrá siempre el
   último y **no reintentes a ciegas** — esperá la confirmación del operador.

**Esta fase decide el veredicto final** (ver Códigos de salida): nodo conectado
con *check mode* pendiente es ⏸️, **no** 🟢.

`--no-ssh-probe` la saltea (offline, tailnet de un solo nodo, o cuando el
operador sólo quiere el estado local); entonces la fila del reporte va
`⏭️ no sondeado` y el veredicto NO puede ser 🟢 — a lo sumo ⏭️.

## Comandos de referencia

```bash
# Preflight / gate "estoy conectado?"
tailscale status >/dev/null 2>&1 && echo connected || echo not-connected
tailscale ip -4 | head -1

# Conectar (elige según host)
sudo tailscale up --ssh                          # dev workstation
sudo tailscale up --ssh --hostname=$(hostname -s)  # VPS

# Verificación post-auth
tailscale status
tailscale status --json | jq -r '.Self.DNSName // "" | split(".")[0]'
tailscale status --self --json | grep -q '"https://tailscale.com/cap/ssh"' && echo ssh-ok
```

## Guardrails

- **Local-only para MUTAR**: instala, enablea y autentica exclusivamente el
  `tailscaled` de ESTE host. Nunca corre comandos de trabajo en otro VPS, ni
  deploya, ni toca sus repos. **Única excepción, read-only: el probe de Phase 4**
  — un `tailscale ssh <peer> true` que no muta nada y existe justamente para
  detectar el *check mode*. Cualquier otro `tailscale ssh` sigue prohibido acá.
- **Idempotente**: ya-conectado ⇒ sólo reporta, no re-autentica el nodo. El probe
  de Phase 4 corre igual (es lo único que puede ver el *check mode*, y es barato
  cuando la auth está caliente: ~1-3s).
- **Nunca declares el fleet alcanzable sin haberlo probado.** «Nodo conectado»
  no implica «SSH autorizado»: son autorizaciones distintas. Si Phase 4 no corrió
  o no dio verde, el reporte lo dice y el veredicto no es 🟢.
- **No toca** el registry (`expected-nodes.yml`) ni el admin console — eso es de
  $bootstrap-vpn-fleet. Sólo instala/enablea/autentica el `tailscaled`
  local.
- Identificá el host ANTES de decidir `--hostname` (regla CLAUDE.md "identificar
  el host antes de llamar a Tailscale").

## Códigos de salida

- `0` — nodo conectado **y** probe SSH verde (Phase 4): el fleet es alcanzable
  ahora. Es el ÚNICO caso 🟢.
- `1` — pausa manual pendiente (URL mostrada, esperando autorización del
  operador). Cubre los dos casos: el `tailscale up` de Phase 2 y el *check mode*
  de Phase 4 con el nodo ya conectado.
- `2` — error (install falló, daemon no arranca, verificación no pasa tras auth).
- `⏭️`/`0` con salvedad — probe saltado (`--no-ssh-probe` o sin peers online): se
  reporta el estado local y se dice explícitamente que el alcance al fleet **no
  se verificó**.

## Acciones disponibles

Tras el reporte, si la sesión es interactiva y NO hubo flags explícitos
(reglas de gating de $output-protocol §4), ofrecer vía AskUserQuestion:

| Opción (label) | description (costo/efecto) | preview (comando exacto) |
|---|---|---|
| Re-verificar conexión | re-corre el diagnóstico read-only (status + IP 100.x + ssh cap) | `$vpn-connect --check` |
| Registrar este nodo en el registry (dry-run primero) | preview del alta en expected-nodes.yml; el `--add-self` real commitea + pushea | `$bootstrap-vpn-fleet --add-self --dry-run` |

## Output final

Reportar siguiendo $output-protocol. Plantilla específica de esta skill:

🟢 vpn-connect OK — <host> conectado Y fleet alcanzable (IP 100.x, nodo <nombre>, probe SSH ✅)
⏸️ vpn-connect — pausa manual pendiente — URL de login mostrada, esperando OAuth del operador
   (dos causas: el `tailscale up` de Phase 2, o el *check mode* de Phase 4 con el nodo YA conectado)
🔴 vpn-connect — N error(es), revisar arriba — install/daemon falló o verificación no pasó
⏭️ vpn-connect — alcance al fleet NO verificado — `--no-ssh-probe` o sin peers online

| Dimensión | Estado | Detalle |
|---|---|---|
| Host / alias | ℹ️ | `hostname -s` + alias resuelto |
| tailscale instalado + daemon | ✅/❌ | versión + `tailscaled` activo |
| Nodo en el tailnet | ✅/⏸️ | conectado / esperando OAuth (URL mostrada) |
| Verificación local (status + IP + ssh cap) | ✅/⚠️/❌ | IP `100.x` + nodo + ssh cap |
| **Sesión SSH al fleet (*check mode*)** | ✅/⏸️/⚠️/⏭️ | probe contra `<peer>`: alcanzable ahora / auth pendiente (URL) / error / no sondeado |
| Registro en expected-nodes.yml | ℹ️ | presente / sugerir `--add-self` |

Las dos filas del medio son **independientes**: la 4ª puede ir ✅ y la 5ª ⏸️ —
ése es justamente el caso que motivó la fase, y el reporte NO debe presentarlo
como «conectado, todo listo».

## Next steps (si aplica)
- (manual, operador) abrir la URL de login y autorizar con la cuenta del fleet.
- (tras autorizar) re-correr `$vpn-connect --check` para confirmar que el
  probe pasa a ✅ antes de lanzar una operación cross-VPS larga.
- `$bootstrap-vpn-fleet --add-self` — registrar el nodo en el repo.
- (admin console) *Disable key expiry* si es un VPS.

## Referencias

- Skill de onboarding/audit/registry: $bootstrap-vpn-fleet
- Entry-point de host nuevo: $init-fleet
- Diagnóstico standalone: [`scripts/diagnostics/tailscale-fleet-check.sh`](../../scripts/diagnostics/tailscale-fleet-check.sh)
- Patrón de captura de URL: [`scripts/maintenance/propagate-toolkit-commit.sh`](../../scripts/maintenance/propagate-toolkit-commit.sh)
- CLAUDE.md sección "Acceso al fleet desde dev"
- Tailscale SSH docs: https://tailscale.com/kb/1193/tailscale-ssh/
