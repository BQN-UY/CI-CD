# Copilot instructions — BQN-UY/CI-CD

## Qué es este repo

Repositorio centralizado de CI/CD. Las composite actions v2 viven en `.github/actions/`.
Los reusable workflows v1 (legacy) viven en `.github/workflows/` — no modificar.

## Reglas estrictas

- Solo modificar `.github/actions/`, `templates/` y `docs/`
- NUNCA tocar `.github/workflows/` (legacy v1)
- Los workflows de proyecto no viven aquí — viven en cada repo de proyecto
- Ambientes válidos en deploy-trigger: `testing`, `staging`, `production`

## Estructura de una action v2

```
.github/actions/<capa>/<stack>/<nombre>/action.yml
```

Capas: `shared/` (agnóstico de stack) | `frontend/<stack>/` | `backend/<stack>/`

## Semántica de ambientes

| Rama | Ambiente |
|---|---|
| `develop`, `release/**` | testing |
| `hotfix/**` | staging |
| `make-release` | production |

## Secrets de deploy (patrón de nombres)

`JENKINS_DEPLOY_TESTING_URL` / `JENKINS_DEPLOY_TESTING_TOKEN`
`JENKINS_DEPLOY_STAGING_URL` / `JENKINS_DEPLOY_STAGING_TOKEN`
`JENKINS_DEPLOY_PRODUCTION_URL` / `JENKINS_DEPLOY_PRODUCTION_TOKEN`
