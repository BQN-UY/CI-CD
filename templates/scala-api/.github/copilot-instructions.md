# Copilot instructions — Scala API (CI/CD v2)

## CI/CD

Este proyecto usa CI/CD v2 de BQN-UY. No agregar lógica de build o deploy
directamente en los workflows — todo se delega a actions de `BQN-UY/CI-CD`.

## Branching model

- `feature/*` → PR → `develop`
- `develop` → próxima versión (deploy automático a **testing**)
- `release/vX.Y.Z` → release candidate (deploy automático a **testing**)
- `hotfix/vX.Y.Z-desc` → fix urgente a producción (deploy automático a **staging**)
- `main` → producción (solo via `make-release`)

## Reglas de branching

- Fixes durante un release → commit en `release/vX.Y.Z`, NUNCA en `develop`
- `develop` después de `start-release` = próxima versión, no el release en curso
- `hotfix/**` = exclusivo para fixes de la versión en producción

## Ambientes

| Rama | Ambiente |
|---|---|
| `develop`, `release/**` | testing |
| `hotfix/**` | staging |
| `make-release` | production |

## Secrets de deploy

```
JENKINS_DEPLOY_URL (compartido)
JENKINS_DEPLOY_TESTING_TOKEN
JENKINS_DEPLOY_STAGING_TOKEN
JENKINS_DEPLOY_PRODUCTION_TOKEN
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
