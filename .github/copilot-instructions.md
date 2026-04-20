# Copilot instructions — BQN-UY/CI-CD

> **Doc canónico**: `docs/v2-hito2-deploy-spec.md`. Si hay conflicto, ese gana.

## Qué es este repo

Repositorio centralizado de CI/CD. Composite actions v2 viven en `.github/actions/`. Reusable workflows v2 (con prefijo `<stack>-`) viven en `.github/workflows/`. Workflows sin prefijo en `.github/workflows/` son **v1 legacy** — no modificar.

## Principio rector v2

**v2 NO depende de `BQN-UY/jenkins`.** Workflows v2 nuevos NO invocan `jenkins-deploy-trigger`, NO leen `sistemas.json`, NO usan secrets `JENKINS_DEPLOY_*`. El composite `shared/jenkins-deploy-trigger` se conserva sólo por compatibilidad con repos en v1.

## Reglas estrictas

- Modificar: `.github/actions/`, `.github/workflows/<stack>-*.yml`, `templates/`, `docs/`
- NO tocar workflows en `.github/workflows/` sin prefijo `<stack>-` (v1 legacy)
- Los workflows ejecutables de cada proyecto NO viven aquí — viven en cada repo y son callers cortos al reusable

## Tres grupos de proyectos

| Grupo | Storage | Versionado |
|---|---|---|
| Server apps (APIs/WARs/python) | **GH Releases** | `v<NEXT>-snapshot.NNN`, `vX.Y.Z-rc.NNN`, `vX.Y.Z` |
| Client apps (BPos/GPos/IDH) | TBD (probablemente GH Releases) | TBD |
| Libs (scala libs) | **Nexus** | `<base>-SNAPSHOT` Maven-standard |

## Versionado v2 server apps

- push develop → `v<NEXT>-snapshot.NNN` (NEXT = last_final + bump leído de `.github/next-bump`)
- push release/hotfix → `vX.Y.Z-rc.NNN` (auto en push, NO hay workflow_dispatch publish-rc)
- make-release → `vX.Y.Z` (final, marcado `latest`)
- NNN: 3 dígitos zero-padded, auto-incrementa
- Cleanup: workflow daily conserva últimos 3 snapshots por target

## Tag protection en repos app

- `v[0-9]*` → protegido (releases finales inmutables)
- `v*-rc.*` → protegido (RCs auditados inmutables)
- `v*-snapshot.*` → libre (cleanup borra)

## Tag `v2` de este repo (CI-CD)

Móvil por diseño — consumers referencian `BQN-UY/CI-CD@v2`. **No protegido** (requiere force-push). Mover al HEAD de main cuando el PR toca `.github/actions/**`, `.github/workflows/<stack>-*.yml` o `templates/**`. No mover para cambios doc-only (`docs/**`, `CLAUDE.md`, `copilot-instructions.md`). Comando: `git tag -f v2 origin/main && git push -f origin v2`.

## Estructura de una action v2

```
.github/actions/<capa>/<stack>/<nombre>/action.yml
```

Capas: `shared/` (agnóstico) | `frontend/<stack>/` | `backend/<stack>/`

## Ambientes (deploy v2 server apps, vía GA-native cuando esté listo)

| Rama | Ambiente |
|---|---|
| `develop` | testing |
| `release/**`, `hotfix/**` | staging |
| `make-release` | production |

## Para libs (Maven en Nexus)

Las libs siguen modelo standard. Cada `build.sbt` debe declarar:
```scala
ThisBuild / dynverSeparator         := "-"
ThisBuild / dynverSonatypeSnapshots := true
```

Apps NO usan estas settings (no publican a Nexus).

## Referencia

- Spec canónico: `docs/v2-hito2-deploy-spec.md`
- Roadmap sin Jenkins: `docs/v2-sin-jenkins-roadmap.md`
- Catálogo workflows: `docs/migration-v2.md`
