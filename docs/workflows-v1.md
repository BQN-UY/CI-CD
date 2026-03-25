# Workflows v1 — Referencia

> Reusable workflows utilizados hasta marzo 2026. Siguen activos en
> `.github/workflows/` y son consumidos por los repositorios que aún no migraron a v2.
> **No modificar** sin evaluar el impacto en los repos consumidores.

---

## Contexto

Los workflows v1 son de tipo `workflow_call` — viven en `.github/workflows/` de este
repo y son invocados desde los repositorios de proyecto con:

```yaml
uses: BQN-UY/CI-CD/.github/workflows/<nombre>.yml@main
```

Características del modelo v1:

- Versionado mediante `version.sbt` + plugin `sbt-release`
- Build mediante `BQN-UY/action_checkout_jdk_sbt-cache@main` (action en repo separado)
- Deploy vía rsync + SSH a Jenkins
- Release notes mediante `release-drafter`
- Hotfix branches con formato `refs/heads/v#.#.#`
- Timezone: `America/Montevideo`

---

## Workflows disponibles

### `scala-ci.yml`

CI para proyectos Scala. Corre en cada PR y push.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `jdk-version` | Versión de JDK | `8` |
| `run_utest` | Ejecutar o saltear unit tests | `true` |

**Secrets requeridos:** `SYSADMIN_PAT` · `NEXUS_USER` · `NEXUS_PASSWORD`

**Jobs:**

| Job | Descripción |
|---|---|
| `labeler` | Aplica labels al PR según `.github/labeler.yml` vía `TimonVS/pr-labeler-action` |
| `u-tests` | Ejecuta `sbt unitTests` y publica resultados. Se omite si el mensaje de commit contiene `ci:` o `(ci)` |
| `merge-update` | Auto-mergea PRs de rama `update` del actor `bqn-sysadmin` con squash (necesita que pasen `labeler` y `u-tests`) |

**Referencia:**
```yaml
uses: BQN-UY/CI-CD/.github/workflows/scala-ci.yml@main
secrets:
  SYSADMIN_PAT: ${{ secrets.SYSADMIN_PAT }}
  NEXUS_USER: ${{ secrets.NEXUS_USER }}
  NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
```

---

### `scala-deploy-jar.yml`

Build y deploy de aplicaciones Scala empaquetadas como JAR (fat jar via `sbt assembly`).

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `jdk-version` | Versión de JDK | `17` |
| `build_path` | Directorio del artefacto compilado | `target` |
| `name` | Nombre del sistema (requerido) | — |
| `actor` | Usuario que disparó el workflow | `no_user_passed` |

**Secrets requeridos:** `SYSADMIN_PAT` · `NEXUS_USER` · `NEXUS_PASSWORD` · `DEPLOY_KEY` · `DEPLOY_IP` · `DEPLOY_PORT` · `DEPLOY_USER` · `JENKINS_URL` · `JENKINS_DEPLOY_JOB` · `JENKINS_USER` · `JENKINS_TOKEN` · `PUBLISHER_PATH`

**Flujo del job `deploy`:**

1. Checkout + setup JDK + cache sbt
2. `sbt assembly` → genera el fat JAR
3. Lee versión desde `version.sbt`
4. Transfiere el JAR al servidor vía rsync (`Pendect/action-rsyncer`)
5. Conecta por SSH y dispara el job de Jenkins con parámetros `SISTEMA`, `VERSION`, `USER`

---

### `scala-deploy-web.yml`

Build y deploy de aplicaciones Scala empaquetadas como WAR (via `sbt package`).
Idéntico a `scala-deploy-jar.yml` en flujo, difiere en el comando de build y extensión del artefacto.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `jdk-version` | Versión de JDK | `8` |
| `build_path` | Directorio del artefacto compilado | `target` |
| `name` | Nombre del sistema (requerido) | — |
| `actor` | Usuario que disparó el workflow | `no_user_passed` |

**Secrets requeridos:** mismos 12 que `scala-deploy-jar.yml`

**Flujo del job `deploy`:**

1. Checkout + setup JDK + cache sbt
2. `sbt package` → genera el WAR
3. Lee versión desde `version.sbt`
4. Transfiere el WAR vía rsync
5. Conecta por SSH y dispara Jenkins con parámetros `SISTEMA`, `VERSION`, `USER`

---

### `scala-make-release-jar.yml`

Release completo para aplicaciones JAR. Soporta release normal (desde `main`) y hotfix (desde rama `refs/heads/v*`).

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `jdk-version` | Versión de JDK | `8` |
| `build_path` | Directorio del artefacto | `target` |
| `name` | Nombre del sistema (requerido) | — |
| `artifact_extension` | Extensión del artefacto | `.jar` |

**Secrets requeridos:** mismos 12 que `scala-deploy-jar.yml`

**Jobs:**

| Job | Condición | Descripción |
|---|---|---|
| `default-release` | `github.ref == refs/heads/main` | `sbt "release with-defaults"` → push tags → upload artifact → release notes vía release-drafter |
| `hotfix-release` | `startsWith(github.ref, refs/heads/v)` | `sbt release-hotfix` → push tags → upload artifact → release notes → PR a main con alerta de conflicto de versión |
| `deploy` | Cuando cualquiera de los anteriores tiene éxito | Descarga artifact → rsync → Jenkins SSH |

---

### `scala-make-release-web.yml`

Release completo para aplicaciones WAR. Mismo flujo que `scala-make-release-jar.yml`,
difiere en que usa `sbt package` en hotfix y maneja artefactos `.war`.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `jdk-version` | Versión de JDK | `8` |
| `build_path` | Directorio del artefacto | `target` |
| `name` | Nombre del sistema (requerido) | — |
| `artifact_extension` | Extensión del artefacto | `.war` |

**Secrets requeridos:** mismos 12 que `scala-deploy-jar.yml`

**Jobs:** `default-release` · `hotfix-release` · `deploy` (mismo patrón que la versión JAR)

---

### `scala-make-release-lib.yml`

Release para librerías Scala publicadas en Nexus. Incluye detección de cambios para
evitar releases innecesarios.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `jdk-version` | Versión de JDK | `8` |
| `force-release` | Forzar release ignorando detección de cambios | — |

**Secrets requeridos:** `SYSADMIN_PAT` · `NEXUS_USER` · `NEXUS_PASSWORD`

**Jobs:**

| Job | Condición | Descripción |
|---|---|---|
| `check-changes` | Siempre | Detecta si hay cambios en archivos `.scala` o `.sbt` desde el commit anterior |
| `make-release` | Cambios detectados o `force-release`, en `main` | `sbt "release with-defaults"` → release notes |
| `make-release-hotfix` | Cambios detectados o `force-release`, en rama `v*` | `sbt release-hotfix` → push → GitHub Release → PR a main |

---

### `scala-publish-snapshot-lib.yml`

Publica un snapshot de librería Scala en Nexus. Usado en cada push a la rama principal.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `jdk-version` | Versión de JDK | `8` |

**Secrets requeridos:** `SYSADMIN_PAT` · `NEXUS_USER` · `NEXUS_PASSWORD`

**Flujo:** Checkout + setup JDK + cache sbt → `sbt publish`

**Referencia:**
```yaml
uses: BQN-UY/CI-CD/.github/workflows/scala-publish-snapshot-lib.yml@main
secrets:
  SYSADMIN_PAT: ${{ secrets.SYSADMIN_PAT }}
  NEXUS_USER: ${{ secrets.NEXUS_USER }}
  NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
```

---

### `start-hotfix.yml`

Crea la rama de hotfix a partir de un tag existente, incrementa el patch version en
`version.sbt` y opcionalmente crea una rama de trabajo adicional.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `git-tag-ref` | Tag de referencia: `latest`, `previous` o `v#.#.#` | `latest` |
| `git-hotfix-ref` | Nombre de la rama de trabajo del hotfix (opcional) | — |

**Secrets requeridos:** `SYSADMIN_PAT`

**Flujo:**

1. Checkout completo (`fetch-depth: 0`)
2. Resuelve el tag (`latest` → último tag, `previous` → penúltimo, o usa el valor literal)
3. Incrementa el patch: `v1.2.3` → rama `v1.2.4`
4. Actualiza `version.sbt` con el nuevo número + `-SNAPSHOT`
5. Commit y push de la rama de versión
6. Si se pasó `git-hotfix-ref`, crea y pushea esa rama adicional desde la versión

---

### `merge-update.yml`

Automatiza el labeling y auto-merge de PRs de ramas `update/*` generadas por Dependabot
o `bqn-sysadmin`.

**Secrets requeridos:** `SYSADMIN_PAT`

**Jobs:**

| Job | Descripción |
|---|---|
| `labeler` | Aplica labels según `.github/labeler.yml` |
| `merge-update` | Mergea con squash si la rama empieza con `update` y el actor es `bqn-sysadmin`. Solo permite `minor` updates |

---

### `release-drafter.yml`

Genera un borrador de release notes leyendo la versión actual desde `version.sbt` en `main`.

**Secrets requeridos:** `SYSADMIN_PAT`

**Flujo:**

1. Descarga solo `version.sbt` desde `main` (`Bhacaz/checkout-files`)
2. Extrae la versión eliminando el sufijo `-SNAPSHOT`
3. Ejecuta `release-drafter/release-drafter@v6` para generar el draft

---

### `remove-old-artifacts.yml`

Limpia artifacts antiguos de GitHub Actions para liberar espacio de almacenamiento.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `age` | Antigüedad mínima para eliminar | `1 week` |
| `skip-recent` | Cantidad de artifacts recientes a preservar | `1` |

**No requiere secrets.**

**Referencia:**
```yaml
uses: BQN-UY/CI-CD/.github/workflows/remove-old-artifacts.yml@main
with:
  age: '2 weeks'
  skip-recent: 2
```

---

## Secrets globales requeridos por v1

| Secret | Descripción | Workflows que lo usan |
|---|---|---|
| `SYSADMIN_PAT` | PAT de `bqn-sysadmin` para push, PR y acciones privilegiadas | Todos |
| `NEXUS_USER` | Usuario de Nexus | CI, deploy, publish, release |
| `NEXUS_PASSWORD` | Contraseña de Nexus | CI, deploy, publish, release |
| `DEPLOY_KEY` | Clave SSH privada para el servidor de deploy | deploy-jar, deploy-web, make-release-jar, make-release-web |
| `DEPLOY_IP` | IP del servidor de deploy | ídem |
| `DEPLOY_PORT` | Puerto SSH del servidor de deploy | ídem |
| `DEPLOY_USER` | Usuario SSH del servidor de deploy | ídem |
| `JENKINS_URL` | URL base de Jenkins | ídem |
| `JENKINS_DEPLOY_JOB` | Path del job de deploy en Jenkins | ídem |
| `JENKINS_USER` | Usuario de Jenkins | ídem |
| `JENKINS_TOKEN` | API token de Jenkins | ídem |
| `PUBLISHER_PATH` | Path en el servidor donde se almacenan los artefactos | ídem |

---

## Dependencias externas

| Action / Tool | Versión | Propósito |
|---|---|---|
| `BQN-UY/action_checkout_jdk_sbt-cache` | `@main` | Checkout + setup JDK + cache sbt (repo interno) |
| `TimonVS/pr-labeler-action` | `v5` | Labeling automático de PRs |
| `desbo/merge-pr-action` | `v0` | Auto-merge de PRs de update |
| `EnricoMi/publish-unit-test-result-action` | `v2` | Publicación de resultados de tests |
| `Pendect/action-rsyncer` | `v2.0.0` | Transferencia de artefactos vía rsync |
| `appleboy/ssh-action` | `master` | Ejecución remota de scripts vía SSH |
| `ad-m/github-push-action` | `master` | Push de tags y ramas post-release |
| `release-drafter/release-drafter` | `v6` | Generación de release notes |
| `vsoch/pull-request-action` | `1.1.1` | Creación de PRs post-hotfix |
| `aaiezza/create-release` | `v1.0.0` | Creación de releases de hotfix en libs |
| `tj-actions/changed-files` | `v47` | Detección de archivos cambiados |
| `Bhacaz/checkout-files` | `v2` | Checkout selectivo de archivos |
| `c-hive/gha-remove-artifacts` | `v1` | Limpieza de artifacts antiguos |
