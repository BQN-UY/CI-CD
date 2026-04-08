# Copilot instructions — Scala API (CI/CD v2)

## CI/CD

Este proyecto usa CI/CD v2 de BQN-UY. No agregar lógica de build o deploy
directamente en los workflows — todo se delega a actions de `BQN-UY/CI-CD`.

## Branching model

### Ramas de trabajo (siempre via PR)

| Rama | Sale de | Merge hacia | Cuándo usar |
|---|---|---|---|
| `feature/*` | `develop` | `develop` | Nueva funcionalidad |
| `fix/*` | `develop` · `release/**` · `hotfix/**` | mismo origen | Corrección de bug |
| `chore/*` | `develop` | `develop` | Deps, configuración, CI |
| `docs/*` | `develop` | `develop` | Documentación |
| `refactor/*` | `develop` | `develop` | Refactoring sin cambio de comportamiento |

### Ramas de ciclo

| Rama | Sale de | Cierra con |
|---|---|---|
| `release/vX.Y.Z` | `develop` via `start-release` | `make-release` → `main` |
| `hotfix/vX.Y.Z-desc` | `main` via `start-hotfix` | `make-release` → `main` |

## Reglas de branching

- `feature/*`, `chore/*`, `docs/*`, `refactor/*` salen siempre de `develop`
- `fix/*` es el único tipo que puede salir de `release/**` o `hotfix/**`
- Fixes durante un release → `fix/*` desde `release/vX.Y.Z`, PR hacia `release/vX.Y.Z`, NUNCA hacia `develop`
- `hotfix/**` = exclusivo para fixes de la versión en producción

## Ambientes

| Rama | Ambiente |
|---|---|
| `develop`, `release/**` | testing |
| `hotfix/**` | staging |
| `make-release` | production |

## Secrets y variables de deploy

```
# Org-level (BQN-UY) — no configurar por repo
JENKINS_DEPLOY_URL              # URL base del webhook GWT
JENKINS_DEPLOY_TESTING_TOKEN    # token → rutea a deploy-nexus-testing
JENKINS_DEPLOY_STAGING_TOKEN    # token → rutea a deploy-nexus-staging
JENKINS_DEPLOY_PRODUCTION_TOKEN # token → rutea a deploy-nexus-production

# Repo-level variable
vars.SISTEMA   # nombre del servicio (ej. payments-api)
```

## Secrets de Nexus

```
NEXUS_USER / NEXUS_PASSWORD / NEXUS_URL
```

## Qué NO hacer

- No modificar la lógica interna de los workflows en `.github/workflows/`
- No usar nombres de secrets distintos a los documentados
- No commitear fixes de release en `develop`
- No ejecutar `make-release` sin haber validado en testing primero
