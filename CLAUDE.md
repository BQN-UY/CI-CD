# BQN-UY/CI-CD — Contexto para AI

Repositorio centralizado de CI/CD de la organización BQN-UY.
Contiene las composite actions reutilizables (v2) y los reusable workflows heredados (v1).

## Estructura del repo

```
.github/
├── actions/          ← composite actions v2  — MODIFICAR AQUÍ
│   ├── shared/       ← lógica agnóstica de stack (jenkins-deploy-trigger, semver-tag, etc.)
│   ├── frontend/     ← acciones por stack frontend (html-js, vaadin, flutter)
│   └── backend/      ← acciones por stack backend (scala, python, node)
└── workflows/        ← reusable workflows v1  — NO MODIFICAR (legacy)

templates/            ← workflows listos para copiar en repos de proyecto
docs/                 ← documentación de referencia v2
```

## Reglas

- Modificar normalmente solo `.github/actions/`, `templates/` y `docs/`
- Excepciones permitidas en raíz y `.github/`: `CLAUDE.md`, `.github/copilot-instructions.md` y archivos de configuración del repo
- NUNCA modificar `.github/workflows/` — son workflows v1 legacy, no se migran
- Los workflows de cada proyecto NO viven aquí — viven en el repo del proyecto
- Toda nueva action v2 va en `.github/actions/<capa>/<stack>/<nombre>/action.yml`

## Ambientes válidos (`shared/jenkins-deploy-trigger`)

`testing` | `staging` | `production`

## Semántica de ambientes

| Rama del proyecto | Ambiente | Propósito |
|---|---|---|
| `develop` | testing | Features de la próxima versión |
| `release/**` | testing | Fixes del release en curso |
| `hotfix/**` | staging | Fix urgente — espejo de producción |
| `make-release` | production | Único deploy irreversible |

## Cómo agregar una nueva action v2

1. Decidir capa: ¿`shared/`, `frontend/<stack>/` o `backend/<stack>/`?
2. Crear `action.yml` en la carpeta correspondiente
3. Agregar el template de workflow en `templates/<stack>/`
4. Documentar en `docs/migration-v2.md`

## Referencia

- Documentación completa: `docs/migration-v2.md`
- Guía de migración Scala: `docs/scala-migration-v2.md`
- Workflows v1 (legacy): `docs/workflows-v1.md`
