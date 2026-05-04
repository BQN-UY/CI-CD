# `.github/deploy.json` — schema y convenciones

Config de deploy descentralizada de v2. Reemplaza al `sistemas.json` centralizado de v1. Cada repo de server app declara su propia config, versionada con el código.

- **Schema JSON**: [`schemas/deploy.schema.json`](../schemas/deploy.schema.json)
- **Decisión y motivación**: ver `docs/v2-hito2-deploy-spec.md` §4.9 y §4.10
- **Consumido por**: reusable workflow `scala-api-deploy.yml` (incluido en este PR / Hito 3 en curso, [#89](https://github.com/BQN-UY/CI-CD/pull/89))
- **Inventario global**: generado semanalmente por workflow cron en CI-CD repo (`scripts/build-inventory.py` — alineación con este schema en track separado)

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
environments (obj, requerido, ≥1 ambiente)
 └── testing | staging | production
      └── installations[] (array, requerido, ≥1)
           ├── name                 (str, requerido, único en el ambiente)
           ├── portainer_endpoint   (str, requerido)
           ├── portainer_stack      (str, requerido — compose project)
           ├── portainer_service    (str, requerido — compose service)
           ├── portainer_replica    (int, opcional, default 1)
           ├── executable_path      (str, requerido, path absoluto dentro del container)
           └── auto_deploy          (bool, opcional, default false)
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
- Validación de coherencia: el schema rechaza combinaciones inválidas (`scala-api` con `executable_path` terminado en `.war`, o `scala-vaadin` terminado en `.jar`).
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
          "portainer_stack": "acp_services",
          "portainer_service": "acp-api",
          "executable_path": "/app/lib/acp-api.jar",
          "auto_deploy": true
        }
      ]
    },
    "staging": {
      "installations": [
        {
          "name": "acp-api_staging",
          "portainer_endpoint": "docker-staging",
          "portainer_stack": "acp_services",
          "portainer_service": "acp-api",
          "executable_path": "/app/lib/acp-api.jar",
          "auto_deploy": true
        }
      ]
    },
    "production": {
      "installations": [
        {
          "name": "acp-api_crl",
          "portainer_endpoint": "docker-prod-01",
          "portainer_stack": "acp_crl",
          "portainer_service": "acp-api",
          "executable_path": "/app/lib/acp-api.jar",
          "auto_deploy": false
        },
        {
          "name": "acp-api_lpi",
          "portainer_endpoint": "docker-prod-01",
          "portainer_stack": "acp_lpi",
          "portainer_service": "acp-api",
          "executable_path": "/app/lib/acp-api.jar",
          "auto_deploy": false
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
| `installations[].name` | Identificador de la instalación dentro del ambiente. Único. Se ingresa como string en el input `installations` del `workflow_dispatch` (uno o varios separados por coma — el workflow valida que cada nombre exista). Convención: `<sistema>_<variante>`. |
| `portainer_endpoint` | Nombre del endpoint Portainer (PublicURL, no ID). Se resuelve a ID vía `GET /api/endpoints?search=<name>` al momento del deploy. |
| `portainer_stack` | Nombre del compose project — label `com.docker.compose.project` del container. Junto con `portainer_service` + `portainer_replica` resuelve el container ID por labels (C2 — robusto frente a renames del container). |
| `portainer_service` | Nombre del servicio compose — label `com.docker.compose.service` del container. |
| `portainer_replica` | Número de réplica — label `com.docker.compose.container-number`. Default `1`. Para servicios escalados (≥2 réplicas), declarar una instalación por réplica. |
| `executable_path` | Path absoluto del artefacto **dentro del container** (ej. `/app/lib/acp-api.jar`). El directorio padre debe existir; el archivo se PUT'a vía Portainer `/archive` con el basename de este path. La extensión se valida cruzada con `application_type` (regex `\.jar$` para `scala-api`, `\.war$` para `scala-vaadin`). |
| `auto_deploy` | Si `true`, la instalación se incluye cuando el deploy se dispara sin selección manual (push → deploy automático a testing/staging). Si `false` u omitido, solo se deploya si se selecciona explícitamente (típico para production). |

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

v2 cambió la identificación de container (de nombre frágil a labels de compose) y unificó `artifact.{deploy_path,extension,target_name}` en un único `executable_path`. La migración no es campo-a-campo: requiere consultar las labels de compose del container existente.

Para migrar un app de v1 a v2:

1. **Localizar** la entrada del app en `BQN-UY/jenkins/config/sistemas.json` (por `apps[].name`).
2. **Para cada installation v1**, consultar las labels de compose del container actual (autenticado con un token Portainer con read-only):
   ```bash
   curl -sS --insecure \
     -H "X-API-KEY: $PORTAINER_TOKEN" \
     "$PORTAINER_URL/api/endpoints/$ENDPOINT_ID/docker/containers/$CONTAINER_NAME/json" \
     | jq '.Config.Labels | {
         project: ."com.docker.compose.project",
         service: ."com.docker.compose.service",
         number:  ."com.docker.compose.container-number"
       }'
   ```
3. **Transformar** al schema v2:
   - Quitar el wrapper `apps[]` — el repo _es_ el app.
   - **Agregar** `application_type` al tope (según el stack del repo).
   - Cambiar `environments[]` (array con `name` interno) por `environments` (objeto con keys `testing` / `staging` / `production`).
   - Reemplazar `portainer_container` por la triple `portainer_stack` / `portainer_service` / `portainer_replica` (`compose.project` / `compose.service` / `compose.container-number` extraídos en el paso 2).
   - Reemplazar `artifact.{deploy_path, extension, target_name}` por un único `executable_path`. Si en v1 el artefacto se copiaba a `${deploy_path}/${target_name|name}.${extension}` (path en el host bind-mounted), en v2 el `executable_path` debe ser ese mismo path **tal cual lo ve el container** (típicamente coincide cuando el bind-mount es idéntico; verificar con `docker inspect` si la ruta dentro del container difiere).
   - **Descartar** el campo `database.{name,servedata_server}`: pertenece al flujo de restore DB, que se aborda en su propio hito (fuera de scope Hito 2).
4. **Agregar** `$schema` al inicio para habilitar validación.
5. **Commit** del `.github/deploy.json` junto con el PR de migración del app a v2.

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
              "artifact": { "deploy_path": "/opt/webapps", "extension": "war", "target_name": "ROOT" },
              "database": { "name": "sga_crl", "servedata_server": "servedata-testing" }
            }
          ]
        }
      ]
    }
  ]
}
```

Asumiendo que `docker inspect sga_testing` devuelve labels `compose.project=sga_services`, `compose.service=sga`, `compose.container-number=1`, y que el bind-mount monta `/opt/webapps` del host en `/opt/webapps` del container:

v2 (`.github/deploy.json` en el repo `sga`):

```json
{
  "$schema": "https://raw.githubusercontent.com/BQN-UY/CI-CD/v2/schemas/deploy.schema.json",
  "application_type": "scala-vaadin",
  "environments": {
    "testing": {
      "installations": [
        {
          "name": "sga_testing",
          "portainer_endpoint": "docker-testing",
          "portainer_stack": "sga_services",
          "portainer_service": "sga",
          "executable_path": "/opt/webapps/ROOT.war",
          "auto_deploy": true
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
