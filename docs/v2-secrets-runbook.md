# Runbook — Secrets de deploy v2

> **Alcance:** los 3 secrets org-level que usa el pipeline de deploy v2 (GitHub Actions). Cubre qué es cada uno, para qué se usa, cómo crearlo/obtenerlo, cómo cargarlo en GitHub y Keeper, y cómo rotarlo.
> **Audiencia:** Pablo + Bruno (responsables operativos), Jonathan (backup contingente de Bruno).
> **No cubre:** credenciales del pipeline v1 Jenkins (siguen gestionadas como hoy, fuera de alcance v2) ni secrets de repos individuales.

---

## Contexto

El diseño v2 (§5.2 de [`v2-deploy-design-proposal-soporte.md`](./v2-deploy-design-proposal-soporte.md)) acordó 3 secrets org-level:

- `PORTAINER_TOKEN_DEPLOY` — autentica llamadas a Portainer API (subida de artefacto + restart de containers)
- `GCHAT_WEBHOOK_PRODUCTION` — notifica al canal Google Chat `Deploy - Production`
- `GCHAT_WEBHOOK_TESTING_STAGING` — notifica al canal Google Chat `Deploy - Testing/Staging`

**Modelo β (GH primario + Keeper backup):**

- **GitHub org secrets** = sistema primario de runtime (lugar donde los workflows leen el valor).
- **Keeper Security** = backup explícito del valor + ledger de rotación, ownership y fechas.
- **Portainer / Google Chat** = sistemas de origen; fuente regenerable de último recurso si se pierde el valor en ambos lados.

**Regla operativa única:** por cada secret se escribe primero al GH org secret y a continuación al folder Keeper correspondiente, **en la misma sesión operativa**. Un solo patrón para los 3.

**Separación de deberes (3-way SoD):**

| Actor | Puede | No puede |
|---|---|---|
| Pablo / Bruno | Escribir GH secrets + escribir backup Keeper | Crear tokens en Portainer |
| Jonathan (backup de Bruno) | Leer backup Keeper testing-staging; en contingencia operar como Bruno con elevación temporal a admin GH org | Rutinariamente escribir GH secrets |
| Soporte Operativo (Jonathan / Elías en Portainer) | Crear/revocar tokens Portainer, configurar Portainer Teams | Ver el valor del secret en GH ni en Keeper |

---

## 1. `PORTAINER_TOKEN_DEPLOY`

### Qué es

Un **API access token de Portainer**. Formato string largo (`ptr_...` o similar según versión de Portainer). Emitido a nombre del usuario de servicio `github` (cuenta en FreeIPA + Portainer, la misma que Jenkins v1 usa por aplicación hoy).

El alcance real de privilegio lo determina el **Team `deploy-apps`** de Portainer — un grupo que Soporte configura con los endpoints/containers que el pipeline v2 puede tocar. El token hereda los permisos del usuario `github` + sus Teams.

### Para qué se usa

Los workflows de deploy v2 (GitHub Actions corriendo en runner self-hosted `docker-soporte`) hacen 2 llamadas HTTPS a la API de Portainer por cada deploy:

```
PUT  https://<portainer>/api/endpoints/{endpointId}/docker/containers/{id}/archive
POST https://<portainer>/api/endpoints/{endpointId}/docker/containers/{id}/restart

Header en ambas: X-API-Key: $PORTAINER_TOKEN_DEPLOY
```

- La primera sube el jar/war al container (reemplaza el artefacto).
- La segunda reinicia el container (regla D1 — restart siempre forzado, §5.1).

Es la única credencial que el runner necesita para hablar con la infraestructura. Por eso es único (1 token para todos los ambientes y repos; allowlist de repos + Portainer Team Scoping limitan el blast radius sin multiplicar tokens).

### Cómo crearlo / de dónde sale

**Pablo/Bruno NO lo crean** — según §5.2 del diseño, crear tokens en Portainer es responsabilidad de Soporte Operativo. El token nace en Portainer del lado de Soporte, ellos te lo pasan de forma segura, y vos lo cargás en GH + Keeper.

**Request exacto a Soporte:**

> Jonathan / Elías, necesito que me generen un API access token de Portainer para el deploy v2.
> Detalles: usuario `github` (cuenta de servicio existente), Team a asociar `deploy-apps` (crearlo si no existe, con acceso a los endpoints/containers de las server apps BQN que migremos a v2, empezando por `acp-api` y `colectivizacion` en testing/staging), nombre del token `deploy-v2`, expiración: sin expiración (rotación anual por política ISO A.5.17). Al crearse, Portainer muestra el valor una sola vez — pasámelo por Keeper o canal seguro (no texto plano en chat). Yo lo cargo en GH org secret + respaldo en Keeper folder `prod-critical` en la misma sesión.

**Del lado de Soporte (contexto, no lo hacemos nosotros):** Portainer UI → My account del usuario `github` (o admin impersonando) → Access tokens → Create access token → Description `deploy-v2` → copiar el valor.

### Cómo cargarlo (tu lado)

1. Abrir https://github.com/organizations/BQN-UY/settings/secrets/actions → **New organization secret**
2. **Name:** `PORTAINER_TOKEN_DEPLOY` (exacto, case-sensitive)
3. **Value:** pegar el valor recibido de Soporte
4. **Repository access:** `Selected repositories` — dejar vacío inicialmente (se agregan `acp-api` y `colectivizacion` al onboarding de cada piloto)

### Backup en Keeper (misma sesión)

- **Folder:** `prod-critical`
- **Entrada nueva** con el valor + metadata:
  - `created_at`: fecha de hoy
  - `owner`: `Pablo + Bruno`
  - `next_rotation`: hoy + 1 año
  - `maps_to_gh_secret`: `PORTAINER_TOKEN_DEPLOY`
  - `origin`: `Portainer user=github, Team=deploy-apps, tokenName=deploy-v2`

> **Por qué `prod-critical` y no `testing-staging`:** aunque el token se usa también en testing/staging, técnicamente puede tocar containers de production (no hay separación por ambiente del lado del token). Portainer Team + GitHub Environment protection actúan de barrera. Por eso el backup va en el folder de mayor criticidad.

### Rotación

- **Frecuencia:** anual (ISO A.5.17) o ad-hoc si hay sospecha de leak.
- **Procedimiento:**
  1. Pedir a Soporte que revoque el token `deploy-v2` y emita uno nuevo con el mismo nombre.
  2. Recibir el nuevo valor por canal seguro.
  3. Sobrescribir `PORTAINER_TOKEN_DEPLOY` en GH org secrets.
  4. Actualizar la entrada de Keeper con el nuevo valor y nueva `next_rotation`.
- **Ventana recomendada:** horario bajo uso — los workflows en ejecución al momento del cambio pueden fallar.

---

## 2. `GCHAT_WEBHOOK_PRODUCTION`

### Qué es

Una **URL de incoming webhook de Google Chat** apuntando al canal `Deploy - Production`. Formato:

```
https://chat.googleapis.com/v1/spaces/<SPACE_ID>/messages?key=<KEY>&token=<TOKEN>
```

Permite enviar mensajes al canal mediante POST HTTP sin autenticación adicional (la URL completa actúa como credencial).

### Para qué se usa

Los workflows de deploy v2 envían mensajes automáticos al canal cada vez que un deploy a **production** comienza, termina OK o falla. Ejemplos:

```
🚀 Deploy iniciado — acp-api v1.2.3 → production
✅ Deploy exitoso — acp-api v1.2.3 → production (2m 14s)
❌ Deploy fallido — acp-api v1.2.3 → production (tag no existe / container timeout / etc.)
```

La separación de canales production vs testing/staging se decidió en §5.5 del doc para que las alertas críticas de prod no se mezclen con el ruido de deploys de desarrollo.

### Cómo crearlo / de dónde sale

A diferencia del token de Portainer, los webhooks de Google Chat **NO requieren intervención de Soporte** — cualquier usuario con permisos de administración del canal puede crearlo. Pablo/Bruno (workspace admins) lo hacen directamente.

**Pasos en Google Chat:**

1. Abrir el canal `Deploy - Production`.
2. Click en el nombre del canal (arriba) → **Apps & integrations** → **Webhooks** → **Add webhook**.
3. **Name:** `CI/CD v2 Deploy Notifier (Production)`
4. **Avatar URL:** opcional (ícono de robot o similar).
5. Click **Save** → Google Chat muestra la URL generada — copiar inmediatamente.

> **Importante:** la URL se puede regenerar desde el mismo menú si se pierde, pero rotar implica actualizar GH + Keeper. Ver sección Rotación.

### Cómo cargarlo (tu lado)

1. https://github.com/organizations/BQN-UY/settings/secrets/actions → **New organization secret**
2. **Name:** `GCHAT_WEBHOOK_PRODUCTION`
3. **Value:** pegar la URL completa (incluyendo `?key=...&token=...`)
4. **Repository access:** `Selected repositories`, vacío inicialmente.

### Backup en Keeper (misma sesión)

- **Folder:** `prod-critical`
- Entrada nueva:
  - `created_at`: fecha de hoy
  - `owner`: `Pablo + Bruno`
  - `next_rotation`: hoy + 1 año
  - `maps_to_gh_secret`: `GCHAT_WEBHOOK_PRODUCTION`
  - `origin`: `Google Chat space "Deploy - Production", webhook name "CI/CD v2 Deploy Notifier (Production)"`

### Rotación

- **Frecuencia:** anual (alinear con el resto) o ad-hoc si se sospecha leak.
- **Blast radius de leak:** bajo — alguien con la URL puede spammear el canal, no daña infra ni filtra datos.
- **Procedimiento:**
  1. Canal `Deploy - Production` → Apps & integrations → Webhooks → editar `CI/CD v2 Deploy Notifier (Production)` → Regenerate URL (o eliminar y crear nuevo con mismo nombre).
  2. Sobrescribir `GCHAT_WEBHOOK_PRODUCTION` en GH org secrets.
  3. Actualizar entrada de Keeper.

---

## 3. `GCHAT_WEBHOOK_TESTING_STAGING`

### Qué es

Igual al anterior, apuntando al canal `Deploy - Testing/Staging`. Mismo formato de URL.

### Para qué se usa

Notifica deploys a **testing y staging** (ambos ambientes al mismo canal). Los deploys de testing generan más ruido (auto-deploy con cada push a `develop`) — por eso están en un canal separado del de production.

### Cómo crearlo / de dónde sale

Mismo procedimiento que `GCHAT_WEBHOOK_PRODUCTION`, cambiando:

- Canal destino: `Deploy - Testing/Staging`
- Nombre del webhook: `CI/CD v2 Deploy Notifier (Testing/Staging)`

### Cómo cargarlo (tu lado)

- **Name** en GH: `GCHAT_WEBHOOK_TESTING_STAGING`
- Mismo allowlist vacío inicialmente.

### Backup en Keeper (misma sesión)

- **Folder:** `testing-staging` (no `prod-critical` — este webhook es de menor sensibilidad y Jonathan necesita acceso de lectura según tabla 3-way SoD).
- Metadata análoga al anterior.

### Rotación

Idéntica a `GCHAT_WEBHOOK_PRODUCTION`.

---

## Checklist rápido de carga inicial (Fase 0 del issue #95)

Para cada uno de los 3 secrets, en orden:

- [ ] Obtener/crear el valor del sistema origen (Portainer vía Soporte, Google Chat directamente)
- [ ] Recibir el valor por canal seguro (si aplica)
- [ ] Crear el GH org secret con el nombre exacto, allowlist `Selected repositories` vacío
- [ ] Crear entrada en Keeper (folder correspondiente) con valor + metadata
- [ ] Verificar con `gh api orgs/BQN-UY/actions/secrets --jq '.secrets[] | {name, visibility}'` que aparece con `"visibility": "selected"`

Una vez los 3 secrets están cargados, pasar a Fase 1 del issue #95 (configuración por repo piloto + agregar cada repo al allowlist de los 3 secrets).

---

## Referencias

- Diseño acordado: [`v2-deploy-design-proposal-soporte.md`](./v2-deploy-design-proposal-soporte.md) §5.2 (modelo β), §5.3 (allowlist), §5.5 (approvers)
- Spec canónico v2: [`v2-hito2-deploy-spec.md`](./v2-hito2-deploy-spec.md)
- Acta follow-up Pablo ↔ Bruno: [`v2-deploy-followup-bruno.md`](./v2-deploy-followup-bruno.md)
- Issue de setup: [#95](https://github.com/BQN-UY/CI-CD/issues/95)
- GitHub org secrets: https://github.com/organizations/BQN-UY/settings/secrets/actions
- Portainer UI: (URL interna — ver bookmark de equipo)
- Google Chat admin: https://admin.google.com/
