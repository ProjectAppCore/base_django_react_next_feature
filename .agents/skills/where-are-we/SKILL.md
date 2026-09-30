---
name: "where-are-we"
description: "Usar cuando el operador vuelve a una sesión con trabajo en marcha y pregunta '¿en qué vamos?', '¿cómo vamos?', '¿qué falta?', 'ya volví', 'dame el estado' o 'status': estado de la sesión (hecho / en curso / pendiente) con % de avance global y del paso actual, en formato $human. Read-only y no frena el trabajo. NO usar para el estado git de los repos ($git-status-report), el tablero de un drenaje ($merge-queue) ni para saber si el trabajo quedó entregado ($all-in-base)."
---

## Objetivo

El operador dejó la sesión trabajando y volvió. En 10 segundos de lectura sabe qué se hizo, qué está pasando, qué falta, cuánto va —global y del paso actual— y si algo espera por él. Es un reporte, no una pausa: el trabajo sigue.

## Cómo invocar este skill

Gating ($output-protocol §4): se ejecuta directo, PROHIBIDO preguntar — el insumo es la sesión misma. `$ARGUMENTS` opcional = un foco (un frente de trabajo: `CI`, `kore`, `deploy`): el reporte se limita a ese frente y el % global sigue siendo el de la sesión. Sin trabajo en la sesión → `Sin trabajo en curso en esta sesión.` (+ lo último hecho, si hubo). Nunca en modo fleet/headless/cron.

Sin picker por diseño: read-only y sin flags de modo — el único argumento es el foco.

## Fuentes, en orden

1. **La conversación.** El pedido del operador define el objetivo (el 100 %); el plan acordado, las decisiones y los resultados de herramientas definen lo hecho. Tras una compactación, el resumen cuenta como fuente.
2. **El plan explícito, si existe:** la lista de tareas de la sesión, el archivo de plan, las fases de la skill en ejecución (p.ej. las de $qa), las unidades del tablero de $merge-queue, los repos de $all-projects. Esa lista es la base del %.
3. **El estado vivo de lo que esta sesión lanzó**, verificado read-only antes de reportarlo: tareas en background, subagentes, workflows, monitores, CI de los PRs en juego (`gh pr checks <n>`). Lo que figura "corriendo" pudo terminar —o fallar— mientras el operador no estaba. Sin forma de confirmarlo → ⚠️ `sin verificar`.

Todo ✅ tiene evidencia en la sesión (resultado de herramienta, CI, test): lo que sólo se planeó no es "hecho".

## Cálculo del avance

| Línea | Mide | Base |
|---|---|---|
| `Global` | el objetivo de la sesión | unidades del plan vigente: pasos, fases, repos, archivos |
| `Actual` | el paso en ejecución | contador observable (tests X/N, jobs X/N, repos X/N); si no hay, sus sub-pasos |

1. Cada % es el número exacto con su base: `57 % (4/7 pasos)`.
2. Unidades de peso muy desigual → estimado con `~` y la razón: `~40 % (2/4 pasos; falta el build, el más largo)`.
3. Por tiempo, sólo en `Actual` y con una duración de referencia real: `~50 % (6 de ~12 min, corrida anterior)`. El `Global` sale del trabajo que falta, nunca del tiempo.
4. La base es un plan que ya existía en la sesión, con un total que no depende de lo que salga de cada paso; armarlo al reportar es inventarlo. Un debug o una investigación abierta no lo tiene (refutar una hipótesis abre otras) → estimado con `~` y `sin plan fijo` en lugar de la base: `- Global ▰▰▰▰▱▱▱▱▱▱ ~40 % (sin plan fijo: causa acotada al worker de Celery; falta reproducirla)`.
5. Un paso cuenta sólo con evidencia; uno fallido no suma. `100 %` global sólo con el objetivo verificado, según la definición de terminado de la regla fleet.
6. Si el alcance cambió, se recalcula contra el plan vigente y la base lo dice: `(3/7 pasos; eran 5)` — el % puede bajar.
7. Sin paso en ejecución → no hay línea `Actual`. Varios frentes en paralelo → una `Actual` por frente (máx. 3), con su nombre.

Barra de 10 bloques, la de la regla fleet: un `▰` por cada 10 % completo (se trunca: 95 % muestra nueve) y `▱` el resto — `▰▰▰▰▰▰▱▱▱▱ 60 %`.

Este reporte SUSTITUYE al bloque de avance de la regla fleet «Avance teórico en cada respuesta» (`CLAUDE.md` / `AGENTS.md`), porque ya lo contiene entero con más detalle: la línea `Global` es su barra —lleva `(antes N %)` cuando cambió desde la respuesta anterior, `57 % (4/7 pasos; antes 45 %)`—, **✅ Hecho** cubre su `Último` y **📋 Pendiente** su `Falta`, con el mismo 🦾, sólo para lo que el operador tiene que tipear. Una respuesta con este reporte no agrega además `📊 Avance …`.

## Formato de salida

Contrato de formato: $human — sus reglas duras aplican completas. Plantilla, en este orden:

```
<estado> <frase>: <paso actual>. <"Nada pendiente de tu parte." | "Te espera: <qué>.">

- Global ▰▰▰▰▰▰▱▱▱▱ 60 % (3/5 fases)
- Actual ▰▰▰▰▰▰▰▰▱▱ 80 % (build 4/5 pasos)

**✅ Hecho**
- <resultado + evidencia: SHA, PR #, test, archivo>

**🔄 En curso**
- <qué> — <⏳ corriendo | ✅ terminó mientras no estabas | ❌ falló: causa>

**📋 Pendiente**
1. <siguiente paso>
2. 🦾 <comando o skill [M] que el operador tiene que tipear>
3. <decisión del operador, sin icono: ¿A) … (recomendada) o B) …?>

⚠️ <riesgo o bloqueo real, en una oración>
```

- `<estado>`: 🔄 en curso · ⏸️ esperando por el operador · ✅ terminado · ❌ bloqueado o falló algo.
- Cada ítem es una línea: el resultado y su evidencia. Hecho agrupado por resultado, no por comando; lo más reciente primero.
- Pendiente en orden de ejecución; 🦾 = un comando o una skill [M] que el operador tiene que tipear, y nada más. Una decisión, un password o una aprobación van sin icono.
- Una decisión es un solo ítem, sin icono: la pregunta con sus opciones en una línea, la recomendada primero — `¿A) migrar hoy con 5 min de corte (recomendada) o B) esperar la ventana del domingo?`.
- Tope ~15 líneas ($human regla 4): el resto como `+N más`. Lo que depende del operador (con 🦾 o sin él) nunca se recorta.
- Sección vacía no aparece; la línea `⚠️` también es opcional.

## Después del reporte

- Trabajo en ejecución que no depende del operador → se retoma en la misma respuesta, sin preguntar si seguir.
- Lo que sigue espera una tarea en background de la sesión (shell, subagente, workflow) → el reporte cierra el turno sin polling; el aviso de fin retoma el trabajo. Una espera externa (CI) sigue el mecanismo de la skill que la estaba corriendo.
- Algo depende del operador → su ítem es la pregunta (o el comando 🦾); espera sólo lo que depende de la respuesta, el resto sigue.
- La skill no muta nada: no reintenta lo fallido, no commitea, no reinicia. Lo fallido se corrige en el flujo normal de la tarea.

## Output final

Excepción output-es-el-producto de $output-protocol §2: sin tabla de dimensiones ni Next steps — el reporte ES el entregable. Cerrar SÓLO con la línea de veredicto:

- `🟢 where-are-we OK` — todo lo reportado quedó verificado.
- `🟡 where-are-we OK con N warning(s)` — N ítems `sin verificar` (marcados ⚠️ arriba).
- `⏭️ where-are-we — N/A o saltado` — la sesión no tiene trabajo.

Sin menú por diseño (§4): output-es-el-producto (§2) — el reporte ES el entregable.
