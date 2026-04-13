# CI/CD v2 — Contexto para AI

Este proyecto usa CI/CD v2 de BQN-UY. La lógica de CI/CD vive en `BQN-UY/CI-CD`
como **reusable workflows** (`.github/workflows/scala-api-*.yml`) que internamente
componen las composite actions del repo. Los workflows de este proyecto son
**callers cortos** que apuntan al reusable workflow correspondiente con `@v2`.

Esto significa que cualquier cambio en la lógica de CI/CD se hace una sola vez
en `BQN-UY/CI-CD` y se propaga automáticamente a todos los proyectos que pinean
`@v2`. Los archivos `.github/workflows/*.yml` de este repo solo cambian cuando
hay que ajustar inputs o triggers específicos del proyecto.

## Branching model

### Ramas de trabajo (corta duración — siempre via PR)

| Rama | Sale de | Merge hacia | Label PR | Cuándo usar |
|---|---|---|---|---|
| `feature/*` | `develop` | `develop` | `feature` | Nueva funcionalidad retrocompatible |
| `fix/*` | `develop` · `release/**` · `hotfix/**` | mismo origen | `fix` | Corrección de bug |
| `chore/*` | `develop` | `develop` | `chore` | Mantenimiento: configuración, CI, tests |
| `docs/*` | `develop` | `develop` | `chore` | Documentación |
| `refactor/*` | `develop` | `develop` | `chore` | Refactoring sin cambio de comportamiento |
| `dependabot/*` | `develop` | `develop` | `update` | Actualización de dependencias (Dependabot) |
| `scala-steward/*` | `develop` | `develop` | `update` | Actualización de dependencias (Scala Steward) |

> `fix/*` es el único tipo que puede salir de una rama distinta a `develop`.
> Un `fix/*` desde `release/**` corrige un bug detectado durante el testeo del RC.
> Un `fix/*` desde `hotfix/**` corrige un bug secundario descubierto dentro del hotfix.
>
> `dependabot/*` y `scala-steward/*` son creadas automáticamente por las herramientas — no crearlas manualmente.
> `auto-label` les asigna `update` automáticamente; Dependabot también se configura con `labels: ["update"]` en `.github/dependabot.yml`.

### Ramas de ciclo (larga duración — gestionadas por workflows)

| Rama | Sale de | Cierra con | Propósito |
|---|---|---|---|
| `develop` | — | — | Integración continua de la próxima versión |
| `release/vX.Y.Z` | `develop` via `start-release` | `make-release` → `main` | Estabilización del RC |
| `hotfix/vX.Y.Z-desc` | `main` via `start-hotfix` | `make-release` → `main` | Fix urgente a producción |
| `main` | — | — | Producción |

## Semántica de Nexus por rama

| Rama | Nexus | Propósito |
|---|---|---|
| `develop` | snapshots | Features de la próxima versión |
| `release/**` | snapshots + RC tags | Fixes del release en curso; cada `publish-rc` crea `vX.Y.Z-rc.N` |
| `hotfix/**` | snapshots + RC tags | Fix urgente; mismo modelo de RCs |
| `make-release` | **releases** (`vX.Y.Z`) | Versión final e irreversible |

> **Deploy a ambientes**: en v2 actual, los workflows publican el JAR a Nexus pero **no deployan**. La asociación rama→ambiente (testing/staging/production) y el push a infraestructura se hará vía workflow GA-native cuando esté implementado (ver `docs/v2-sin-jenkins-roadmap.md`, Hito 3).

## Reglas críticas

- `feature/*`, `chore/*`, `docs/*`, `refactor/*` salen **siempre** de `develop` — nunca de `release/**` ni `hotfix/**`
- `fix/*` desde `release/**` → corrige un bug del RC en curso; PR hacia `release/vX.Y.Z`, **NUNCA hacia `develop`**
- `fix/*` desde `hotfix/**` → corrige un bug secundario del hotfix; PR hacia `hotfix/vX.Y.Z-desc`
- `dependabot/*` y `scala-steward/*` apuntan **siempre a `develop`** — nunca a `release/**` ni `hotfix/**`
- `deploy-action` se usa cuando el PR requiere una acción manual en infra antes o durante el deploy (ej. nueva variable de entorno, migración de DB, nuevo secret, nuevo componente de infra). Reemplaza al label de tipo (`feature`, `fix`, etc.) — describir el tipo de cambio en el cuerpo del PR y la acción requerida en la sección "Deploy action requerida"
- `develop` después de `start-release` → próxima versión, no afecta el release en curso
- Los fixes de `release/**` vuelven a `develop` al final via back-merge automático de `make-release`
- `hotfix/**` es exclusivo para fixes urgentes de la versión en producción — no mezclar con features
- `make-release` es irreversible — solo ejecutar cuando el release fue validado en testing

## Workflows

| Archivo | Trigger | Qué hace |
|---|---|---|
| `ci.yml` | PR → develop · push release/\*\* · push hotfix/\*\* | lint + build + security |
| `publish.yml` | push develop · push release/\*\* · push hotfix/\*\* | snapshot Nexus (sin deploy automático — ver `docs/v2-sin-jenkins-roadmap.md`) |
| `start-release.yml` | manual (workflow_dispatch) | crea `release/vX.Y.Z` desde develop |
| `make-release.yml` | manual (workflow_dispatch) | tag + Nexus release + GitHub Release + back-merge (sin deploy production — ver `docs/v2-sin-jenkins-roadmap.md`) |
| `start-hotfix.yml` | manual (workflow_dispatch) | crea `hotfix/vX.Y.Z-desc` desde main |
| `setup-labels.yml` | manual (workflow_dispatch) | crea/sincroniza las labels estándar (tipo + `size/*`) — correr al inicializar el repo |

> Las labels `size/xs..xl` son informativas y las asigna automáticamente `pr-size-label` en cada PR según líneas y archivos modificados. No reemplazan al label de tipo — `label-check` sigue exigiendo exactamente una de `feature` / `fix` / `chore` / `update` / `deploy-action` / `breaking-change`.

## Secrets y variables requeridos

| Secret / Variable | Nivel | Uso |
|---|---|---|
| `NEXUS_USER` / `NEXUS_PASSWORD` / `NEXUS_URL` | repo | Publicar JAR en Nexus |

> **Nota**: en v2 los secrets `JENKINS_DEPLOY_*` y `vars.SISTEMA` ya no aplican — el deploy quedó fuera del scope de los reusable workflows (ver `docs/v2-sin-jenkins-roadmap.md`). Volverán cuando el deploy GA-native esté implementado (Hito 3) o serán reemplazados por nuevos secrets según el mecanismo elegido.

## Convención de configuración

Cada proyecto Scala API mantiene tres `application.conf` con roles bien diferenciados:

### 1. `application.conf` (raíz del proyecto) — configuración Pekko

Relativamente estático. Solo contiene los includes de Pekko y las sobreescrituras del bloque `pekko {}` (loggers, loglevel, actor provider, dispatchers). **No incluye configuración de la aplicación.**

```hocon
# Main application configuration
include "version"                    # Configuraciones de versión (si existen)
include "pekko-reference"            # Configuración base de Pekko
include "pekko-http-core-reference"  # Configuración del núcleo HTTP
include "pekko-http-reference"       # Rutas y extensiones HTTP

pekko {
  loggers = ["org.apache.pekko.event.slf4j.Slf4jLogger"]
  loglevel = "DEBUG"
  ...
}
```

### 2. `docs/application.conf` — configuración de referencia (sin secretos)

Documenta todas las claves que requiere el sistema según su `AppConfig`. Se incluye en el repositorio y es de lectura pública. Incorpora los `reference.conf` del framework (Pekko + framework BQN) con una sola línea. Reglas:

- Empieza con `include "reference"  # Includes all reference.conf settings`
- Solo incluye configuración de la aplicación — no repite el bloque `pekko {}` del raíz
- Reemplaza passwords y tokens con `"••••••••"` — nunca exponer credenciales reales
- Sirve de guía para configurar un ambiente nuevo

### 3. `src/test/resources/application.conf` — configuración de service tests

Usada por los tests de integración HTTP que ejercitan los endpoints de la propia API. Se incluye en el repositorio con valores de testing (no producción). Reglas:

- Empieza con `include "reference"  # Includes all reference.conf settings`
- Contiene la configuración completa del servidor (igual estructura que `docs/application.conf`)
- Agrega el bloque del cliente HTTP de la propia API para que los tests puedan conectarse:

```hocon
# Token de acceso para los service tests.
# Puede ser un token estático de fixed-tokens o un accessToken de bsecurity.
access-token = ""

# Cliente HTTP apuntando al servidor bajo test.
nombre-api {
  url = "http://localhost:8080"
# url = "https://api.testing.banquinet.org/nombre-api"
  connection-timeout            = 3 seconds
  request-timeout               = 10 seconds
  max-connections               = 10
  max-retries                   = 3
  max-open-requests             = 32
  circuit-breaker-max-failures  = 5
  circuit-breaker-reset-timeout = 20 seconds
  check-connection-task {
    enabled       = false
    initial-delay = "1 min"
    interval      = "10 min"
    inactive      = []
  }
  dispatcher {
    type = Dispatcher
    executor = "thread-pool-executor"
    thread-pool-executor { fixed-pool-size = 4 }
    throughput = 1
  }
}
```

La URL local queda activa por defecto; la URL de testing se comenta con `#` para cambiar rápidamente de target sin modificar el archivo.

## Qué NO hacer

- No agregar lógica de build/deploy directamente en los workflows — usar las actions de `BQN-UY/CI-CD`
- No hardcodear versiones de Java — el default (`"21"`) está en `backend/scala/lint-build`
- No usar nombres de secrets distintos a los documentados arriba
- No modificar el branching model — `develop` nunca mergea directo a `main`
- No commitear en `develop` para resolver un issue de un release en curso
