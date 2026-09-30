---
name: maintainability-pass
description: "Pasada de mantenibilidad de UN proyecto: complejidad, duplicación, dependencias entre módulos, arquitectura y deuda técnica con efecto demostrado. Diagnostica hasta 3 candidatos nuevos; --apply hace refactors acotados que conservan el comportamiento y prepara pruebas para /qa. Registra decisiones y detiene cambios cuyo beneficio no justifica coste/riesgo. Funciona sola o delegada por /improvement-pass; no hace reescrituras globales ni cambia el producto por estilo."
argument-hint: "[proyecto] [--apply|--check|--refresh|--review3] [--module=<alcance>]"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Agent, AskUserQuestion, EnterWorktree
---

# Maintainability pass

Reducir el coste comprobable de entender/cambiar un proyecto preservando sus
contratos. Leer
`$HOME/webapps/vps-ops-toolkit/workflows/improvement/IMPROVEMENT_STANDARDS.md`
para modos, registro, criterio de beneficio y contexto delegado.

## Cómo invocar este skill

Sin menú por diseño (§4): el alcance y el modo se resuelven de la invocación y del contexto; la delegación conserva la selección del conductor.

Sin picker por diseño: sin flags diagnostica y registra hasta tres candidatos
nuevos, sin modificar la aplicación. `--apply` aplica los elegibles; `--check`
no escribe nada; `--refresh` descubre/registra sin refactors; `--review3` revisa
hasta tres anteriores. Modos excluyentes; proyecto/cwd y alcance explícito no se
vuelven a preguntar. Delegada por [[improvement-pass]], hereda su contexto.

Qué NO se pregunta: nombres internos o elecciones locales reversibles. Una
reorganización de arquitectura o cambio de contrato fuera del alcance se
registra como propuesta, no se supone autorizado por “mejorar mantenibilidad”.

## 1. Preflight y causas

Resolver coordenada, políticas y módulos reales. Para aplicar, usar el worktree
de la sesión o crear `session-worktree.sh create refactor maintainability-<slug>`
antes del primer write; Claude entra con `EnterWorktree`, Codex con `cd` y workdir
correspondiente. Los cambios no requieren tocar el clon que sirve la app.

Buscar mecanismos, no un número objetivo de líneas o complejidad:

| Problema | Beneficio que debe poder demostrarse |
|---|---|
| Complejidad | Ramas/efectos difíciles de modificar causan bugs o dificultan un cambio concreto. |
| Duplicación | La misma regla de negocio diverge o exige modificar varios sitios al cambiar. |
| Arquitectura | Ciclos, límites de responsabilidad rotos o dependencia transversal con efecto real. |
| Deuda técnica | Workaround, código obsoleto o acoplamiento bloquea una operación/prueba/mantenimiento. |

Leer call sites, contratos, pruebas existentes e historial relevante. Dos
fragmentos parecidos con responsabilidades distintas no obligan a abstraerlos.
Un archivo largo, un nombre imperfecto o una métrica alta no justifican por sí
solos una intervención. [[repo-cleanup]] orienta la auditoría de archivos sin uso;
la eliminación de tests pertenece a [[test-audit]], nunca a esta pasada.

## 2. Propuesta y valor

Crear candidatos `maintainability` con causa y paths exactos. Nombrar el cambio
que será más seguro/sencillo tras el refactor y su evidencia. Aplicar la regla
común: las mejoras pequeñas y baratas requieren beneficio concreto y riesgo
bajo; las reorganizaciones grandes con retorno marginal se difieren con razón.

Elegir la menor transformación que elimine la causa: extracción de una regla
compartida, función pura para una decisión, límite entre coordinación/efecto o
reducción de ramas redundantes. Preservar APIs, validaciones, errores, orden de
efectos, transacciones y persistencia. Una modificación de resultados públicos
es trabajo funcional para [[implement]], salvo que ya forme parte del pedido.

No agregar un framework/capa/abstracción para una única variante hipotética. No
mezclar formateo global, renombres masivos ni modernizaciones de dependencias
con el refactor elegido. Un candidato que exige ese alcance queda `blocked` o
se formula como propuesta separada, sin ocultarlo bajo “limpieza”.

## 3. Aplicación y guion

Trabajar secuencialmente dentro de los paths aprobados, conservando cambios
ajenos. Si el descubrimiento contradice la propuesta, reducir alcance o
registrar `needs-evidence`; no seguir refactorizando para justificar el trabajo.

Entregar `brief-maintainability` a [[qa]] con la capa dueña, test existente a
extender y `file:line`. Cada caso debe invocar el comportamiento con entradas
concretas, asertar resultado/estado exacto y nombrar el bug que detectaría.
Cubrir los bordes que el refactor puede alterar: ramas válidas e inválidas,
orden de efectos, errores propagados y equivalencia del contrato.

No pedir tests de cantidad de funciones, orden de imports, estructura interna
o “la función nueva fue llamada”. Si la transformación es local y no tiene
comportamiento nuevo que probar, declarar abstención de autoría y utilizar las
pruebas conductuales existentes adecuadas. El guion documenta qué debe correr
QA para validar que no se alteró el comportamiento; no inventa cobertura.

## 4. Registro y cierre

Guardar reporte y estados con el helper común; los análisis o mediciones van
en el reporte, no como objetivo en el ledger. Un cambio aplicado espera QA.

Independiente: handoff a [[qa]], sin ejecutarlo en esta pasada. Delegada: devolver
IDs, diff, contratos preservados, guion, evidencias y pendientes al conductor;
sin rama, commit o PR adicionales. No tratar tests fallidos como deuda menor ni
modificar expectativas para acomodar un refactor incorrecto.

## Output final

Usar [[_output-protocol]]: Complejidad · Duplicación · Arquitectura · Deuda ·
Valor · QA. Explicar cada parada con alcance, beneficio restante y coste/riesgo,
sin afirmar que todo el proyecto está perfecto. Cerrar con
`🟢/🟡/🔴 maintainability-pass — <resultado>` según evidencia; bloque de avance
antes de esa última línea.
