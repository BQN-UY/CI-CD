# Copilot instructions — Scala API (CI/CD v2)

> **Doc canónico**: `BQN-UY/CI-CD/docs/v2-hito2-deploy-spec.md`. Si hay conflicto, ese gana.

## CI/CD

Este proyecto usa CI/CD v2 de BQN-UY. No agregar lógica de build o deploy directamente en los workflows — todo se delega a actions de `BQN-UY/CI-CD`.

## Tipo de proyecto

**Server app** — los artefactos van a **GitHub Releases** del propio repo (NO a Nexus). Cada build crea un Release/Pre-release con el JAR adjunto.

## Branching model

### Ramas de trabajo (siempre via PR)

| Rama | Sale de | Merge hacia | Label | Cuándo usar |
|---|---|---|---|---|
| `feature/*` | `develop` | `develop` | `feature` | Nueva funcionalidad |
| `fix/*` | `develop` · `release/**` · `hotfix/**` | mismo origen | `fix` | Corrección de bug |
| `chore/*` | `develop` | `develop` | `chore` | Configuración, CI, tests |
| `docs/*` | `develop` | `develop` | `chore` | Documentación |
| `refactor/*` | `develop` | `develop` | `chore` | Refactoring sin cambio de comportamiento |
| `dependabot/*` | `develop` | `develop` | `update` | Actualización de deps (Dependabot) |
| `scala-steward/*` | `develop` | `develop` | `update` | Actualización de deps (Scala Steward) |

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
- `breaking-change` label: marca que el próximo release necesita major bump (workflow lo registra en `.github/next-bump`)
- `deploy-action` = el PR requiere acción manual en infra antes/durante el deploy. Reemplaza al label de tipo — describir en cuerpo del PR.

## Versionado

| Trigger | Tag GH | Tipo | Ambiente del deploy |
|---|---|---|---|
| push `develop` | `v<NEXT>-snapshot.NNN` | pre-release | testing |
| push `release/vX.Y.Z` | `vX.Y.Z-rc.NNN` | pre-release | staging |
| push `hotfix/vX.Y.Z-desc` | `vX.Y.Z-rc.NNN` | pre-release | staging |
| `make-release` (manual) | `vX.Y.Z` | release final | production (manual) |

- NNN: 3 dígitos zero-padded, auto-incrementa
- `<NEXT>` = `last_final_tag + bump`, donde `bump` viene de `.github/next-bump` (default `minor`, cambia a `major` en PR con label `breaking-change`)

## Tag protection (configurar en GH Settings)

- `v[0-9]*` → protegido (releases finales inmutables)
- `v*-rc.*` → protegido (RCs auditados inmutables)
- `v*-snapshot.*` → libre (cleanup workflow borra)

## Secrets

Para server apps no se requieren secrets especiales — el `GITHUB_TOKEN` que GitHub provee automáticamente alcanza para publish y deploy GA-native (cuando exista).

## Qué NO hacer

- No modificar la lógica interna de los workflows en `.github/workflows/` — son callers cortos al reusable
- No publicar a Nexus desde este repo (server apps van a GH Releases)
- No declarar `dynverSeparator` ni `dynverSonatypeSnapshots` en `build.sbt` (son para libs)
- No usar secrets `JENKINS_DEPLOY_*` ni `NEXUS_*` (no aplican en v2 server apps)
- No commitear fixes de release en `develop`
- No ejecutar `make-release` sin haber validado en testing primero
- No borrar tags `v[0-9]*` ni `v*-rc.*`
