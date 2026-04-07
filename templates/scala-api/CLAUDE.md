# CI/CD v2 — Contexto para AI

Este proyecto usa CI/CD v2 de BQN-UY. Las actions reutilizables viven en
`BQN-UY/CI-CD`. Los workflows de este proyecto viven en `.github/workflows/`.

## Branching model

| Rama | Propósito | Merge destino |
|---|---|---|
| `feature/*` | Nueva funcionalidad | `develop` via PR |
| `develop` | Integración continua de la próxima versión | — |
| `release/vX.Y.Z` | Estabilización del release candidate | `main` via make-release |
| `hotfix/vX.Y.Z-desc` | Fix urgente a lo que está en producción | `main` via make-release |
| `main` | Producción | — |

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

- Fixes detectados en testing durante un release → commit en `release/vX.Y.Z`, **NUNCA en `develop`**
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

## Secrets requeridos

| Secret | Uso |
|---|---|
| `NEXUS_USER` / `NEXUS_PASSWORD` / `NEXUS_URL` | Publicar JAR en Nexus |
| `DEPLOY_TESTING_URL` / `DEPLOY_TESTING_TOKEN` | Deploy a testing |
| `DEPLOY_STAGING_URL` / `DEPLOY_STAGING_TOKEN` | Deploy a staging |
| `DEPLOY_PRODUCTION_URL` / `DEPLOY_PRODUCTION_TOKEN` | Deploy a production |

## Qué NO hacer

- No agregar lógica de build/deploy directamente en los workflows — usar las actions de `BQN-UY/CI-CD`
- No hardcodear versiones de Java — el default (`"21"`) está en `backend/scala/lint-build`
- No usar nombres de secrets distintos a los documentados arriba
- No modificar el branching model — `develop` nunca mergea directo a `main`
- No commitear en `develop` para resolver un issue de un release en curso
