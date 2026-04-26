# BQN-UY/CI-CD — Contexto para AI

Repositorio centralizado de CI/CD de la organización BQN-UY.
Contiene composite actions reutilizables (v2), reusable workflows v2 y los reusable workflows heredados (v1).

> **Documento canónico del modelo v2**: `docs/v2-hito2-deploy-spec.md`. Si hay conflicto entre cualquier documento y el spec, **el spec gana**. Este CLAUDE.md condensa lo operativo.

## Contexto organizacional (unidad Banquinet)

Equipo, roles, restricciones estructurales, herramientas, stakeholders y política IA de la unidad Banquinet: [`BQN-UY/banquinet/README.md@8fb0749`](https://github.com/BQN-UY/banquinet/blob/8fb07499762e059a3ca49cf960f9bd1f66cda5e4/README.md) (permalink al commit fijo). Útil para razonar sobre alcance, estimación y quién decide/aprueba. **Actualizar el sha del permalink cuando cambie el README canónico** del repo `BQN-UY/banquinet`.

**Tracking cross-repo de esta iniciativa**: issue canónico [`BQN-UY/banquinet#3 — Tracking — CI/CD v2`](https://github.com/BQN-UY/banquinet/issues/3). Fuente única de verdad del estado global de la migración v2. Este repo mantiene spec + código; el estado organizacional de la iniciativa vive allí. Convención de uso: [`BQN-UY/banquinet/docs/TRACKING.md`](https://github.com/BQN-UY/banquinet/blob/main/docs/TRACKING.md).

### Ritual — update al tracking issue

Al cerrar un PR o issue que cambia materialmente el estado de la migración v2, postear un **update comment** a [`banquinet#3`](https://github.com/BQN-UY/banquinet/issues/3). Previene fragmentación de contexto entre sesiones.

**Aplica cuando** el cambio:
- cierra o avanza un hito del roadmap v2 (1, 2, 2bis, 3, 4, 5),
- cierra o identifica un bloqueo externo,
- modifica composites, reusable workflows, templates o specs canónicos (`docs/v2-*-spec.md`, `docs/v2-*-roadmap.md`),
- formaliza políticas (tag `v2`, IA, versionado, secrets, automation identity, ritual de tracking).

**NO aplica** para cambios operativos sin impacto en estado organizacional (typos, renames internos, dependabot bumps sin cambio de API expuesta a consumers).

**Formato del comment** (convención de [`TRACKING.md`](https://github.com/BQN-UY/banquinet/blob/main/docs/TRACKING.md) §2.2):

```markdown
## Update YYYY-MM-DD — <agente/sesión>

- **Hito**: qué se cerró/avanzó + links a PRs/commits.
- **Próximo**: próximos candidatos (resaltar los autónomos sin bloqueos externos).
- **Bloqueos**: cambios en bloqueos externos.
- **Links**: PRs, commits, issues relevantes.
```

Si además corresponde actualizar el **body** del issue (snapshot vivo — ej. marcar hito como hecho, agregar housekeeping nuevo, cambiar bloqueos activos), editar el body primero y dejar un comment corto adicional (`## Update YYYY-MM-DD — body actualizado`) explicando la edición. Nunca sobreescribir comentarios ajenos; si hay conflicto al editar el body, re-leer y re-aplicar, explicitándolo en el comentario.

## Estructura del repo

```
.github/
├── actions/          ← composite actions v2  — MODIFICAR AQUÍ
│   ├── shared/       ← lógica agnóstica de stack (semver-tag, github-release, security-scan, etc.)
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

## Principio rector v2

**v2 no depende de `BQN-UY/jenkins` para nada.** Ese repo (rama `production`, scripts groovy, `sistemas.json`) queda congelado como legacy v1. Workflows v2 nuevos NO invocan `jenkins-deploy-trigger`, NO leen archivos del repo jenkins, NO referencian secrets `JENKINS_DEPLOY_*`. Ver `docs/v2-sin-jenkins-roadmap.md`.

> El composite `shared/jenkins-deploy-trigger` se conserva por compatibilidad con repos aún en v1, pero NO se usa en código nuevo de v2.

## Tres grupos de proyectos

| Grupo | Ejemplos | Storage de artefactos | Versionado |
|---|---|---|---|
| **Server apps** | scala APIs, WARs, python servers | **GH Releases** del propio repo | `v<NEXT>-snapshot.NNN` / `vX.Y.Z-rc.NNN` / `vX.Y.Z` |
| **Client apps** | BPos, GPos, IDH (firmwares) | TBD (probablemente GH Releases) | TBD por equipo |
| **Libs** | scala libs, protocolos | **Nexus** maven-snapshots / maven-releases | `<base>-SNAPSHOT` (Maven-standard) |

Detalle completo en `docs/v2-hito2-deploy-spec.md` §1.

## Convención de versionado v2 (server apps)

| Trigger | Tag GH | Tipo | Cleanup |
|---|---|---|---|
| push `develop` | `v<NEXT>-snapshot.NNN` | pre-release | sí (workflow daily, conserva últimos 3 por target) |
| push `release/vX.Y.Z` o `hotfix/vX.Y.Z-desc` | `vX.Y.Z-rc.NNN` | pre-release | no |
| `make-release` (workflow_dispatch) | `vX.Y.Z` | release final | no |

- **NNN**: 3 dígitos zero-padded (`001`, `002`, ...), auto-incrementa por trigger
- **`<NEXT>`**: derivada de `last_final_tag + bump`, donde `bump ∈ {minor, major}` se lee de `.github/next-bump` (default `minor`)
- **RCs son auto en push** (no hay `publish-rc` workflow_dispatch separado)
- `.github/next-bump` lo actualiza un workflow al merger PRs con label `breaking-change`; `make-release` lo resetea a `minor`

> **NO confundir con libs**: las libs siguen el modelo Maven-standard `<base>-SNAPSHOT` en Nexus. La convención de arriba es para server apps.

## Tag protection requerida en repos app

| Patrón | Protegido contra | Razón |
|---|---|---|
| `v[0-9]*` | delete + force-push | releases finales son inmutables |
| `v*-rc.*` | delete + force-push | RCs auditados son inmutables |
| `v*-snapshot.*` | (libre) | cleanup workflow necesita borrarlos |

## Tag `v2` de este repo

Los consumers (repos de proyecto) referencian este repo vía `BQN-UY/CI-CD@v2` en sus callers. A diferencia de los tags de repos app (inmutables), **`v2` de este repo es móvil por diseño** — se mueve al HEAD de main bajo criterio explícito. **No debe estar protegido** en Settings → Tag protection (requiere force-push).

**Regla — cuándo mover** (según los paths tocados por el PR mergeado):

| Paths tocados | ¿Mueve `v2`? |
|---|---|
| `.github/actions/**` | Sí |
| `.github/workflows/<stack>-<tipo>-*.yml` (reusables v2, ej. `scala-api-ci.yml`, `scala-lib-publish-snapshot.yml`) | Sí |
| `templates/**` | Sí |
| `docs/**`, `CLAUDE.md`, `.github/copilot-instructions.md` | No |
| Resto de `.github/workflows/*.yml` (v1 legacy, lista explícita en §Reglas) | No |

**Cómo mover** (post-merge, a cargo del maintainer del repo):

```bash
git fetch origin main
git tag -f v2 origin/main
git push -f origin v2
```

**Checkpoint por hito**: al cerrar cada hito (1, 2, 3, 4, 5), auditar con `git log v2..main --oneline` que no queden commits code-visible sin propagar.

**Escape para consumers**: quien necesite congelación total puede pinear al SHA (ej. `BQN-UY/CI-CD@<sha>`) en vez de `@v2`. Cuando exista versionado semver del propio CI-CD (`vX.Y.Z`), también será opción.

## Ambientes (deploy v2 server apps)

| Rama del proyecto | Ambiente | Propósito |
|---|---|---|
| `develop` | testing | Features de la próxima versión (auto-deploy desde snapshot) |
| `release/**` | staging | Validación del RC (auto-deploy desde rc) |
| `hotfix/**` | staging | Fix urgente — espejo de producción (auto-deploy desde rc) |
| `make-release` | production | Único deploy irreversible (manual por Soporte) |

> Mecanismo concreto del deploy GA-native: pendiente de Hito 2/3. Ver `docs/v2-hito2-deploy-spec.md`.

> Composite legacy `shared/jenkins-deploy-trigger` admite ambientes `testing | staging | production` para repos aún en v1.

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

- **Spec canónico v2 (server apps)**: `docs/v2-hito2-deploy-spec.md`
- Hoja de ruta v2 sin Jenkins: `docs/v2-sin-jenkins-roadmap.md`
- Documentación completa: `docs/migration-v2.md`
- Guía de migración Scala: `docs/scala-migration-v2.md`
- Workflows v1 (legacy): `docs/workflows-v1.md`
