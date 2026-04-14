# `.github/deploy.json` — schema y convenciones

Config de deploy descentralizada de v2. Reemplaza al `sistemas.json` centralizado de v1. Cada repo de server app declara su propia config, versionada con el código.

- **Schema JSON**: [`schemas/deploy.schema.json`](../schemas/deploy.schema.json)
- **Decisión y motivación**: ver `docs/v2-hito2-deploy-spec.md` §4.9 y §4.10
- **Consumido por**: reusable workflow `scala-api-deploy.yml` (pendiente — Hito 3)
- **Inventario global**: generado semanalmente por workflow cron en CI-CD repo (Hito 3)

---

## Referenciar el schema

Incluir `$schema` al inicio del archivo para habilitar validación en editores (VSCode, IntelliJ, etc.):

```json
{
  "$schema": "https://raw.githubusercontent.com/BQN-UY/CI-CD/v2/schemas/deploy.schema.json",
  "application_type": "scala-api",
  "environments": { ... }
}
```

---

## Estructura

```
application_type (str, requerido, enum)
environments (obj, requerido)
 └── testing | staging | production (al menos uno)
      └── installations[] (array, requerido, ≥1)
           ├── name                  (str, requerido, único en el ambiente)
           ├── portainer_endpoint    (str, requerido)
           ├── portainer_container   (str, requerido)
           ├── auto_deploy           (bool, default false)
           └── artifact (obj, requerido)
                ├── deploy_path      (str, requerido, path absoluto)
                ├── extension        (str, requerido, "war" | "jar")
                └── target_name      (str, opcional, default = name)
```

### `application_type` — tipo de aplicación

Declara el stack + forma del artefacto. Alinea con la taxonomía `templates/<stack>-<tipo>/` y los reusable workflows `<stack>-<tipo>-*.yml`. **Requerido**.

| Valor | Stack | Artefacto | Validación de `extension` |
|---|---|---|---|
| `scala-api` | Scala standalone (sbt assembly) | JAR | obligatorio `jar` |
| `scala-vaadin` | Scala + Vaadin en Tomcat | WAR | obligatorio `war` |
| `scala-web` | Scala web (Play, otros) no-Vaadin | JAR o WAR | libre |
| `python-api` | FastAPI / Flask / etc. | TBD | libre (hasta primer caso real) |
| `node-api` | Node API | TBD | libre (hasta primer caso real) |

**Libs NO llevan `deploy.json`** — publican a Nexus, no deploya. El enum solo lista tipos deployables.

**Motivación**:
- Self-describing: el workflow de inventario agrega tipo sin peek-ar al `build.sbt` / `pyproject.toml` de cada repo.
- Validación de coherencia: el schema rechaza combinaciones inválidas (`scala-api` con `extension: war`).
- Defensa en profundidad: el reusable workflow que invoca deploy puede verificar que `application_type` coincide con el suyo, evitando que un repo apunte por error al template equivocado.
- Futuro: agregar un stack nuevo = un valor al enum + un template dedicado. No hay lógica dispersa.

---

## Ejemplo

```json
{
  "$schema": "https://raw.githubusercontent.com/BQN-UY/CI-CD/v2/schemas/deploy.schema.json",
  "application_type": "scala-api",
  "environments": {
    "testing": {
      "installations": [
        {
          "name": "acp-api_testing",
          "portainer_endpoint": "docker-testing",
          "portainer_container": "acp-api_testing",
          "auto_deploy": true,
          "artifact": {
            "deploy_path": "/opt/webapps",
            "extension": "jar"
          }
        }
      ]
    },
    "staging": {
      "installations": [
        {
          "name": "acp-api_staging",
          "portainer_endpoint": "docker-staging",
          "portainer_container": "acp-api_staging",
          "auto_deploy": true,
          "artifact": {
            "deploy_path": "/opt/webapps",
            "extension": "jar"
          }
        }
      ]
    },
    "production": {
      "installations": [
        {
          "name": "acp-api_crl",
          "portainer_endpoint": "docker-prod-01",
          "portainer_container": "acp-api_crl",
          "auto_deploy": true,
          "artifact": {
            "deploy_path": "/opt/webapps",
            "extension": "jar",
            "target_name": "acp-api"
          }
        },
        {
          "name": "acp-api_lpi",
          "portainer_endpoint": "docker-prod-01",
          "portainer_container": "acp-api_lpi",
          "auto_deploy": true,
          "artifact": {
            "deploy_path": "/opt/webapps",
            "extension": "jar",
            "target_name": "acp-api"
          }
        }
      ]
    }
  }
}
```

---

## Semántica de campos

| Campo | Descripción |
|---|---|
| `environments.<env>` | Uno de `testing`, `staging`, `production`. Solo se definen los ambientes en los que la app deploya. |
| `installations[].name` | Identificador de la instalación dentro del ambiente. Único. Se usa como valor en el dropdown de deploy manual (`workflow_dispatch`). Convención: `<sistema>_<variante>`. |
| `portainer_endpoint` | Nombre del endpoint Portainer (no ID). Se resuelve a ID vía `GET /api/endpoints?search=<name>` al momento del deploy. |
| `portainer_container` | Nombre del container en ese endpoint. Se resuelve a ID vía `GET /api/endpoints/{id}/docker/containers/json?filters=...`. |
| `auto_deploy` | Si `true`, la instalación se incluye cuando el deploy se dispara sin selección manual (push → deploy automático a testing/staging). Si `false` u omitido, solo se deploya si se selecciona explícitamente (típico para production). |
| `artifact.deploy_path` | Path absoluto en el host donde copiar el archivo (montado como bind-mount al container). Convención actual en BQN: `/opt/webapps`. |
| `artifact.extension` | `war` (servlet en Tomcat) o `jar` (standalone). |
| `artifact.target_name` | Nombre con que se renombra el archivo al copiarlo (sin extensión). Si se omite, se usa `installations[].name`. Útil cuando el container espera un nombre fijo (ej. Tomcat espera `ROOT.war`) distinto al nombre lógico de la instalación. |

---

## Mapping desde `sistemas.json` v1

La estructura de v1 era:

```json
{
  "apps": [
    { "name": "<sistema>", "environments": [ { "name": "<env>", "installations": [ ... ] } ] }
  ]
}
```

Para migrar un app de v1 a v2:

1. **Localizar** la entrada del app en `BQN-UY/jenkins/config/sistemas.json` (por `apps[].name`).
2. **Transformar** al schema v2:
   - Quitar el wrapper `apps[]` — el repo _es_ el app.
   - **Agregar** `application_type` al tope (según el stack del repo).
   - Cambiar `environments[]` (array con `name` interno) por `environments` (objeto con keys `testing` / `staging` / `production`).
   - Copiar cada installation tal cual (los campos coinciden: `name`, `portainer_endpoint`, `portainer_container`, `auto_deploy`, `artifact.{deploy_path,extension,target_name}`).
   - **Descartar** el campo `database.{name,servedata_server}`: pertenece al flujo de restore DB, que se aborda en su propio hito (fuera de scope Hito 2).
3. **Agregar** `$schema` al inicio para habilitar validación.
4. **Commit** del `.github/deploy.json` junto con el PR de migración del app a v2.

### Ejemplo de transformación

v1 (fragmento de `sistemas.json`):

```json
{
  "apps": [
    {
      "name": "sga",
      "environments": [
        {
          "name": "testing",
          "installations": [
            {
              "name": "sga_testing",
              "portainer_endpoint": "docker-testing",
              "portainer_container": "sga_testing",
              "auto_deploy": true,
              "artifact": { "deploy_path": "/opt/webapps", "extension": "war" },
              "database": { "name": "sga_crl", "servedata_server": "servedata-testing" }
            }
          ]
        }
      ]
    }
  ]
}
```

v2 (`.github/deploy.json` en el repo `sga`):

```json
{
  "$schema": "https://raw.githubusercontent.com/BQN-UY/CI-CD/v2/schemas/deploy.schema.json",
  "application_type": "scala-api",
  "environments": {
    "testing": {
      "installations": [
        {
          "name": "sga_testing",
          "portainer_endpoint": "docker-testing",
          "portainer_container": "sga_testing",
          "auto_deploy": true,
          "artifact": { "deploy_path": "/opt/webapps", "extension": "war" }
        }
      ]
    }
  }
}
```

---

## Validación local

Con cualquier validador de JSON Schema 2020-12. Ejemplo con [`ajv-cli`](https://github.com/ajv-validator/ajv-cli):

```bash
npx ajv-cli validate \
  -s schemas/deploy.schema.json \
  -d .github/deploy.json \
  --spec=draft2020 --strict=false
```

> El workflow de inventario (§4.10) correrá esta validación contra todos los repos de la org y reportará errores en el inventario agregado.

---

## Campos fuera de scope del Hito 2

Estos campos existían en `sistemas.json` v1 y **no se incluyen** en el schema v2 por ahora. Si se vuelven necesarios, se agregan en hitos propios:

- `database.name`, `database.servedata_server` → Hito de restore DB.
- Configuración de redes macvlan, env vars del container, health checks → provisioning, gestionado directamente en Portainer (stacks), no en el deploy de versión.
