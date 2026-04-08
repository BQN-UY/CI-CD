# Copilot instructions — Scala API (CI/CD v2)

## CI/CD

Este proyecto usa CI/CD v2 de BQN-UY. No agregar lógica de build o deploy
directamente en los workflows — todo se delega a actions de `BQN-UY/CI-CD`.

## Branching model

### Ramas de trabajo (siempre via PR)

| Rama | Sale de | Merge hacia | Label | Cuándo usar |
|---|---|---|---|---|
| `feature/*` | `develop` | `develop` | `feature` | Nueva funcionalidad |
| `fix/*` | `develop` · `release/**` · `hotfix/**` | mismo origen | `fix` | Corrección de bug |
| `chore/*` | `develop` | `develop` | `chore` | Configuración, CI, tests |
| `docs/*` | `develop` | `develop` | `chore` | Documentación |
| `refactor/*` | `develop` | `develop` | `chore` | Refactoring sin cambio de comportamiento |
| `dependabot/*` | `develop` | `develop` | `deps` | Actualización de deps (Dependabot) |
| `scala-steward/*` | `develop` | `develop` | `deps` | Actualización de deps (Scala Steward) |

### Ramas de ciclo

| Rama | Sale de | Cierra con |
|---|---|---|
| `release/vX.Y.Z` | `develop` via `start-release` | `make-release` → `main` |
| `hotfix/vX.Y.Z-desc` | `main` via `start-hotfix` | `make-release` → `main` |

## Reglas de branching

- `feature/*`, `chore/*`, `docs/*`, `refactor/*` salen siempre de `develop`
- `fix/*` es el único tipo que puede salir de `release/**` o `hotfix/**`
- Fixes durante un release → `fix/*` desde `release/vX.Y.Z`, PR hacia `release/vX.Y.Z`, NUNCA hacia `develop`
- `dependabot/*` y `scala-steward/*` apuntan siempre a `develop` — nunca a `release/**` ni `hotfix/**`
- `hotfix/**` = exclusivo para fixes de la versión en producción
- `deploy-action` = el PR requiere acción manual en infra antes/durante el deploy (nueva env var, migración DB, nuevo secret, nuevo componente). Reemplaza al label de tipo — describir el cambio en el cuerpo del PR

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
