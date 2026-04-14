# Hito 2bis — Guía para reunión con Soporte

> Propósito: esclarecer qué hace Jenkins hoy en el proceso de deploy a testing / staging / production para decidir **qué migrar a v2, cómo y cuándo**. Foco: la comunicación Jenkins ↔ Portainer.
>
> Salida esperada de la reunión: respuestas concretas a las preguntas de §4, suficientes para cerrar §5.1, §5.2 y §5.3 del spec canónico (`docs/v2-hito2-deploy-spec.md`) y arrancar Hito 3 (implementación del deploy GA-native).

---

## 1. Contexto para Soporte (leer antes de la reunión)

### 1.1 Qué estamos haciendo

Migramos el CI/CD de la organización desde Jenkins + Nexus hacia **GitHub Actions (GA) nativo**. Ya completamos:

- **Hito 1**: los workflows v2 no invocan Jenkins para CI (build, test).
- **Hito 2 §7**: los **server apps** (APIs scala, WARs, python servers) **ya no publican a Nexus** — publican a **GitHub Releases** del propio repo. Validado end-to-end en `acp-api`.

**Falta**: reemplazar el deploy que hoy hace Jenkins (stop container → copiar JAR/WAR → start container) por un workflow GA que haga lo mismo contra Portainer directamente.

### 1.2 Premisa ya confirmada

- **Todos los hosts están en la misma LAN** (sin sitios remotos / cross-DC).
- **Docker gestionado por Portainer** en todos los hosts.
- **Server apps** ahora tienen sus artefactos en **GitHub Releases**, no en Nexus.

Esto nos inclina hacia: **un único runner self-hosted de GitHub Actions en la LAN**, que se comunica con Portainer igual que Jenkins hoy.

### 1.3 Qué NO está en scope de esta reunión

- Client apps (BPos/GPos/IDH): tienen flujo propio, no entran acá.
- Libs (scala libs, protocolos): siguen en Nexus — no se deploya nada.
- Restore de base de datos: se aborda en un hito aparte.
- CI (build/test): ya migrado, funciona sin Jenkins.

---

## 2. Lo que hace Jenkins hoy (baseline — fuente: `deploy-nexus.groovy`)

Para cada deploy a testing / staging / production, Jenkins ejecuta:

1. **Recibe webhook** desde GitHub Actions con: `SISTEMA`, `VERSION`, `ENVIRONMENT`, `ACTOR`, `INSTALLATION`, `RESTORE`.
2. **Lee `config/sistemas.json`** (en el repo `BQN-UY/jenkins`): resuelve qué instalaciones corresponden al `(sistema, environment)`.
3. **Notifica inicio** a Google Chat.
4. **Si production** → stage `input` manual con submitter restringido (hoy: admins, soporte, auxiliar_soporte).
5. **Si `RESTORE=true`** → invoca job `IDS/restoreDB` (fuera de scope).
6. **Por cada instalación, en paralelo**:
   - **Resuelve URL** del artefacto en Nexus (vía Nexus Search API).
   - **Stop container** vía **Portainer API**.
   - **Descarga JAR/WAR** a archivo local en el agente Jenkins.
   - **Copia el artefacto** a `deploy_path/target_name` (en el host destino).
   - **Start container** vía **Portainer API**.
7. **Registra deploy** (en Jenkins).
8. **Notifica fin** a Google Chat.

**En v2 cambia**:
- Paso 6.1: el artefacto se descarga de **GH Releases** (no Nexus) con `gh release download`.
- Paso 4 y 7: la aprobación y el registro los hace GitHub (Environments + Deployments API).
- El resto (stop / copiar / start / notificar) hay que replicarlo en el runner GA.

---

## 3. La pregunta central: ¿cómo llega el JAR al container?

De esto depende todo el diseño del runner y del workflow de deploy. Hay tres mecanismos posibles y necesitamos saber **cuál refleja la realidad de hoy**:

| Opción | Cómo funciona hoy (hipótesis) | Implica en v2 |
|---|---|---|
| **α. Portainer API pura** | El container tiene un volumen montado; Jenkins sube el JAR al volumen vía endpoint Portainer (`/containers/{id}/archive` o similar), luego stop/start vía API. Nunca toca el host directamente. | Runner único en cualquier host de la LAN. No necesita SSH a los hosts. Solo token de Portainer. |
| **β. SSH + host FS + Portainer API** | Jenkins hace SSH/SCP al host destino, copia el JAR a `deploy_path` (bind mount leído por el container), y usa Portainer API solo para stop/start. | Runner único + SSH keys del runner a cada host. Más superficie, más secrets. |
| **γ. Rebuild de imagen** | Jenkins empuja el JAR a un registry como parte de una imagen nueva; Portainer redeploya la stack con la imagen nueva. | Runner único + registry de imágenes + redeploy via Portainer API. Cambio más grande. |

**Sospecha actual** (a confirmar): hoy es **β** (SSH + cp al host) porque el groovy habla de `deploy_path` y `target_name` a nivel filesystem, y Portainer API se usa sobre todo para stop/start.

Si es β y todos los hosts están en la LAN, con un **runner único** en la LAN alcanza — replica lo que hace Jenkins con las mismas credenciales que Jenkins tiene hoy.

---

## 4. Preguntas para Soporte

> Orden sugerido: 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6. Las primeras dos desbloquean el resto.

### 4.1 Autenticación y acceso de Jenkins a Portainer

- ¿Qué credencial usa Jenkins para hablar con Portainer hoy? (token de API, usuario/password, API key por endpoint…)
- ¿Es una única credencial para todos los endpoints Portainer, o una por endpoint?
- ¿Podemos generar una credencial equivalente (o reutilizarla) para el runner GA?
- ¿El token está scoped a ciertos endpoints / containers o tiene acceso global?

### 4.2 Mecanismo de deploy real — ¿cómo llega el JAR al container?

- ¿El JAR/WAR vive en un **volumen montado** del host (bind mount a `deploy_path`), o **dentro de la imagen** Docker?
- Si es bind mount: ¿Jenkins copia el archivo al host por **SSH/SCP**, o lo sube al volumen **vía Portainer API**?
- Si es SSH: ¿el agente Jenkins tiene claves SSH a cada host? ¿qué usuario? ¿están distribuidas cómo?
- ¿Alguna app usa un mecanismo distinto a los demás? (ej. WARs en Tomcat vs JARs standalone).

### 4.3 Instalaciones — qué significa hoy y cómo lo representamos en v2

En `sistemas.json` v1 hay `(sistema → environment → installations[])`. En v2 el plan es reemplazarlo por `.github/deploy.json` en cada repo app, con un schema tipo:

```json
{
  "environments": {
    "testing":    { "installations": [{ "name": "...", "portainer_endpoint": "...", "portainer_container": "...", "deploy_path": "/opt/...", "target_name": "...", "auto_deploy": true }] },
    "staging":    { "installations": [ ... ] },
    "production": { "installations": [ ... ] }
  }
}
```

Preguntas:

- ¿Cuántos `portainer_endpoint` distintos existen hoy? ¿Nombres?
- Para un sistema típico (ej. `acp-api`) en production: ¿cuántas instalaciones, en qué hosts / endpoints Portainer, con qué `deploy_path` y `target_name`?
- ¿Hay sistemas que deployan a **más de una instalación en paralelo** en el mismo ambiente (ej. varios nodos productivos)?
- ¿Campos extra que usen hoy y no estén en el schema propuesto?

### 4.4 Portainer — detalles operativos

- ¿Versión de Portainer? (API CE vs BE, endpoints difieren).
- ¿Los containers se identifican por **nombre** o por **ID**? (si es ID, cambia en cada recreate).
- Al hacer stop/start, ¿el container mantiene el bind mount (el JAR nuevo queda), o se recrea desde la imagen (y perdemos el cambio)?
- ¿Hay **health checks** que validan que el container arrancó bien después del start? Si no, ¿podemos agregarlos?
- ¿Cómo se hace **rollback** hoy si un deploy sale mal? (re-deploy de la versión anterior, script manual, snapshot…)

### 4.5 Notificaciones y auditoría

- ¿URL / webhook de Google Chat? ¿Es un solo canal para los tres ambientes o uno por ambiente? (pasa a ser secret del runner GA).
- ¿Formato de mensaje que Soporte quiere mantener? (inicio, fin, con link al run, etc.)
- ¿Qué registro de deploys existe hoy además del log de Jenkins? (lo reemplazaremos con GitHub Deployments API — nativo, sin servicio nuevo).

### 4.6 Aprobación de production

- Hoy: submitters habilitados en el `input` stage de Jenkins = `admins, soporte, auxiliar_soporte`. ¿Sigue siendo la política correcta?
- En v2: se migra a **GH Environments → required reviewers** (un team de GitHub). ¿Qué team/usuarios cubren esa lista?

---

## 5. Hosting del runner GA

Dado que todos los hosts están en la misma LAN, el plan es:

- **Un único runner self-hosted** (Linux), registrado a nivel organización BQN-UY, con label `bqn-deploy`.
- Instalado en un host de la LAN con acceso a:
  - Portainer API (todos los endpoints).
  - Hosts destino (si el mecanismo es β — SSH).
  - Internet saliente (para `gh release download`, `docker pull` si aplica).
- Servicio systemd, logs en journald, auto-update activado.

Preguntas para Soporte:

- ¿Qué host propone Soporte para hostear el runner? (opciones: el propio host de Jenkins, un nuevo VM, etc.)
- ¿Hay restricciones de red / firewall que debamos considerar?
- ¿Plan de DR: si el runner cae, cuál es el SLA aceptable? (sin deploys en vuelo críticos porque production es manual, pero snapshots/RCs sí dependen del runner).

---

## 6. Salida concreta de la reunión

Al cierre de la reunión deberíamos tener:

- [ ] Mecanismo de deploy confirmado (α / β / γ) → cierra §5.2 del spec
- [ ] Inventario de endpoints Portainer + ejemplo completo de instalaciones de un sistema → cierra §5.3 del spec
- [ ] Credenciales/tokens que el runner necesita (Portainer, SSH, Google Chat webhook)
- [ ] Host elegido para el runner GA + responsable de instalarlo → cierra §5.1 del spec
- [ ] Lista final de reviewers para GH Environment `production`
- [ ] Lista de sistemas/apps con casos especiales (WAR, Tomcat, etc.)

Con eso actualizamos `docs/v2-hito2-deploy-spec.md` §4 y §5, mergeamos y arranca **Hito 3** (implementación).

---

## 7. Referencias

- Spec canónico v2 (autoridad): `docs/v2-hito2-deploy-spec.md`
- Descripción del deploy v1 (baseline): `docs/jenkins.md` + `BQN-UY/jenkins/deploy-nexus.groovy`
- Roadmap v2 sin Jenkins: `docs/v2-sin-jenkins-roadmap.md`
