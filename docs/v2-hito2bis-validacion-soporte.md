# v2 sin Jenkins — Validación con Soporte

> Documento corto para validar supuestos antes de diseñar la solución completa. Foco: deploy de **server apps** (APIs scala, WARs, python servers). Fuera de scope: client apps, libs, restore DB.

---

## 1. Supuestos a validar (checklist)

Marcar ✅ / ❌ / 🟡 (parcial, con nota).

### Sobre la infraestructura actual

- [ ] Todos los hosts donde corren server apps están en la **misma LAN** (sin sitios remotos / cross-DC).
- [ ] Todos los containers de server apps están **gestionados por Portainer** (endpoint `https://docker-soporte:9443`).
- [ ] Los containers se identifican por **nombre** (no por ID dinámico) y ese nombre es estable entre re-deploys.
- [ ] Las redes macvlan / IP fija / environments de containers se configuran **al crear la app** (provisioning) y **no cambian en cada deploy de versión**.

### Sobre el deploy de versión nueva (lo que queremos reemplazar)

- [ ] El deploy de una versión nueva consiste en: **reemplazar el archivo** (`.war`/`.jar`) en el path montado + **restart del container**. No se hace rebuild de imagen, no se redeploya el stack.
- [ ] El archivo `sistemas.json` (repo `BQN-UY/jenkins`) es la **única** fuente de verdad del mapping `sistema → ambiente → (endpoint Portainer, nombre container, path destino, nombre archivo)`.
- [ ] Hoy el agente Jenkins que ejecuta el deploy está labeled con el nombre del endpoint Portainer (`node("${container_parent}")`), y tiene **acceso FS directo** al `executable_path` del container (bind mount al host o NAS compartido) — no usa SSH.
- [ ] Jenkins usa el endpoint FTP (`SISTEMAS_PATH`) para bajar el artefacto desde NAS2 al workspace del agente, y después hace `cp` local.
- [ ] El token `portainer_jenkins_token` tiene permisos sobre **todos** los endpoints Portainer relevantes (no está scoped por endpoint).

### Sobre ambientes y aprobaciones

- [ ] Testing y staging → auto-deploy al publicarse una versión nueva (snapshot/RC).
- [ ] Production → deploy manual con aprobación humana (hoy: submitters `admins, soporte, auxiliar_soporte`).
- [ ] Las notificaciones a Google Chat (inicio / fin / confirmación producción) son requisito que se debe mantener.

> Si alguno de los checkboxes es ❌ o 🟡, anotar al lado el detalle — eso nos cambia el diseño.

---

## 2. Qué cambia al sustituir Jenkins por GitHub Actions (v1 → v2)

### 2.1 Qué se sustituye (sale de la infra BQN)

| v1 (hoy) | v2 (futuro) |
|---|---|
| **Jenkins** (`https://jenkins.bqn.uy`) como orquestador de deploys | **GitHub Actions** (cloud de GitHub) orquesta; un runner self-hosted en la LAN ejecuta |
| **Nexus** (`maven-snapshots`, `maven-releases`) como storage de artefactos de apps | **GitHub Releases** del propio repo de cada app (Nexus se mantiene **solo para libs**) |
| **NAS2 + FTP** como intermediario para bajar artefactos (`SISTEMAS_PATH/versiones/*.war`) | El runner GA descarga directo desde GitHub Releases con `gh release download` — **no pasa por FTP/NAS2** |
| **`sistemas.json`** en repo `BQN-UY/jenkins` (centralizado, groovy) | **`.github/deploy.json`** en cada repo de app (descentralizado, versionado con el código) |
| **Active Choice dropdowns** en Jenkins para elegir sistema/instalación/versión | **`workflow_dispatch`** en GitHub Actions con inputs equivalentes |
| **Aprobación producción** en Jenkins (`input` stage con submitter restringido) | **GitHub Environments** con `required reviewers` (team de GitHub) |
| **Registro de deploys** en Jenkins (`registerDeploy.groovy`, `deploy-log.jsonl`) | **GitHub Deployments API** (nativo, sin servicio nuevo) |

### 2.2 Qué se mantiene (no cambia)

- **Portainer** sigue gestionando los containers — misma URL, mismo token (o uno equivalente para el runner).
- **Google Chat** sigue siendo el canal de notificaciones.
- **Redes macvlan, IP fija, stacks, environments de containers**: provisioning sigue igual, no lo toca el deploy de versión.
- **Nexus** se mantiene **solo para libs** (protocolos comunes, scala libs que otras apps resuelven).

### 2.3 Qué se agrega (nuevo en la infra BQN)

Requerimientos **nuevos** que Soporte necesita prever:

1. **Runner self-hosted de GitHub Actions** — un host Linux en la LAN, registrado a nivel organización BQN-UY, corre el agente de GA como servicio systemd. Equivalente funcional al agente Jenkins que hace el deploy hoy.
   - **A confirmar**: si el modelo es **un runner por host** (espejo de los agentes Jenkins labeled actuales) o **un runner único** con acceso a todos los mounts. Depende de la topología actual de mounts/NAS.
2. **Credenciales del runner**:
   - Token Portainer (el actual u otro nuevo con scope equivalente).
   - Acceso FS a los `executable_path` de cada container (heredado del modelo actual — mismo mount).
   - Webhook URL de Google Chat (equivale al secret `DEPLOY_APP_WEBHOOK` actual).
3. **Ningún cambio en Portainer, stacks, redes o hosts productivos** — el runner reemplaza al agente Jenkins; la infraestructura Docker queda intacta.

---

## 3. Preguntas abiertas para resolver después de la validación

> Estas no bloquean la validación de arriba; se resuelven en la reunión de diseño.

1. **¿Uno o varios runners?** — depende de si los `executable_path` de los distintos endpoints están en un único NAS compartido accesible desde un solo host, o si cada host tiene su bind mount local.
2. **¿Dónde se instala el runner?** — propuesta de host (puede ser el mismo host Jenkins actual, o uno nuevo).
3. **¿Se migran todos los apps a la vez o en olas?** — primer candidato ya probado: `acp-api`.

---

## 4. Salida esperada

Al devolver este documento con el checklist marcado, podemos:

- Cerrar el diseño del runner (§5.1 del spec).
- Cerrar el schema de `.github/deploy.json` (§5.3 del spec).
- Arrancar la implementación del deploy GA-native (Hito 3).

El spec canónico completo vive en `docs/v2-hito2-deploy-spec.md` — este documento es un resumen de validación, no lo reemplaza.
