# Migración Scala a CI/CD v2

Guía paso a paso para migrar un repositorio Scala/Pekko desde el modelo v1
(`version.sbt` + sbt-release + Jenkins) al modelo v2 (`sbt-dynver` + Git tags + webhook deploy).

---

## Contexto

### Modelo v1 (actual)

- La versión vive en el archivo `version.sbt` del repositorio.
- `sbt-release` gestiona el ciclo: quita `-SNAPSHOT` → compila → tagea → sube versión → nuevo `-SNAPSHOT` → commit.
- El deploy se dispara via SSH a Jenkins.
- Los workflows del proyecto llaman a reusable workflows del CI-CD repo (`workflow_call`).

### Modelo v2

- La versión vive en el **tag de Git**. No existe `version.sbt`.
- `sbt-dynver` calcula la versión en build-time leyendo el historial Git.
- El deploy se dispara vía webhook HTTP.
- Los workflows del proyecto invocan composite actions del CI-CD repo.

| Situación | Versión calculada por sbt-dynver |
|---|---|
| Commit exactamente en tag `v1.5.0` | `1.5.0` |
| 3 commits después de `v1.5.0` | `1.5.0+3-abc1234` |
| Árbol de trabajo sucio (local) | `1.5.0+3-abc1234+dirty` |

---

## Pre-requisitos

- Acceso de escritura al repositorio del proyecto.
- Acceso para crear tags en el repositorio.
- Coordinación con DevOps para tener el endpoint de webhook de deploy disponible
  antes de activar `make-release.yml`.

---

## Paso 1 — Identificar la última versión liberada

Revisar `version.sbt` en el repositorio a migrar:

```bash
cat version.sbt
# Ejemplo: version in ThisBuild := "1.5.1-SNAPSHOT"
# → la última release fue 1.5.0
```

La regla es simple: si dice `X.Y.Z-SNAPSHOT`, la última release publicada fue `X.Y.(Z-1)`
o bien `X.(Y-1).último` según el ciclo de sbt-release que se haya usado.
Confirmarlo revisando el historial de releases en GitHub o Nexus.

---

## Paso 2 — Verificar si existe el tag Git correspondiente

```bash
git fetch --tags
git tag --list "v*" --sort=-version:refname | head -10
```

### Caso A — el tag ya existe

sbt-release crea tags con el formato `v{version}` (ej. `v1.5.0`) por defecto.
Si el tag existe, `sbt-dynver` lo detecta automáticamente. **No hay nada más que hacer en este paso.**

### Caso B — el tag no existe

Puede ocurrir si el repositorio nunca pasó por un release formal o si los tags
no fueron pusheados. En ese caso, crear el tag apuntando al commit que corresponde
a la última versión publicada en Nexus:

```bash
# Identificar el commit de la última release
git log --oneline | head -20

# Crear el tag anotado apuntando a ese commit
git tag -a v1.5.0 <commit-sha> -m "Release v1.5.0"

# Pushear el tag al remoto
git push origin v1.5.0
```

> **Importante:** el prefijo `v` que usa sbt-release coincide con el prefijo que
> usa la action `shared/semver-tag` — son compatibles y la secuencia de versiones
> continúa sin saltos.

---

## Paso 3 — Cambios en el proyecto Scala

### 3.1 `project/plugins.sbt`

Reemplazar `sbt-release` por `sbt-dynver`:

```scala
// QUITAR
addSbtPlugin("com.github.sbt" % "sbt-release" % "1.x.x")

// AGREGAR
addSbtPlugin("com.github.sbt" % "sbt-dynver" % "5.0.1")
```

### 3.2 `build.sbt`

Eliminar toda la configuración de sbt-release. Buscar y quitar bloques como:

```scala
// QUITAR — ejemplos de configuración de sbt-release a eliminar
releaseProcess := Seq(...)
releaseTagName := ...
releaseCommitMessage := ...
releaseNextVersion := ...
releaseCrossBuild := ...
releaseIgnoreUntrackedFiles := ...
```

`sbt-dynver` setea el campo `version` automáticamente — no declarar `version :=`
ni `version in ThisBuild :=` en ningún archivo.

### 3.3 Eliminar `version.sbt`

```bash
git rm version.sbt
```

### 3.4 Verificar localmente

```bash
sbt version
```

Resultado esperado si hay 3 commits desde `v1.5.0`:

```
[info] 1.5.0+3-abc1234
```

Resultado esperado si el HEAD apunta exactamente al tag:

```
[info] 1.5.0
```

---

## Paso 4 — Actualizar los workflows del proyecto

Reemplazar las referencias a los reusable workflows v1 por las composite actions v2.

### `ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches: [develop]
  push:
    branches: ["release/**", "hotfix/**"]

jobs:
  verify-label:
    name: Verificar label de PR
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - uses: BQN-UY/CI-CD/.github/actions/shared/label-check@v2
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}

  lint-build:
    name: Lint & Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # sbt-dynver necesita historial Git completo
      - uses: BQN-UY/CI-CD/.github/actions/backend/scala/lint-build@v2

  security:
    name: Security scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # BetterLeaks analiza historial completo
      - uses: BQN-UY/CI-CD/.github/actions/shared/security-scan@v2
```

### `publish-and-deploy.yml`

```yaml
name: Publish and deploy

on:
  push:
    branches: [develop, "hotfix/**", "release/**"]

jobs:
  publish:
    name: Publish JAR snapshot → Nexus + deploy testing/staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: BQN-UY/CI-CD/.github/actions/backend/scala/lint-build@v2

      - name: Publish snapshot to Nexus
        shell: bash
        run: sbt publish
        env:
          NEXUS_USER:     ${{ secrets.NEXUS_USER }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_URL:      ${{ secrets.NEXUS_URL }}

      - name: Deploy to testing
        if: github.ref == 'refs/heads/develop'
        uses: BQN-UY/CI-CD/.github/actions/shared/deploy-trigger@v2
        with:
          environment: testing
          service-url: ${{ secrets.DEPLOY_TESTING_URL }}
          token:       ${{ secrets.DEPLOY_TESTING_TOKEN }}

      - name: Deploy to staging
        if: startsWith(github.ref, 'refs/heads/hotfix/') || startsWith(github.ref, 'refs/heads/release/')
        uses: BQN-UY/CI-CD/.github/actions/shared/deploy-trigger@v2
        with:
          environment: staging
          service-url: ${{ secrets.DEPLOY_STAGING_URL }}
          token:       ${{ secrets.DEPLOY_STAGING_TOKEN }}
```

### Fixes durante el ciclo de release

> **Cambio de comportamiento respecto a v1:** en v1 no se usaban ramas `release/**`
> ni `develop`. Este es uno de los cambios más importantes a internalizar en v2.

Una vez creada la rama `release/vX.Y.Z` con `start-release.yml`, esa rama y
`develop` son **independientes**. Los commits que lleguen a `develop` después
del `start-release` son para la **próxima versión** — no afectan el release en
curso ni re-publican en staging.

**Si se detecta un problema durante el testeo en staging, el fix se commitea
directamente sobre `release/vX.Y.Z` — nunca sobre `develop`.**

El push a `release/vX.Y.Z` dispara `publish-and-deploy.yml` automáticamente:
publica el snapshot en Nexus y redespliega staging. Una vez validado,
`make-release.yml` cierra el ciclo: crea el tag, publica en Nexus releases,
mergea a main y hace back-merge a develop (así los fixes vuelven a develop al final).

---

### `start-release.yml`

```yaml
name: Start release

on:
  workflow_dispatch:
    inputs:
      bump:
        description: Tipo de bump de versión
        required: true
        default: minor
        type: choice
        options: [major, minor, patch]

jobs:
  start-release:
    name: Crear release branch
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: develop

      - name: Calcular versión
        id: semver
        uses: BQN-UY/CI-CD/.github/actions/shared/semver-tag@v2
        with:
          bump: ${{ inputs.bump }}
          dry-run: "true"         # Solo calcula, no crea el tag

      - name: Crear release branch
        shell: bash
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git checkout -b "release/${{ steps.semver.outputs.tag }}"
          git push origin "release/${{ steps.semver.outputs.tag }}"
```

### `make-release.yml`

```yaml
name: Make release

on:
  workflow_dispatch:
    inputs:
      bump:
        description: Tipo de bump
        required: true
        default: minor
        type: choice
        options: [major, minor, patch]
      environment:
        description: Entorno de deploy
        required: true
        default: production
        type: choice
        options: [production]

jobs:
  release:
    name: Tag + Nexus + GitHub Release + deploy + back-merge
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    permissions:
      contents: write          # requerido para crear tags y hacer push de ramas
      security-events: write   # requerido para subir SARIF al tab de Security
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: BQN-UY/CI-CD/.github/actions/backend/scala/lint-build@v2

      - uses: BQN-UY/CI-CD/.github/actions/shared/security-scan@v2

      - name: Crear tag SemVer
        id: tag
        uses: BQN-UY/CI-CD/.github/actions/shared/semver-tag@v2
        with:
          bump: ${{ inputs.bump }}

      - name: Publish release JAR → Nexus
        shell: bash
        run: sbt publish
        env:
          NEXUS_USER:     ${{ secrets.NEXUS_USER }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_URL:      ${{ secrets.NEXUS_URL }}

      - name: GitHub Release
        uses: BQN-UY/CI-CD/.github/actions/shared/github-release@v2
        with:
          tag: ${{ steps.tag.outputs.tag }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Merge release → main
        uses: BQN-UY/CI-CD/.github/actions/shared/git-merge@v2
        with:
          source: ${{ github.ref_name }}
          target: main

      - name: Back-merge main → develop
        uses: BQN-UY/CI-CD/.github/actions/shared/git-merge@v2
        with:
          source: main
          target: develop

      - name: Deploy to production
        uses: BQN-UY/CI-CD/.github/actions/shared/deploy-trigger@v2
        with:
          environment: production
          service-url: ${{ secrets.DEPLOY_PRODUCTION_URL }}
          token:       ${{ secrets.DEPLOY_PRODUCTION_TOKEN }}
```

### `start-hotfix.yml`

```yaml
name: Start hotfix

on:
  workflow_dispatch:
    inputs:
      description:
        description: Descripción corta del bug (ej. fix-null-parser)
        required: true

jobs:
  start-hotfix:
    name: Crear hotfix branch desde main
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: main

      - name: Calcular versión patch
        id: semver
        uses: BQN-UY/CI-CD/.github/actions/shared/semver-tag@v2
        with:
          bump: patch
          dry-run: "true"

      - name: Crear hotfix branch
        shell: bash
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          BRANCH="hotfix/${{ steps.semver.outputs.tag }}-${{ inputs.description }}"
          git checkout -b "$BRANCH"
          git push origin "$BRANCH"
```

---

## Paso 5 — Secrets requeridos en el repositorio

Confirmar con DevOps que los siguientes secrets están configurados en el repo:

| Secret | Descripción |
|---|---|
| `NEXUS_USER` | Usuario de Nexus |
| `NEXUS_PASSWORD` | Contraseña de Nexus |
| `NEXUS_URL` | URL base del repositorio Nexus |
| `DEPLOY_TESTING_URL` | Endpoint del webhook de deploy — ambiente testing |
| `DEPLOY_TESTING_TOKEN` | Token de autenticación — ambiente testing |
| `DEPLOY_STAGING_URL` | Endpoint del webhook de deploy — ambiente staging |
| `DEPLOY_STAGING_TOKEN` | Token de autenticación — ambiente staging |
| `DEPLOY_PRODUCTION_URL` | Endpoint del webhook de deploy — ambiente production |
| `DEPLOY_PRODUCTION_TOKEN` | Token de autenticación — ambiente production |

Los secrets `DEPLOY_KEY`, `DEPLOY_IP`, `DEPLOY_PORT`, `DEPLOY_USER`, `JENKINS_USER`,
`JENKINS_TOKEN` y `PUBLISHER_PATH` usados en v1 **dejan de ser necesarios** en v2.

---

## Impacto en artefactos publicados en Nexus

El nombre de los artefactos cambia solo para los **snapshots**. Los releases son idénticos.

| | v1 | v2 |
|---|---|---|
| Snapshot | `1.5.1-SNAPSHOT` | `1.5.0+3-abc1234` |
| Release  | `1.5.0`          | `1.5.0` ✓ igual  |

Si algún otro proyecto consume snapshots de este repo por nombre de versión exacto,
actualizar esa referencia para que use la convención de sbt-dynver antes de migrar.

---

## Checklist de migración

```
[ ] Identificada la última versión publicada (version.sbt)
[ ] Verificado o creado el tag v{version} en Git
[ ] sbt-dynver agregado en project/plugins.sbt
[ ] sbt-release eliminado de project/plugins.sbt
[ ] Configuración de sbt-release eliminada de build.sbt
[ ] version.sbt eliminado (git rm)
[ ] sbt version muestra la versión correcta localmente
[ ] ci.yml actualizado a v2
[ ] publish-and-deploy.yml actualizado a v2
[ ] start-release.yml creado
[ ] make-release.yml actualizado a v2
[ ] start-hotfix.yml actualizado a v2
[ ] Secrets de deploy configurados por DevOps (DEPLOY_TESTING_URL, DEPLOY_TESTING_TOKEN, DEPLOY_STAGING_URL, DEPLOY_STAGING_TOKEN, DEPLOY_PRODUCTION_URL, DEPLOY_PRODUCTION_TOKEN)
[ ] PR abierto con label feature hacia develop
[ ] CI pasa en la feature branch
```

---

## Rollback

Si es necesario revertir la migración antes de hacer release:

1. Restaurar `version.sbt` con el contenido original.
2. Restaurar `project/plugins.sbt` con sbt-release.
3. Restaurar la configuración en `build.sbt`.
4. Revertir los workflows a las referencias `@main` de v1.

El tag Git creado en el Paso 2 puede quedarse — no interfiere con sbt-release.
