# BQN-UY/CI-CD

Repositorio central de CI/CD de la organización. Contiene toda la lógica de build, lint,
test, release y deploy. Los repositorios de proyecto no tienen lógica de CI propia —
solo definen cuándo disparar cada workflow.

---

## Estructura

```
.github/
├── actions/               # Composite actions v2 (referenciables con @v2)
│   ├── shared/            # Language-agnostic: security, versionado, deploy
│   ├── backend/           # scala/, python/, node/
│   └── frontend/          # html-js/, vaadin/, flutter/
└── workflows/             # Reusable workflows v1 (en uso por repos actuales)

docs/
├── migration-v2.md        # Guía de referencia completa de CI/CD v2
├── scala-migration-v2.md  # Migración paso a paso para repos Scala
└── workflows-v1.md        # Referencia de workflows v1 (legado, activos hasta marzo 2026)
```

---

## Uso rápido — CI/CD v2

Las actions se referencian desde los workflows de cada proyecto usando el tag `@v2`:

```yaml
# Verificar label obligatorio en PR
- uses: BQN-UY/CI-CD/.github/actions/shared/label-check@v2
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}

# Scan de seguridad (OpenGrep SAST + BetterLeaks)
- uses: BQN-UY/CI-CD/.github/actions/shared/security-scan@v2

# Calcular y crear tag SemVer
- uses: BQN-UY/CI-CD/.github/actions/shared/semver-tag@v2
  with:
    bump: minor   # major | minor | patch

# Back-merge entre ramas
- uses: BQN-UY/CI-CD/.github/actions/shared/git-merge@v2
  with:
    source: main
    target: develop

# Crear GitHub Release con notas autogeneradas
- uses: BQN-UY/CI-CD/.github/actions/shared/github-release@v2
  with:
    tag: ${{ steps.tag.outputs.tag }}

# Disparar deploy vía webhook
- uses: BQN-UY/CI-CD/.github/actions/shared/deploy-trigger@v2
  with:
    environment: production
    service-url: ${{ secrets.DEPLOY_WEBHOOK_URL }}
    token: ${{ secrets.DEPLOY_TOKEN }}
```

### Actions de stack

| Stack | Action |
|---|---|
| Backend Scala/Pekko | `BQN-UY/CI-CD/.github/actions/backend/scala/lint-build@v2` |
| Backend Python/FastAPI | `BQN-UY/CI-CD/.github/actions/backend/python/lint-test@v2` |
| Backend Node.js | `BQN-UY/CI-CD/.github/actions/backend/node/lint-test@v2` |
| Frontend HTML+JS | `BQN-UY/CI-CD/.github/actions/frontend/html-js/lint-build@v2` |
| Frontend Vaadin | `BQN-UY/CI-CD/.github/actions/frontend/vaadin/lint-build@v2` |
| Frontend Flutter | `BQN-UY/CI-CD/.github/actions/frontend/flutter/lint-test@v2` |

---

## Permisos requeridos

Los workflows que usen `semver-tag`, `git-merge` o `github-release` deben declarar:

```yaml
permissions:
  contents: write          # crear tags y push de ramas
  security-events: write   # subir SARIF al tab de Security (security-scan)
```

---

## Documentación

| Documento | Descripción |
|---|---|
| [`docs/migration-v2.md`](docs/migration-v2.md) | Guía de referencia completa: estructura, todas las actions, stacks soportados, roles y convenciones |
| [`docs/scala-migration-v2.md`](docs/scala-migration-v2.md) | Guía paso a paso para migrar repos Scala de `version.sbt` + sbt-release a `sbt-dynver` + Git tags |
| [`docs/workflows-v1.md`](docs/workflows-v1.md) | Referencia de los workflows v1 en `.github/workflows/` (activos, consumidos por repos que aún no migraron a v2) |

---

## Workflows v1 (legado)

Los workflows en `.github/workflows/` son de tipo `workflow_call` y siguen activos. Son referenciados desde los repos de proyecto como:

```yaml
uses: BQN-UY/CI-CD/.github/workflows/<nombre>.yml@main
```

| Workflow | Descripción |
|---|---|
| `scala-ci.yml` | CI para proyectos Scala: labeling, unit tests, auto-merge de PRs `update/*` |
| `scala-deploy-jar.yml` | Build (`sbt assembly`) y deploy de fat JAR vía rsync + Jenkins |
| `scala-deploy-web.yml` | Build (`sbt package`) y deploy de WAR vía rsync + Jenkins |
| `scala-make-release-jar.yml` | Release completo de JAR: `sbt release`, push de tags, rsync, Jenkins. Soporta hotfix |
| `scala-make-release-web.yml` | Release completo de WAR: mismo flujo que la versión JAR |
| `scala-make-release-lib.yml` | Release de librería Scala publicada en Nexus, con detección de cambios |
| `scala-publish-snapshot-lib.yml` | Publica snapshot de librería en Nexus (`sbt publish`) |
| `start-hotfix.yml` | Crea rama de hotfix desde un tag existente e incrementa el patch version |
| `merge-update.yml` | Labeling y auto-merge de PRs de ramas `update/*` de Dependabot/bqn-sysadmin |
| `release-drafter.yml` | Genera borrador de release notes leyendo la versión desde `version.sbt` |
| `remove-old-artifacts.yml` | Limpia artifacts antiguos de GitHub Actions |

Ver detalles completos en [`docs/workflows-v1.md`](docs/workflows-v1.md).

---

## Agregar un nuevo stack

1. Decidir la capa: `frontend/` o `backend/`
2. Crear la carpeta: `.github/actions/backend/go/lint-test/`
3. Escribir el `action.yml` usando como plantilla cualquier action existente del mismo tipo
4. Abrir PR en este repo con label `feature`

> Agregar un stack nuevo no afecta ningún repo existente — el aislamiento está garantizado por la estructura de carpetas.

---

## Gestión

Repositorio gestionado por el equipo de DevOps · `@pablo-zebraitis`
