# CI/CD v2 — Contexto para AI

Este proyecto usa CI/CD v2 de BQN-UY. Las actions reutilizables viven en
`BQN-UY/CI-CD`. Los workflows de este proyecto viven en `.github/workflows/`.

## Branching model

### Ramas de trabajo (corta duración — siempre via PR)

| Rama | Sale de | Merge hacia | Label PR | Cuándo usar |
|---|---|---|---|---|
| `feature/*` | `develop` | `develop` | `feature` | Nueva funcionalidad retrocompatible |
| `fix/*` | `develop` · `release/**` · `hotfix/**` | mismo origen | `fix` | Corrección de bug |
| `chore/*` | `develop` | `develop` | `chore` | Mantenimiento: configuración, CI, tests |
| `docs/*` | `develop` | `develop` | `chore` | Documentación |
| `refactor/*` | `develop` | `develop` | `chore` | Refactoring sin cambio de comportamiento |
| `dependabot/*` | `develop` | `develop` | `update` | Actualización de dependencias (Dependabot) |
| `scala-steward/*` | `develop` | `develop` | `update` | Actualización de dependencias (Scala Steward) |

> `fix/*` es el único tipo que puede salir de una rama distinta a `develop`.
> Un `fix/*` desde `release/**` corrige un bug detectado durante el testeo del RC.
> Un `fix/*` desde `hotfix/**` corrige un bug secundario descubierto dentro del hotfix.
>
> `dependabot/*` y `scala-steward/*` son creadas automáticamente por las herramientas — no crearlas manualmente.
> `auto-label` les asigna `update` automáticamente; Dependabot también se configura con `labels: ["update"]` en `.github/dependabot.yml`.

### Ramas de ciclo (larga duración — gestionadas por workflows)

| Rama | Sale de | Cierra con | Propósito |
|---|---|---|---|
| `develop` | — | — | Integración continua de la próxima versión |
| `release/vX.Y.Z` | `develop` via `start-release` | `make-release` → `main` | Estabilización del RC |
| `hotfix/vX.Y.Z-desc` | `main` via `start-hotfix` | `make-release` → `main` | Fix urgente a producción |
| `main` | — | — | Producción |

## Semántica de ambientes

| Rama | Nexus | Ambiente | Propósito |
|---|---|---|---|
| `develop` | snapshots | testing | Features de la próxima versión |
| `release/**` | snapshots | testing | Fixes del release en curso |
| `hotfix/**` | snapshots | staging | Fix urgente — espejo de producción |
| `make-release` | **releases** | production | Versión definitiva e irreversible |

- **testing**: ambiente compartido por `develop` y `release/**`. Nunca mezcla con producción, pero un push a `develop` puede pisar un deploy de `release/**` que esté siendo validado. Congelar merges a `develop` mientras se valida un release.
- **staging**: espejo de producción, exclusivo para validar hotfixes. Nunca comparte estado con testing.
- **production**: solo vía `make-release` manual. Crea tag Git, publica en Nexus releases, crea GitHub Release, mergea a main y hace back-merge a develop.

## Reglas críticas

- `feature/*`, `chore/*`, `docs/*`, `refactor/*` salen **siempre** de `develop` — nunca de `release/**` ni `hotfix/**`
- `fix/*` desde `release/**` → corrige un bug del RC en curso; PR hacia `release/vX.Y.Z`, **NUNCA hacia `develop`**
- `fix/*` desde `hotfix/**` → corrige un bug secundario del hotfix; PR hacia `hotfix/vX.Y.Z-desc`
- `dependabot/*` y `scala-steward/*` apuntan **siempre a `develop`** — nunca a `release/**` ni `hotfix/**`
- `deploy-action` se usa cuando el PR requiere una acción manual en infra antes o durante el deploy (ej. nueva variable de entorno, migración de DB, nuevo secret, nuevo componente de infra). Reemplaza al label de tipo (`feature`, `fix`, etc.) — describir el tipo de cambio en el cuerpo del PR y la acción requerida en la sección "Deploy action requerida"
- `develop` después de `start-release` → próxima versión, no afecta el release en curso
- Los fixes de `release/**` vuelven a `develop` al final via back-merge automático de `make-release`
- `hotfix/**` es exclusivo para fixes urgentes de la versión en producción — no mezclar con features
- `make-release` es irreversible — solo ejecutar cuando el release fue validado en testing

## Workflows

| Archivo | Trigger | Qué hace |
|---|---|---|
| `ci.yml` | PR → develop · push release/\*\* · push hotfix/\*\* | lint + build + security |
| `publish-and-deploy.yml` | push develop · push release/\*\* · push hotfix/\*\* | snapshot Nexus + deploy automático |
| `start-release.yml` | manual (workflow_dispatch) | crea `release/vX.Y.Z` desde develop |
| `make-release.yml` | manual (workflow_dispatch) | tag + Nexus release + GitHub Release + deploy production + back-merge |
| `start-hotfix.yml` | manual (workflow_dispatch) | crea `hotfix/vX.Y.Z-desc` desde main |

## Secrets y variables requeridos

| Secret / Variable | Nivel | Uso |
|---|---|---|
| `NEXUS_USER` / `NEXUS_PASSWORD` / `NEXUS_URL` | repo | Publicar JAR en Nexus |
| `JENKINS_DEPLOY_URL` | **org** | URL base del webhook GWT (igual para todos los ambientes) |
| `JENKINS_DEPLOY_TESTING_TOKEN` | **org** | Token GWT — rutea al job `deploy-nexus-testing` |
| `JENKINS_DEPLOY_STAGING_TOKEN` | **org** | Token GWT — rutea al job `deploy-nexus-staging` |
| `JENKINS_DEPLOY_PRODUCTION_TOKEN` | **org** | Token GWT — rutea al job `deploy-nexus-production` |
| `vars.SISTEMA` | repo | Nombre del servicio — se pasa en el payload al webhook |

## Qué NO hacer

- No agregar lógica de build/deploy directamente en los workflows — usar las actions de `BQN-UY/CI-CD`
- No hardcodear versiones de Java — el default (`"21"`) está en `backend/scala/lint-build`
- No usar nombres de secrets distintos a los documentados arriba
- No modificar el branching model — `develop` nunca mergea directo a `main`
- No commitear en `develop` para resolver un issue de un release en curso
