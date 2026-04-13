# BQN-UY/CI-CD — Contexto para AI

Repositorio centralizado de CI/CD de la organización BQN-UY.
Contiene composite actions reutilizables (v2), reusable workflows v2 y los reusable workflows heredados (v1).

## Estructura del repo

```
.github/
├── actions/          ← composite actions v2  — MODIFICAR AQUÍ
│   ├── shared/       ← lógica agnóstica de stack (jenkins-deploy-trigger, semver-tag, etc.)
│   ├── frontend/     ← acciones por stack frontend (html-js, vaadin, flutter)
│   └── backend/      ← acciones por stack backend (scala, python, node)
└── workflows/        ← convive v1 (legacy) y v2 (reusable workflows)
    ├── <stack>-<tipo>-<workflow>.yml  ← v2  (ej. scala-api-ci.yml) — MODIFICAR AQUÍ
    ├── setup-labels.yml               ← v2 agnóstico al stack
    └── (resto)                        ← v1 legacy — NO MODIFICAR

templates/            ← callers cortos listos para copiar en repos de proyecto
docs/                 ← documentación de referencia v2
```

> GitHub no soporta subcarpetas en `.github/workflows/` — la taxonomía stack/tipo se expresa en el nombre del archivo (`<stack>-<tipo>-<workflow>.yml`).

## Reglas

- Modificar normalmente `.github/actions/`, `.github/workflows/<stack>-*.yml`, `templates/` y `docs/`
- Excepciones permitidas en raíz y `.github/`: `CLAUDE.md`, `.github/copilot-instructions.md` y archivos de configuración del repo
- NUNCA modificar los workflows v1 legacy en `.github/workflows/` (los que no tienen prefijo `<stack>-`): `merge-update.yml`, `release-drafter.yml`, `remove-old-artifacts.yml`, `scala-ci.yml`, `scala-deploy-jar.yml`, `scala-deploy-web.yml`, `scala-make-release-jar.yml`, `scala-make-release-lib.yml`, `scala-make-release-web.yml`, `scala-publish-snapshot-lib.yml`, `start-hotfix.yml`
- Los workflows ejecutables de cada proyecto NO viven aquí — viven en el repo del proyecto y son callers cortos al reusable workflow correspondiente
- Toda nueva action v2 va en `.github/actions/<capa>/<stack>/<nombre>/action.yml`
- Todo nuevo reusable workflow v2 va en `.github/workflows/<stack>-<tipo>-<workflow>.yml` con `on: workflow_call`

## Ambientes válidos (`shared/jenkins-deploy-trigger`)

`testing` | `staging` | `production`

## Semántica de ambientes

| Rama del proyecto | Ambiente | Propósito |
|---|---|---|
| `develop` | testing | Features de la próxima versión |
| `release/**` | testing | Fixes del release en curso |
| `hotfix/**` | staging | Fix urgente — espejo de producción |
| `make-release` | production | Único deploy irreversible |

## Convención de versionado (v2)

- **Snapshots dynver** (cualquier push entre tags): `X.Y.Z-SNAPSHOT` (formato Maven). El repo Nexus `maven-snapshots` requiere el sufijo `-SNAPSHOT`.
- **Release candidate**: tag `vX.Y.Z-rc.N` creado por `scala-api-publish-rc.yml` (workflow_dispatch en release/** o hotfix/**). N arranca en 1, se autoincrementa por iteración.
- **Release final**: tag `vX.Y.Z` creado por `scala-api-make-release.yml` al promover a producción.

Cada proyecto Scala debe declarar en `build.sbt`:

```scala
ThisBuild / dynverSeparator         := "-"   // evita '+' (Nexus rechaza %2B; SemVer lo ignora al ordenar)
ThisBuild / dynverSonatypeSnapshots := true  // formato Maven '<base>-SNAPSHOT' entre tags
```

## Cómo agregar una nueva action v2

1. Decidir capa: ¿`shared/`, `frontend/<stack>/` o `backend/<stack>/`?
2. Crear `action.yml` en la carpeta correspondiente
3. Cablearla dentro del reusable workflow del stack/tipo correspondiente (`.github/workflows/<stack>-<tipo>-*.yml`)
4. Documentar en `docs/migration-v2.md`

## Cómo agregar un reusable workflow v2 para un nuevo stack/tipo

1. Crear `.github/workflows/<stack>-<tipo>-<workflow>.yml` con `on: workflow_call` (ej. `scala-lib-ci.yml`)
2. Componerlo con las composite actions correspondientes
3. Crear `templates/<stack>-<tipo>/` con callers cortos (uno por workflow)
4. Documentar en `docs/migration-v2.md`

## Referencia

- Documentación completa: `docs/migration-v2.md`
- Guía de migración Scala: `docs/scala-migration-v2.md`
- Workflows v1 (legacy): `docs/workflows-v1.md`
