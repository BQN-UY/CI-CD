# CI/CD v2 — Guía de referencia

> Basado en el documento `BQNUY_CICD_v2_Referencia.docx.pdf` · Marzo 2026
> Audiencia: Equipo de Desarrollo · Clasificación: Confidencial — uso interno

---

## 1. Qué es CI/CD v2 y por qué existe

El repositorio `BQN-UY/CI-CD` centraliza **toda la lógica de CI/CD de la organización**.
Los repositorios de proyecto no contienen lógica de build propia — solo definen cuándo
disparar cada workflow.

### Principios de diseño

| Principio | Descripción |
|---|---|
| **Sin duplicación** | La lógica de build, lint, test y deploy vive una sola vez en CI-CD. |
| **Cero fricción** | Una línea `uses:` reemplaza decenas de pasos en cada repo. |
| **Escalabilidad** | Agregar un nuevo stack es agregar una carpeta. El resto no se toca. |
| **Seguridad por defecto** | OpenGrep y BetterLeaks corren en cada PR sin configuración adicional. |
| **SemVer 2.0 estricto** | La versión vive en el tag de Git. No hay archivos de versión que colisionen en back-merge. |

---

## 2. Estructura del repositorio CI-CD

GitHub Actions requiere que cada action tenga su propio `action.yml` en la raíz de su
carpeta. La estructura usa dos niveles de agrupación: **capa** (`shared`, `frontend`,
`backend`) y **stack** (`python`, `scala`, `flutter`, etc.).

```
BQN-UY/CI-CD
└── .github/
    └── actions/
        ├── shared/                      # No sabe nada del lenguaje
        │   ├── security-scan/
        │   │   └── action.yml
        │   ├── semver-tag/
        │   │   └── action.yml
        │   ├── git-merge/
        │   │   └── action.yml
        │   ├── github-release/
        │   │   └── action.yml
        │   ├── deploy-trigger/
        │   │   └── action.yml
        │   └── label-check/
        │       └── action.yml
        │
        ├── frontend/
        │   ├── html-js/
        │   │   └── lint-build/          # ESLint + Prettier + build
        │   │       └── action.yml
        │   ├── vaadin/
        │   │   └── lint-build/          # Maven + Checkstyle + Java
        │   │       └── action.yml
        │   └── flutter/
        │       ├── lint-test/           # flutter analyze + test
        │       │   └── action.yml
        │       └── build-apk/           # apk / ipa / web
        │           └── action.yml
        │
        └── backend/
            ├── python/
            │   └── lint-test/           # Ruff + mypy + pytest
            │       └── action.yml
            ├── scala/
            │   └── lint-build/          # scalafmt + sbt compile + test
            │       └── action.yml
            └── node/
                └── lint-test/           # ESLint + Jest/Vitest
                    └── action.yml
```

### Regla para ubicar una action nueva

Responder en orden:

1. ¿Menciona algún lenguaje, runtime o toolchain? Si **no** → `shared/`. Fin.
2. ¿Produce algo que el usuario final consume directamente? Si **sí** → `frontend/`. Si **no** → `backend/`.
3. ¿Qué tecnología usa internamente? Esa es la subcarpeta: `python/`, `scala/`, `flutter/`, etc.

### Cómo se referencia desde un workflow de proyecto

El path del `uses:` siempre sigue el mismo patrón:

```yaml
# Shared — igual para cualquier repo
- uses: BQN-UY/CI-CD/.github/actions/shared/security-scan@v2
- uses: BQN-UY/CI-CD/.github/actions/shared/semver-tag@v2

# Frontend HTML+JS
- uses: BQN-UY/CI-CD/.github/actions/frontend/html-js/lint-build@v2

# Backend Python
- uses: BQN-UY/CI-CD/.github/actions/backend/python/lint-test@v2

# Backend Scala
- uses: BQN-UY/CI-CD/.github/actions/backend/scala/lint-build@v2
```

---

## 3. Actions compartidas (`shared/`)

Las actions de `shared/` no contienen lógica de stack. Se usan igual desde cualquier tipo
de repo y nunca deben modificarse al agregar un nuevo lenguaje.

### 3.1 `shared/label-check`

Verifica que el PR tenga exactamente uno de los labels obligatorios. Si no hay label,
el CI falla y el merge queda bloqueado.

**Labels aceptados:** `breaking-change` · `feature` · `fix` · `chore` · `deploy-action`

**Input requerido:**

| Input | Descripción |
|---|---|
| `github-token` | `GITHUB_TOKEN` del repo que invoca |

---

### 3.2 `shared/security-scan`

Corre **OpenGrep** (SAST) y **BetterLeaks** (secrets scanning) sobre el código.
Si encuentra algo, el CI falla y el PR no puede mergearse.

- OpenGrep genera un reporte SARIF y, si el workflow tiene `permissions: security-events: write`, lo sube al tab de *Security* del repo. Si el permiso no está configurado, el análisis corre igual pero el reporte no se publica.
- BetterLeaks falla con `--fail-on-findings` si detecta un secreto.

No requiere inputs — opera sobre el checkout actual. Para que el upload de SARIF funcione, el workflow que la invoca debe declarar `permissions: security-events: write`.

---

### 3.3 `shared/semver-tag`

Calcula el próximo tag SemVer 2.0 leyendo el historial de Git y crea un tag anotado (no firmado con GPG).
El tipo de bump (`major` / `minor` / `patch`) lo elige el desarrollador al disparar
`make-release`. Si se requieren tags firmados con GPG, el manejo de claves y la firma
deben implementarse en el workflow que invoca esta action.

> **Permisos requeridos:** esta action hace push de tags al repositorio remoto. El workflow
> que la use debe declarar `permissions: contents: write` (o utilizar un PAT con permisos
> equivalentes); de lo contrario el push fallará si el `GITHUB_TOKEN` es read-only por defecto.

**Inputs:**

| Input | Descripción | Default |
|---|---|---|
| `bump` | `major` \| `minor` \| `patch` | `minor` |
| `prefix` | Prefijo del tag | `v` |
| `dry-run` | Solo calcula, no crea el tag | `false` |

**Outputs:**

| Output | Ejemplo |
|---|---|
| `version` | `1.3.0` |
| `tag` | `v1.3.0` |

---

### 3.4 `shared/git-merge`

Realiza un back-merge automático sin conflictos. Al no existir archivos de versión
(no hay `version.sbt` ni equivalente), este paso siempre es limpio.

**Inputs:**

| Input | Descripción |
|---|---|
| `source` | Rama de origen (ej. `main`) |
| `target` | Rama de destino (ej. `develop`) |

---

### 3.5 `shared/github-release`

Crea un GitHub Release con release notes autogeneradas a partir de los PRs incluidos
y sus labels. Usa `softprops/action-gh-release@v2`.

**Input requerido:**

| Input | Descripción |
|---|---|
| `tag` | Tag a publicar (ej. `v1.3.0`) |

---

### 3.6 `shared/deploy-trigger`

Dispara el deploy vía webhook HTTP. El `service-url` y el `token` se configuran como
secrets en cada repo del proyecto. Falla si el webhook devuelve un status distinto de
`200` o `204`.

**Inputs requeridos:**

| Input | Descripción |
|---|---|
| `environment` | `dev` \| `staging` \| `production` |
| `service-url` | URL del webhook de deploy |
| `token` | Token de autenticación |

---

## 4. Caso 1 — Backend: Scala / Pekko REST API

### 4.1 Action de stack: `backend/scala/lint-build`

Build completo con sbt: `scalafmt check` + `compile` + `test`.
El versionado usa **sbt-dynver** — no existe `version.sbt`.

**Inputs:**

| Input | Default |
|---|---|
| `java-version` | `"21"` |
| `scala-version` | `"3.4.2"` |

**Pasos que ejecuta:**

1. Setup Java (Temurin) con cache de sbt
2. Setup sbt
3. `sbt scalafmtCheckAll`
4. `sbt compile`
5. `sbt test`

---

### 4.2 Versionado: sbt-dynver

No existe `version.sbt`. El plugin `sbt-dynver` calcula la versión en build-time
leyendo el historial de Git:

| Situación | Rama | Versión calculada |
|---|---|---|
| Commit = tag `v1.2.0` | `main` | `1.2.0` |
| 3 commits después de `v1.2.0` | `develop` | `1.2.0+3-abc1234` |
| 5 commits en hotfix | `hotfix/v1.1.1` | `1.1.0+5-def5678` |
| Árbol sucio (local) | cualquiera | `1.2.0+3-abc1234+dirty` |

> **Sin conflictos en back-merge:** al no existir `version.sbt`, el back-merge
> automático de `hotfix → develop` siempre es limpio. Fue el problema histórico
> que este modelo resuelve.

---

### 4.3 Workflows del proyecto Scala

Los workflows viven en el repositorio del proyecto (ej. `BQN-UY/mi-api-scala`),
no en CI-CD.

#### `ci.yml` — se dispara en PRs y pushes a release/hotfix

```
Trigger: PR → develop  |  push → release/** y hotfix/**

Jobs:
  verify-label  → shared/label-check        (solo en PR)
  lint-build    → backend/scala/lint-build
  security      → shared/security-scan
```

#### `publish-snapshot.yml` — publica snapshot a Nexus

```
Trigger: push → develop  |  push → hotfix/**

La versión la calcula sbt-dynver automáticamente (formato: 1.2.0+3-abc1234).
Publica con: sbt publish
```

#### `start-release.yml` — crea la release branch

```
Trigger: workflow_dispatch
Input:   bump (major | minor | patch)

Pasos:
  1. Checkout develop con historial completo
  2. shared/semver-tag (dry-run: true) → calcula la próxima versión
  3. Crea y pushea branch release/v{version}
```

#### `make-release.yml` — hace el release completo

```
Trigger: workflow_dispatch
Inputs:  bump (major | minor | patch) + environment (staging | production)

Pasos:
  1. backend/scala/lint-build
  2. shared/security-scan
  3. shared/semver-tag              → crea el tag Git
  4. sbt publish                    → publica JAR release en Nexus
  5. shared/github-release          → crea GitHub Release con notas
  6. shared/git-merge               → merge release → main
  7. shared/git-merge               → back-merge main → develop
  8. shared/deploy-trigger          → dispara deploy via webhook
```

#### `start-hotfix.yml` — crea la hotfix branch

```
Trigger: workflow_dispatch
Input:   description (ej. "fix-null-parser")

Pasos:
  1. Checkout main con historial completo
  2. shared/semver-tag (dry-run: true, bump: patch) → calcula versión patch
  3. Crea branch hotfix/v{version}-{description}
```

---

## 5. Caso 2 — Frontend: HTML+JS / Backend: Python 3 + FastAPI

### 5.1 Actions de stack

#### `frontend/html-js/lint-build`

ESLint + Prettier check + npm build. Genera el artefacto en `/dist`.

| Input | Default |
|---|---|
| `node-version` | `"20"` |

Pasos: Setup Node → `npm ci` → `npx eslint` → `npx prettier --check` → `npm run build`

#### `backend/python/lint-test`

Ruff lint + format check + mypy + pytest.

| Input | Default |
|---|---|
| `python-version` | `"3.12"` |

Pasos: Setup Python → `pip install` → `ruff check` → `ruff format --check` → `mypy` → `pytest`

---

### 5.2 Workflows — Frontend HTML+JS

#### `ci.yml`
```
Jobs: verify-label + lint-build (html-js) + security
```

#### `publish-snapshot.yml`
El snapshot del frontend es el artefacto `/dist` guardado en GitHub Actions Artifacts
(no en Nexus). Si hay CDN o storage propio, se agrega un paso de upload.

#### `make-release.yml`
```
Pasos:
  1. frontend/html-js/lint-build
  2. shared/security-scan
  3. shared/semver-tag              → crea el tag Git
  4. shared/github-release          → crea GitHub Release (adjunta /dist)
  5. shared/git-merge               → merge release → main
  6. shared/git-merge               → back-merge main → develop
  7. shared/deploy-trigger          → dispara deploy via webhook
```

---

### 5.3 Workflows — Backend Python/FastAPI

#### `ci.yml`
```
Jobs: verify-label + lint-test (python) + security
```

#### `publish-snapshot.yml`
El snapshot de Python es una **imagen Docker** publicada en GHCR (GitHub Container
Registry), equivalente a los maven-snapshots del stack Scala.

```
Tag de imagen: ghcr.io/bqn-uy/{repo}:{github.sha}
```

#### `make-release.yml`
```
Pasos:
  1. backend/python/lint-test
  2. shared/security-scan
  3. shared/semver-tag              → crea el tag Git
  4. docker/build-push-action       → publica imagen con tag v{version} + latest
  5. shared/github-release          → crea GitHub Release
  6. shared/git-merge               → merge release → main
  7. shared/git-merge               → back-merge main → develop
  8. shared/deploy-trigger          → dispara deploy via webhook
```

---

## 6. Resumen comparativo de stacks

### Action de stack por tipo de repo

| Tipo de repo | Action de stack | Actions shared (siempre presentes) |
|---|---|---|
| Frontend HTML+JS | `frontend/html-js/lint-build` | `label-check`, `security-scan`, `semver-tag`, `git-merge`, `github-release`, `deploy-trigger` |
| Frontend Vaadin | `frontend/vaadin/lint-build` | ídem |
| Frontend Flutter | `frontend/flutter/lint-test` + `build-apk` | ídem |
| Backend Python/FastAPI | `backend/python/lint-test` | ídem |
| Backend Scala/Pekko | `backend/scala/lint-build` | ídem |
| Backend Node.js | `backend/node/lint-test` | ídem |

### Artefacto publicado por stack

| Stack | Snapshot | Release |
|---|---|---|
| Scala/Pekko | JAR en Nexus maven-snapshots | JAR en Nexus maven-releases + GitHub Release |
| Python/FastAPI | Imagen Docker en GHCR (SHA tag) | Imagen Docker en GHCR (`vX.Y.Z` + `latest`) + GitHub Release |
| HTML+JS | Artefacto `/dist` en Actions Artifacts | Artefacto `/dist` adjunto en GitHub Release |
| Vaadin | WAR/JAR en Nexus maven-snapshots | WAR/JAR en Nexus maven-releases + GitHub Release |
| Flutter | APK/IPA en Actions Artifacts | APK/IPA adjunto en GitHub Release |

### Conventional Commits y labels de PR

| Label PR | Tipo de commit | Bump SemVer sugerido |
|---|---|---|
| `breaking-change` | `feat(scope)!` o `fix!` | MAJOR (`1.2.3 → 2.0.0`) |
| `feature` | `feat:` | MINOR (`1.2.3 → 1.3.0`) |
| `fix` | `fix:` | PATCH (`1.2.3 → 1.2.4`) |
| `chore` | `chore:`, `docs:`, `refactor:` | PATCH |
| `deploy-action` | Cualquiera + infra requerida | Independiente del bump |

> **`breaking-change` vs `deploy-action`:** `breaking-change` habla de compatibilidad
> de API — los consumidores deben actualizar su código. `deploy-action` habla de
> requisitos de infraestructura — el ambiente necesita preparación antes del deploy.
> Son dimensiones independientes y pueden coexistir en el mismo PR.

---

## 7. Cómo agregar un nuevo stack

La estructura está diseñada para escalar sin modificar nada existente.
El procedimiento es siempre el mismo:

1. Decidir la capa: ¿`frontend/` o `backend/`?
2. Crear la subcarpeta con el nombre del stack:
   - `.github/actions/frontend/go/lint-build/`
   - `.github/actions/backend/go/lint-test/`
3. Escribir el `action.yml` usando como plantilla cualquier action existente del mismo tipo.
4. En el repo del proyecto, agregar el `uses:` correspondiente en los workflows.
   Las shared actions no cambian.
5. Abrir PR en `BQN-UY/CI-CD` con label `feature`. El CI valida que la nueva action funcione.

> **Zero impacto en repos existentes:** agregar `backend/go/lint-test/` no toca ningún
> workflow de Python, Scala ni ningún otro stack. El principio de aislamiento está
> garantizado por la estructura de carpetas.

---

## 8. Archivos de soporte en cada repo de proyecto

Estos archivos van en el repositorio del proyecto, no en CI-CD.

### 8.1 `.github/pull_request_template.md`

Guía al desarrollador para completar la información del PR y asignar el label correcto.

```markdown
## Descripción
<!-- Qué hace este PR y por qué -->

## Tipo de cambio (seleccionar label en GitHub — obligatorio)
- [ ] `feature`          — nueva funcionalidad retrocompatible
- [ ] `fix`              — corrección de bug retrocompatible
- [ ] `breaking-change`  — rompe compatibilidad de API
- [ ] `chore`            — refactor, deps, docs, tests
- [ ] `deploy-action`    — requiere acción previa en el ambiente

## Deploy action requerida
<!-- Si marcaste deploy-action, describir exactamente qué debe hacerse -->
<!-- Ej: migración DB, nueva variable de entorno, cambio de config -->
N/A

## Checklist
- [ ] Tests pasan localmente
- [ ] No hay secrets hardcodeados
- [ ] PR tiene exactamente un label asignado
```

### 8.2 `.github/labeler.yml`

Aplica labels automáticamente según el nombre de la rama fuente del PR.

```yaml
breaking-change:
  - head-branch: [".*breaking.*", ".*BREAKING.*"]

feature:
  - head-branch: ["feature/.*"]

fix:
  - head-branch: ["fix/.*", "hotfix/.*"]

chore:
  - head-branch: ["chore/.*", "docs/.*", "refactor/.*"]
```

---

## 9. Roles y responsabilidades

| Responsabilidad | Desarrollador | DevOps / Infra |
|---|---|---|
| Actions shared (CI-CD) | Propone cambios vía PR | Owner — aprueba y mergea |
| Actions de stack (CI-CD) | Owner — escribe y mantiene | Revisa |
| Workflows del proyecto | Owner | Revisa |
| Secrets del repo | — | Owner |
| Seguridad — hallazgos SAST | Resuelve | Asesora |
| Secretos detectados | Rota y limpia historial | Asesora |
| Decidir bump SemVer | Owner (en `make-release`) | — |
| Decidir `breaking-change` | Owner (en PR) | — |
| Decidir `deploy-action` | Owner (en PR) | Ejecuta en ambiente |

---

## 10. Glosario rápido

| Término | Significado en este contexto |
|---|---|
| **Composite action** | Action de GitHub definida en `action.yml` con `runs.using: composite`. Puede usarse como paso dentro de cualquier workflow. |
| **sbt-dynver** | Plugin de sbt que calcula la versión del proyecto leyendo el historial Git, sin necesidad de `version.sbt`. |
| **back-merge** | Merge automático de `main → develop` luego de un release, para mantener develop actualizado. |
| **SAST** | Static Application Security Testing. Análisis estático de código en busca de vulnerabilidades. |
| **GHCR** | GitHub Container Registry. Registro de imágenes Docker integrado en GitHub. |
| **webhook deploy** | Mecanismo donde el CI llama a un endpoint HTTP para disparar el deploy, en lugar de conectarse via SSH a Jenkins. |
| **dry-run** | Modo de ejecución que calcula el resultado (ej. próxima versión) sin efectuar cambios reales en el sistema. |
