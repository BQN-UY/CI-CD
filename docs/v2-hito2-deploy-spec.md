# Hito 2 — Spec del deploy GA-native (borrador)

> Estado: **borrador para discusión** · Tracking: `docs/v2-sin-jenkins-roadmap.md` Hito 2

Documento para alinear el diseño del workflow de deploy GA-native que reemplaza a Jenkins en v2.
Contiene: requisitos heredados de v1, decisiones de diseño abiertas, y criterios de aceptación.

## Principio rector

**v2 no depende de `BQN-UY/jenkins` para nada.** Ese repo (incluyendo su rama `production`, los scripts groovy, `sistemas.json`, etc.) es legacy de v1 y queda congelado. v2 lee la lógica de v1 sólo como referencia para entender requisitos — pero ningún workflow ni runner GA invoca, importa o lee archivos de ese repo.

---

## 1. Baseline — qué hace el deploy v1 (Jenkins)

Resumen de `~/projects/bqn/jenkins/CI_CD/deploy-nexus.groovy` (319 líneas, pipeline declarativo).
**Esta sección es descriptiva** — captura qué requisitos hay que cubrir en v2. v2 NO lee, ejecuta, ni invoca código del repo `BQN-UY/jenkins` (ver Principio rector).

**Inputs** (por webhook GWT desde GitHub Actions):
- `SISTEMA` — nombre del sistema, debe coincidir con `sistemas.json`
- `VERSION` — sbt-dynver (snapshot o release) o tag explícito
- `ENVIRONMENT` — `testing` | `staging` | `production`
- `ACTOR` — github actor que disparó el deploy
- `INSTALLATION` — coma-separado, vacío = todas las que tengan `auto_deploy: true`
- `RESTORE` — bool, restaurar DB antes (solo testing/staging)

**Flujo:**
1. Carga `sistemas.json` desde `BQN-UY/jenkins/config/sistemas.json` (PAT GitHub).
2. Resuelve `installations` para el `(sistema, environment)` solicitado.
3. Notifica inicio a Google Chat (webhook).
4. Si production → `input` manual con submitter restringido (`admins,soporte,auxiliar_soporte`).
5. Si `RESTORE` y no production → invoca `IDS/restoreDB`.
6. **Por cada instalación, en paralelo:**
   - Resuelve URL exacta del artefacto en Nexus vía Search API (necesario por el sufijo Scala `_2.13` y el timestamp Maven en snapshots).
   - Se conecta al **endpoint Portainer** correspondiente (cada instalación tiene su `portainer_endpoint` y `portainer_container`).
   - Stop container.
   - Descarga JAR/WAR desde Nexus a `localFile`.
   - Copia a `deploy_path/target_name` (default `/opt/webapps`).
   - Start container.
7. Registra el deploy en `deploy-registry` (success/failure por instalación).
8. Notifica fin a Google Chat.

**Dependencias técnicas:**
- Portainer API (token `portainer_jenkins_token`).
- Nexus (credenciales `nexus_deploy`).
- `sistemas.json` con schema: `apps[].environments[].installations[]` con `name`, `portainer_endpoint`, `portainer_container`, `artifact.{extension, deploy_path, target_name}`, `auto_deploy`.
- Google Chat webhook por ambiente.
- Jenkins agents en cada `portainer_endpoint` (el `cp` corre **localmente en el host destino**, no remoto — por eso se usa `node(pEndpoint)`).
- `deploy-registry` (servicio interno).
- `IDS/restoreDB` (job Jenkins separado).

---

## 2. Decisiones de diseño abiertas

### 2.1 Self-hosted runner GA — ¿dónde y cuántos?

El runner GA reemplaza al "Jenkins agent" del modelo v1. Necesita:
- Acceso de red a Portainer (todos los endpoints), Nexus, NAS2, DBs.
- Capacidad de ejecutar `curl` + `cp` (mínimo).
- Token efímero a GitHub (auto-gestionado por el runner).

| Opción | Pros | Contras |
|---|---|---|
| **A. Un runner único** en `DEPLOY_IP` | Mínimo a operar; ya está en red interna (acceso a todo) | SPOF; el `cp` al host destino debe ser **remoto** (SSH), no local — distinto al modelo v1 |
| **B. Un runner por endpoint Portainer** (espejo de Jenkins agents) | `cp` local al host (igual que v1); paraleliza naturalmente | N runners a instalar/mantener (~5-10); más superficie de ataque |
| **C. Runners "labeled"** (subset estratégico, ej. uno por DC físico) | Equilibrio: paralelismo + menos superficie | Diseñar el labeling y el routing del job; complejidad media |

> **Pregunta para Soporte/IDS**: ¿cuántos `portainer_endpoint` distintos hay hoy en `sistemas.json`?
> ¿Están en el mismo DC? Si sí, A simplifica mucho. Si están distribuidos geográficamente, C es la respuesta natural.

### 2.2 Mecanismo de deploy — ¿cómo llegamos al artefacto en el container?

Tres caminos limpios:

| Opción | Cómo funciona | Encaja si |
|---|---|---|
| **α. Portainer API** (HTTP + token) | El runner llama a Portainer para `stop` → reemplaza imagen/volumen → `start`. El artefacto se monta vía volumen Docker o se incluye en una imagen recreada. | Los containers están totalmente bajo Portainer y se pueden rebuilds/recreate por API |
| **β. SSH + `docker pull && restart`** | El runner SSH al host, hace `docker pull` (si la imagen es la unidad) o `cp + docker restart` (si el artefacto es un archivo montado). | Hosts tienen Docker + acceso SSH desde el runner |
| **γ. SCP + systemd** | El runner copia el JAR vía SCP, hace `systemctl restart <servicio>`. Sin Docker. | Servicios corren como units systemd directamente, sin containers |

**Importante**: v1 usa una **mezcla de α y β**: API de Portainer para start/stop + `cp` local del archivo (porque el agent corre en el host). El equivalente GA-native más cercano sería **β** (runner único, SSH al host, `docker stop && cp && docker start`) o **A+α** (runner único, todo via API de Portainer si el modelo de containers lo soporta).

> **Pregunta para Soporte/IDS**: ¿los services corren todos containerizados via Portainer?
> ¿El JAR/WAR se monta como volumen o está dentro de la imagen?
> Si es volumen → β o "A+API+volumen". Si está en la imagen → α (rebuild via Portainer).

### 2.3 Modelo de "instalaciones" — ¿dónde vive el config?

Por el principio rector, v2 **no** lee `sistemas.json` de `BQN-UY/jenkins`. Necesita su propia fuente de verdad. Tres caminos:

| Opción | Implicancia |
|---|---|
| **A. `sistemas.json` en `BQN-UY/CI-CD`** | Single source para v2; el runner lo lee del mismo repo donde están los workflows (cero PATs cruzados). v1 sigue con su copia en `BQN-UY/jenkins` — divergen pero no se mezclan. Bueno si necesitamos vista global de instalaciones. |
| **B. Config por proyecto** (`.github/deploy.json` o `.github/deploy.yml` en cada repo) | El repo dueño del servicio declara sus instalaciones. Descentralizado, cero registro central. Cada equipo gestiona el mapping de sus propios services. Pierde vista global pero ningún proyecto depende de otro. |
| **C. GitHub Environments** + variables/secrets | Cada `environment` (testing/staging/production) en cada repo lleva sus `vars.PORTAINER_ENDPOINT`, `vars.DEPLOY_PATH`, `secrets.PORTAINER_TOKEN`, etc. Cero JSON, todo en GH UI. Native + auditado por GitHub. |

**Recomendación inicial**: **B + C combinados**.
- `.github/deploy.json` (o `.yml`) en cada repo → estructura: lista de instalaciones por environment, `portainer_endpoint`, `portainer_container`, `deploy_path`, `target_name`, `auto_deploy`. Versionado con el código.
- GH Environments → secretos/tokens/URLs sensibles por ambiente. Required reviewers para production.

Ventaja: ningún acoplamiento a un repo central, cero PATs cruzados, cada equipo dueño de su propio mapping. La vista global se obtiene a demanda con un script que escanee los repos via GitHub API (no es necesario tenerla pre-agregada).

---

## 3. Otras decisiones secundarias

### 3.1 Aprobación de production
- **GitHub Environments** ya provee aprobación manual (required reviewers). Mapea 1:1 al `input` de Jenkins.
- **Pregunta**: ¿conservamos los submitters actuales (`admins,soporte,auxiliar_soporte`) como required reviewers en GH Environments?

### 3.2 Notificaciones
- v1 usa Google Chat. ¿Mantenemos? Alternativas: comentario en commit/PR, GitHub Discussions, Slack.
- **Recomendación**: mantener Google Chat por continuidad.

### 3.3 Registro de deploys
- v1 escribe a un servicio interno (`deploy-registry`). Por el principio rector, v2 no lo invoca.
- **Recomendación**: usar **GitHub Deployments API** (nativo) — cada deploy GA-native crea un Deployment en el repo del proyecto con env, ref y status. Auditable, queryable, sin servicio nuevo.
- Si se requiere agregación entre repos, un dashboard externo puede leer la API de cada repo. Fuera de scope inicial.

### 3.4 Resolución de URL en Nexus
- v1 usa Nexus Search API (no asume el path) por dos razones: artifact ID con sufijo Scala `_2.13`, y timestamp Maven en snapshots.
- **Decisión de Hito 1 + acp-api#8**: con `dynverSeparator := "-"` los paths son predecibles. ¿Sigue siendo necesaria la Search API o podemos asumir paths directos?

### 3.5 Restore DB
- v1 invoca `IDS/restoreDB`. ¿Migrar también a GA workflow_dispatch o queda fuera de Hito 2?
- **Recomendación**: fuera de Hito 2; se aborda en su propio hito (parte de "operativos en GA" del informe Jenkins, §10 Fase 3).

---

## 4. Criterios de aceptación del spec

El spec se considera completo cuando responde:

- [ ] (2.1) Cantidad y ubicación de runners GA + plan de instalación
- [ ] (2.2) Mecanismo elegido (α/β/γ) + ejemplo end-to-end con un sistema real
- [ ] (2.3) Ubicación de `sistemas.json` + schema actualizado si cambia
- [ ] (3.1) Required reviewers de GH Environments definidos por env
- [ ] (3.2) Notificaciones: canal y formato
- [ ] (3.3) Registro de deploys: API y/o servicio
- [ ] (3.4) Resolución de URL Nexus: directa vs Search API
- [ ] Lista de secrets nuevos requeridos por el runner (Portainer, SSH keys, etc.)
- [ ] Diseño del nuevo composite `shared/deploy-*` y reusable workflow `scala-api-deploy.yml`
- [ ] Criterio de migración de proyectos: cómo se mueve un repo v2 publish-only a v2 con deploy GA-native (PR mecánico)

Cuando el spec esté completo y aprobado → arranca Hito 3 (implementación).

---

## 5. Próximos pasos

1. Compartir este borrador con Soporte/IDS para responder las preguntas de §2 y §3.
2. Cuando estén las respuestas, actualizar este doc → consolidar en versión definitiva.
3. Spinoff: PR en `BQN-UY/CI-CD` con el spec definitivo + ADR si corresponde.
4. Habilitar Hito 3.
