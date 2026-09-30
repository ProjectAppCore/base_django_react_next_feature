---
name: "security-pass"
description: "Pasada de seguridad de UN proyecto: autenticación, permisos por rol y objeto, inputs, secretos y dependencias. Diagnostica hasta 3 candidatos nuevos y registra su evidencia; --apply corrige sólo los elegibles en el worktree de sesión y prepara pruebas para $qa. Reutiliza $vuln-audit para dependencias. Aplica la regla común de beneficio sin diferir riesgos obligatorios. Funciona sola o delegada por $improvement-pass; no opera sobre el VPS ni rota credenciales automáticamente."
---

# Security pass

Mejorar la seguridad de un proyecto con evidencia del camino explotable y cambios
acotados. Leer el contrato común en
`$HOME/webapps/vps-ops-toolkit/workflows/improvement/IMPROVEMENT_STANDARDS.md`:
resuelve modos, worktree, registro, regla de beneficio y contexto delegado. Las
pruebas las escribe/ejecuta $qa, no esta pasada.

## Cómo invocar este skill

Sin menú por diseño (§4): el alcance y el modo se resuelven de la invocación y del contexto; la delegación conserva la selección del conductor.

Sin picker por diseño: sin flags diagnostica hasta tres candidatos nuevos y
registra metadatos; el proyecto sale del cwd/contexto. No modifica la aplicación.
`--apply` autoriza los cambios elegibles y el handoff; `--check` no escribe nada,
ni reportes ni ledger; `--refresh` sólo descubre/registra; `--review3` revisa hasta
tres candidatos anteriores. Los modos son excluyentes. Con contexto de
$improvement-pass, hereda selección, modo y worktree sin menú propio.

Qué NO se pregunta: permisos ya concedidos para el alcance, coordenadas
resolubles ni rotación de secretos como consecuencia automática de una alerta.
Una decisión real de negocio sobre quién puede acceder sí se plantea con la
evidencia; el resto de la pasada continúa donde sea independiente.

## 1. Preflight e inventario dirigido

Resolver la coordenada y leer políticas del proyecto antes de escribir. En
`--apply`, reutilizar el worktree propio; si falta, crearlo con
`session-worktree.sh create fix security-<slug>` y entrar (Claude:
`EnterWorktree`; Codex: `cd`, todos los comandos con ese workdir).

Identificar usuarios/roles, límites entre tenants, endpoints, permisos por
objeto, autenticación/sesiones, entradas externas y dependencias declaradas.
Seguir una petición desde su entrada hasta lectura/escritura/efecto; no
calificar como vulnerable un endpoint únicamente porque carece de login si su
contrato autoriza acceso público.

| Superficie | Evidencia útil para un candidato |
|---|---|
| Auth | Credenciales/sesión inválidas o revocadas aceptadas; flujo que omite un control requerido. |
| Permisos | Otro rol/tenant/propietario puede obtener datos o ejecutar un efecto no autorizado. |
| Inputs | Entrada no validada llega a SQL, shell, HTML, path, upload o destino externo peligroso. |
| Secrets | Un secreto llega a frontend, log, respuesta, artefacto público o destino no autorizado. |
| Dependencias | Advisory aplicable, versión afectada, alcance runtime/dev y ruta de actualización permitida. |

Las credenciales canónicas bajo `config/credentials/` del toolkit son un diseño
autorizado, no una filtración por existir. Reportar ubicación/canal/mecanismo,
nunca valores; no copiar `.env`, tokens, cookies ni bodies a un brief, chat o
artefacto. No probar exploits contra usuarios, datos ni servicios reales.

## 2. Dependencias y selección

Reutilizar $vuln-audit en modo auditoría para las superficies presentes; no
reimplementar sus scanners ni tratar todo paquete outdated como una vulnerabilidad.
Scanner ausente = evidencia incompleta, no seguridad confirmada. El scanner no se
instala ni cambia el venv del servicio para poder auditar.

Construir candidatos del frente `security`, deduplicados por causa, con el
formato común. Autorización eludida, exposición comprobada de secretos o datos y
vulnerabilidad aplicable que incumple un requisito obligatorio llevan
`mandatory: true`; incertidumbre se documenta y diagnostica, no se convierte en
una afirmación de explotación. Seleccionar hasta tres conforme al helper.

Antes de cualquier dependencia mutante, delegar a $vuln-audit sólo el
candidato seleccionado en el worktree actual y con el contexto común. Añadir
el descriptor textual `VULN_CANDIDATE` con `surface`,
`packages:[{name,current,target}]`, `advisories` y `allowed_paths`; la delegada
actualiza sólo ese set, no un batch global de outdated. Su `--apply` conserva
límites patch/minor, pins, Node/Python y venv aislado; una
actualización major o feature release de framework no se autoriza aquí. Un
riesgo que necesita major queda `blocked` con la acción explícita de
modernización, no `defer-low-value`. El contexto evita commits/PRs de una segunda
rama y no concede permiso para tocar otras dependencias.

Si `security-pass` se ejecuta independiente, crear ese contexto de delegación
con `conductor: security-pass`, `owns_git: conductor` y la selección propia;
`vuln-audit` deja el diff y esta pasada conserva la responsabilidad de su rama
y entrega. Si ya existe conductor `improvement-pass`, preservar el contexto
externo: no reemplazar su ownership ni abrir otra ronda.

## 3. Aplicación y guion para QA

Aplicar sólo el camino y los archivos del candidato aprobado: permisos en el
servidor, validación en el límite correcto y saneamiento en el origen. Evitar
cambios globales de auth, nuevos roles o defaults más restrictivos sin el
contrato de producto correspondiente. Si aparecen archivos/contratos fuera del
alcance, parar ese candidato y explicarlo; no restaurar archivos ajenos.

Preparar un bloque `brief-security`, que $qa transforma en los briefs de su
Architect. Cada ítem incluye:

- ID, comportamiento/requisito y `file:line` real.
- Actor/rol/tenant/objeto y entrada concreta; caso permitido y caso rechazado.
- Valor esperado de respuesta/estado y ausencia de efecto persistente en el
  caso rechazado, acompañada por una aserción positiva sobre el estado conservado.
- Capa y test existente a extender; bug que atraparía; entorno de tests aislado.

Ejemplo de expectativa: propietario cambia su objeto y recibe el valor nuevo;
otro tenant recibe 403/404 conforme al contrato y el objeto conserva el valor
original. No basta con comprobar que se invocó un permiso ni con un mock.

## 4. Registro y cierre

Guardar reporte saneado y estados mediante el helper común. `--check` entrega
todo en la respuesta. Cambio aplicado = `qa-pending`; no marcar `verified`
porque desapareció una advertencia estática o porque un scanner quedó verde.

Independiente: entregar el guion y siguiente paso $qa; no ejecutarlo dentro
de esta skill. Delegada: devolver al conductor IDs, diff, guion, riesgos y
pendientes; sin commit/push/PR propios. No ejecutar deploy, rotación, revocación,
secret scanning remoto ni cambios del host como efecto implícito.

## Output final

Usar $output-protocol: Auth · Permisos · Inputs · Secrets · Dependencias ·
Valor · QA. Cada frente suficiente lleva alcance y razón de parada conforme al
contrato común. Un candidato obligatorio bloqueado mantiene la advertencia y el
paso necesario; no declarar el frente suficiente. Cerrar con
`🟢/🟡/🔴 security-pass — <resultado>` según la evidencia, con el bloque de avance
antes de esa última línea.
