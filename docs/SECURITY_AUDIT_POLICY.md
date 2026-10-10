# Política temporal de auditoría npm

El template conserva la auditoría de **todas** las dependencias y el bloqueo de
alertas high/critical. Acepta temporalmente una sola advisory en una cadena dev
revisada, mediante `frontend/scripts/npm-audit-gate.cjs`. Esto es aceptación
limitada de riesgo: **no es un parche ni una certificación de falso positivo**.

## Riesgo y evidencia revisada

[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
sigue publicada como High, afecta braces <=3.0.3 y no tiene versión corregida.
El [maintainer cuestiona el reporte](https://github.com/micromatch/braces/issues/70),
el [PR de depth guards fue retirado](https://github.com/micromatch/braces/pull/75)
y la [corrección de la advisory sigue pendiente](https://github.com/github/advisory-database/pull/10132).
Estas disputas no eliminan el aviso oficial.

En las versiones revisadas, `@next/eslint-plugin-next/dist/utils/get-root-dirs.js:15,20–29`
solo pasa patrones a `fast-glob` desde `settings.next.rootDir`. La configuración
local `frontend/eslint.config.mjs` y sus imports no lo definen; el plugin utiliza
`context.cwd` sin llamar a glob en ese caso. `fast-glob/out/utils/pattern.js:137`
expande el patrón del consumidor mediante `micromatch.braces`; no toma ese patrón
del contenido HTTP ni de los nombres de archivos encontrados.

No se acreditó entrada externa hacia este camino en el template revisado. Esto
no prueba que la librería sea invulnerable, ni que un proyecto derivado mantenga
el mismo contexto. Configuraciones que incorporen globs no confiables requieren
otra evaluación; la clasificación dev por sí sola no basta.

## Contrato y vencimiento

La política `frontend/npm-audit-policy.json`, propiedad del conductor, declara:

- `schemaVersion: 1` y una sola `exception` con advisory URL, repository, owner, reason,
  reviewedAt, expiresAt, packages y context.
- Revisión fechada el **10 de octubre de 2026 UTC** y vencimiento absoluto
  **2026-10-24T00:00:00Z**. No se renueva automáticamente ni se reinicia al copiar
  el template. Cambiar la fecha requiere una nueva decisión revisada y modificar
  deliberadamente el contrato del helper.
- Repository exacto `ProjectAppCore/base_django_react_next_feature`, que debe
  coincidir con `GITHUB_REPOSITORY` al utilizar la excepción. GitHub proporciona
  esta identidad: CI no debe fijarla ni sustituirla. Un fork o proyecto nuevo
  bloquea aunque copie la política antes del vencimiento y requiere revisión
  propia. Una verificación local del template declara explícitamente esta
  variable; no es una autorización para otro repositorio.
- Cadena exacta: eslint-config-next@16.3.8 → @next/eslint-plugin-next@16.3.8 →
  fast-glob@3.3.1 → micromatch@4.0.8 → braces@3.0.3. Cada entrada tiene version,
  node (`node_modules/<nombre>`) y via con el siguiente nombre; braces omite via.
  Todos los nodos deben ser únicos y `dev: true` en el lock.
- Hashes SHA-256 de `eslint.config.mjs` y `package.json`, relativos al frontend.
  El primero fija las reglas/imports revisados; el segundo fija el comando lint
  y las dependencias declaradas. Un cambio invalida la excepción: no actualizar
  fingerprints sin revisar de nuevo el origen de los patrones.

La excepción admite únicamente las cinco highs propagadas por esa URL y esas
aristas. Otra high, cualquier critical, advisory adicional, cambio de versión,
nodo, ámbito dev, contexto, esquema o informe inválido hace fallar el helper con
exit 1. También falla al llegar al vencimiento. Si el audit ya no contiene
highs/criticals, pasa sin usar la excepción, incluso después de vencer o sin
identidad de repositorio.

## Ejecución y trazabilidad

El CI ejecuta el audit completo con `--include=dev --include=optional --include=peer
--json`, conserva su JSON y solo acepta los códigos npm 0/1 para procesarlo.
Errores de red, JSON inválido y otros códigos no se convierten en éxito. Después:

```sh
node scripts/npm-audit-gate.cjs <report.json> <package-lock.json> <policy.json> <frontend-context-dir>
```

El helper no realiza peticiones, instala paquetes ni modifica archivos. Emite en
stderr una advertencia con advisory, repositorio, owner, motivo y vencimiento cuando aplica
la excepción. El CI conserva el informe completo y la política como artefactos,
sin anunciar que las vulnerabilidades quedaron corregidas.

El audit runtime `npm audit --omit=dev --include=optional --include=peer
--audit-level=high` continúa independiente y obligatorio. No sustituye al
completo: [npm omite esas dependencias del payload auditado](https://docs.npmjs.com/cli/v11/commands/npm-audit/).
Lint, typechecks, build y pruebas mantienen sus controles.

Las pruebas del gate usan Node built-in, archivos temporales reales y el CLI,
sin Jest ni dependencias nuevas. Solo simulan el reloj en el proceso hijo:

```sh
node --test scripts/__tests__/npm-audit-gate.test.cjs
```

El owner indicado en la política debe revisar la resolución upstream antes del
vencimiento. Cuando el audit completo pase sin excepción, retirar la excepción
y su manejo específico; una advisory corregida o una actualización oficial
compatible se verifica con un nuevo audit completo, no por un comentario o PR
abierto. Un derivado no debe renovar esta aceptación como parte de su generación.
