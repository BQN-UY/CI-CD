# Identidad de automatizaciones en GitHub — PAT vs Machine User vs GitHub App

> **Propósito.** Documento de decisión + referencia sobre cómo BQN autentica sus automatizaciones en GitHub: workflows de CI/CD, Scala Steward, back-merges automatizados, inventory, propagación de libs.
>
> **Audiencia.** Bruno Artola, Pablo Zebraitis. También sirve de ramp-up para quien se sume a operar la infra CI/CD.
>
> **Estado.** Propuesta — pendiente de validación conjunta antes de ejecutar la transición.

---

## 1. Por qué este documento

La activación de CI/CD v2 libs (Fase 4) nos obliga a decidir: ¿qué credenciales usamos para que los workflows lean repos de la org y emitan `repository_dispatch`? Dos PATs clásicos (`ORG_INVENTORY_TOKEN`, `DISPATCH_TOKEN`) es lo rápido, pero abre dos preguntas que conviene responder juntas:

1. ¿Hay una alternativa mejor que PATs para automatización?
2. ¿Qué hacemos con `bqn-sysadmin`, nuestra cuenta de automatización actual?

Este doc responde ambas con el detalle suficiente para que Bruno pueda opinar fundadamente sin tener que investigarlo por separado.

---

## 2. Estado actual — `bqn-sysadmin`

### 2.1 Qué es

Una cuenta de usuario GitHub creada en enero 2021. Tipo: `User` (humana). No es una App. No es un "bot" técnicamente — es un humano de ficción.

```
login:        bqn-sysadmin
tipo:         User (human)
creada:       2021-01-12
rol en org:   admin (direct membership)
email:        null (oculto)
public repos: 0
seat:         consume 1 seat del plan GH de BQN
```

### 2.2 Para qué se usa realmente

Auditoría de commits firmados por `bqn-sysadmin` en los repos locales que tenemos (muestra de 30+ repos):

| Repo | Commits | Tipo predominante |
|---|---|---|
| `fui` | 184 | Scala Steward (dep updates) |
| `vaadin-app` | 171 | Scala Steward |
| `vaadin` | 165 | Scala Steward |
| `sga` | 151 | `[hotfix]` back-merges automatizados + Scala Steward |
| `ws` | 136 | Scala Steward |
| `crypt` | 129 | Scala Steward |
| `backoffice` | 113 | Scala Steward |
| `remote-printer-server` | 113 | Scala Steward |
| `utils` | 113 | Scala Steward |
| `common-libs` | 111 | Scala Steward |
| `banquinet-common-ui` | 104 | Scala Steward |
| `remote-printer-common` | 103 | Scala Steward |
| `pdf` | 97 | Scala Steward |
| ... | ... | mismo patrón |

**Conclusión del audit:** `bqn-sysadmin` es hoy, en la práctica, la identidad bajo la cual corre **Scala Steward** (propagación automática de actualizaciones de dependencias sbt) y los **back-merges automatizados** de hotfixes en Jenkins.

### 2.3 Permisos actuales

`bqn-sysadmin` es **admin de la org BQN-UY**. Eso significa acceso a:
- Todos los repos (read/write).
- Settings de la org (secrets, webhooks, teams, billing).
- Creación/eliminación de repos.
- Invitar/expulsar miembros.

**Principio de mínimo privilegio (ISO A.8.2).** El uso real de `bqn-sysadmin` (abrir PRs con updates de deps + hacer back-merges) requiere `contents:write` + `pull_requests:write` sobre los repos donde opera. No requiere privilegios de **admin de org**. Actualmente le estamos dando muchísimo más de lo que necesita.

### 2.4 Costo

- **1 seat GH** consumido mientras la cuenta exista.
- **Superficie de ataque:** credenciales (password, SSH keys, PATs) de una cuenta admin viven en algún lado (Keeper, probablemente). Si alguna se filtra → control total de la org.
- **Mantenimiento:** rotación de PAT/password manual; recovery email/phone a gestionar; MFA a configurar; etc.

---

## 3. Tres opciones conceptuales

| Opción | Qué es | Cuenta humana? | Consume seat? |
|---|---|---|---|
| **PAT clásico** | Token personal de un humano real (ej Pablo) | — | No (el seat lo paga el humano que ya existe) |
| **Machine user** | Cuenta GH creada específicamente para automatización (ej `bqn-sysadmin`) | Sí (es una cuenta `User` que parece humana) | **Sí, 1 por cuenta** |
| **GitHub App** | Identidad de primer nivel, distinta de `User` | No — es otra entidad en el sistema | **No** |

La industria convergió en los últimos 5 años hacia **GitHub Apps** para automatización. Machine users siguen existiendo porque resolvían cosas que las Apps originalmente no podían hacer (como ser reviewer), pero esas brechas se han ido cerrando.

---

## 4. Analogía sencilla

**PAT = tu llave personal.**
Cuando un workflow la usa, actúa **como vos**. Si mañana te vas, el workflow se cae. Si la llave se filtra en un log, el atacante puede hacer todo lo que vos podés hacer.

**Machine user = un "empleado fantasma".**
Una cuenta que parece persona pero que no es nadie. Tiene credenciales propias pero figura como usuario en todos los papeles. Paga seat, consume licencia, el auditor pregunta quién es. Es la solución de la era 2015.

**GitHub App = un empleado robot con contrato claro.**
Pertenece a la organización, no a una persona. Tiene permisos acotados por configuración. Cuando actúa, se identifica como sí mismo (`bqn-cicd-automation[bot]`). Si te vas, sigue funcionando. Si sus credenciales se roban, solo puede hacer lo que su "etiqueta de empleado" le permite, por 1 hora máximo.

---

## 5. Cómo funciona cada uno dentro de un workflow

### 5.1 Flujo con PAT (o machine user)

```
1. Alguien crea PAT en su cuenta GH → guarda valor en Keeper + GH secret
2. Workflow corre
3. Workflow usa el secret directo → API de GH lo autentica como el dueño del PAT
4. Logs, auditoría, commits → aparecen como hechos por ese usuario
5. El PAT vive N meses o "never expires"
```

### 5.2 Flujo con GitHub App

```
1. Admin crea la App en settings de la org (una vez)
   - Define permisos exactos: contents:read, pull_requests:write, etc.
   - La App le da: APP_ID (público) + PRIVATE_KEY (archivo .pem secreto)
   - Admin guarda PRIVATE_KEY en Keeper + GH secret (org-level)
2. Admin instala la App en la org BQN-UY (una vez)
   - Selecciona a qué repos da acceso: "All repos" o "Selected"
3. Workflow corre
4. Workflow llama al action oficial actions/create-github-app-token
   - Ingresa APP_ID + PRIVATE_KEY
   - Recibe de vuelta un installation-token efímero (vive 1 hora)
5. Workflow usa ese token → API de GH lo autentica como "bqn-cicd-automation[bot]"
6. Logs, auditoría, commits → aparecen como hechos por el bot, separados de humanos
7. A la hora, el token expira automáticamente
```

El usuario nunca ve el installation-token — se genera, se usa, se descarta.

---

## 6. Las cinco ganancias reales (en orden de importancia ISO)

### 6.1 Identidad no atada a una persona (ISO A.5.30 continuidad)

Si Pablo se va de BQN:
- Con **PAT** → el workflow se cae. Alguien tiene que generar un PAT nuevo y reprovisionar en cada lugar donde estaba.
- Con **machine user** → la cuenta sigue, pero sus credenciales las tenía quien la creó. En la práctica, si nadie más tiene las contraseñas/keys, también se cae.
- Con **App** → la App sigue. Admin transfiere la administración a otro. Cero interrupción.

En un equipo de 7 donde 2 personas tienen admin, **la continuidad del negocio no puede depender del PAT de un individuo ni de una cuenta zombie**. ISO A.5.30 lo pide literalmente.

### 6.2 Tokens ephemeral (ISO A.5.17 credenciales gestionadas)

- **PAT** que vive 1 año → si leakea en un log a día 1, el atacante tiene 365 días de ventana.
- **Installation token de App** que vive 1 hora → ventana máxima 60 minutos.

Cambia radicalmente la postura ante un incidente. Si descubrís un leak de tu PAT hoy, tenés que rotarlo ya, investigar qué se hizo, etc. Si descubrís un leak de un installation-token, ya expiró.

### 6.3 Scoping granular (ISO A.8.2 privilegios mínimos)

Un PAT tiene scope del tipo "repo" (todas las operaciones que el usuario puede hacer en todos los repos que puede tocar). Incluso los fine-grained PATs son más gruesos.

Una App declara permisos como:
```
Repository permissions:
  contents: read
  metadata: read
  repository_dispatch: write
  pull_requests: write
Organization permissions: (ninguna)
```

Esa es la "etiqueta del empleado robot" — si alguien intenta hacer algo que no está en la etiqueta, GitHub lo rechaza **aunque haya robado el token**.

### 6.4 Audit trail separado (ISO A.8.15 logging)

En el audit log cuando usás PAT:
```
[2026-04-15 10:23] pablo-zebraitis created repository_dispatch on acp-api
```
¿Fue Pablo? ¿Fue un workflow? No se distingue.

Con App:
```
[2026-04-15 10:23] bqn-cicd-automation[bot] created repository_dispatch on acp-api
```
Sabés instantáneamente que fue automatización. Oro para investigar incidentes.

### 6.5 Rate limits más altos

- PAT: 5000 req/hora compartidas con actividad humana en GH.
- App: 5000 req/hora **por instalación**, aislado del consumo humano.

A nivel BQN no es crítico, pero `inventory.yml` escaneando 30 repos podría tocar el rate limit compartido y bloquear el trabajo normal en la UI.

---

## 7. Impacto en seats / billing

Cuestión específica que nos preocupaba: **¿la App consume licencia?**

| Identidad | Consume seat | Costo |
|---|---|---|
| Human user | Sí | 1 seat × plan |
| **Machine user** (`bqn-sysadmin` hoy) | **Sí** | **1 seat × plan** |
| GitHub App | **No** | Gratis, ilimitadas |

Esto inclina la balanza aún más fuerte hacia Apps. No solo no cuesta nada, sino que **migrar `bqn-sysadmin` → App libera un seat**.

---

## 8. Lo que NO cambia (mito a disipar)

**"Con GitHub App no hay credencial que se pueda filtrar."** Falso.
La PRIVATE_KEY sigue siendo un archivo que hay que proteger. Si leakea, atacante puede generar installation-tokens a voluntad. La diferencia real es que **los tokens derivados son de corta vida**, pero la private key en sí es el mismo tipo de "llave maestra" que el PAT.

Mitigación:
- PRIVATE_KEY vive en Keeper folder `prod-critical`, nunca sale de ahí salvo a GH como secret.
- Rotación de la key = regenerar `.pem` en GH (1 click), actualizar en Keeper + GH secret.
- Más simple que rotar un PAT entre múltiples lugares.

---

## 9. Costo de implementación

### 9.1 Setup inicial — una sola vez, estimado 30-60 min

1. GH org settings → Developer settings → GitHub Apps → New GitHub App.
2. Nombre: `bqn-cicd-automation`. Homepage: link a CI-CD repo. Descripción.
3. Webhook: **desmarcar "Active"** (no necesitamos webhooks — la App es "client-side" en nuestros workflows).
4. Permisos (Repository permissions): solo los mínimos necesarios (ver §10).
5. Subscribe to events: ninguno.
6. Where can this app be installed: **Only this organization**.
7. Create → GitHub genera APP_ID.
8. Generate a private key → descarga `.pem`.
9. Install App → BQN-UY → seleccionar repos.
10. En Keeper: crear entrada `github-app-bqn-cicd-automation` en folder prod-critical con APP_ID + PRIVATE_KEY.
11. En GH org secrets: `BQN_CICD_APP_ID` (value plain) + `BQN_CICD_APP_PRIVATE_KEY` (paste del .pem entero).

### 9.2 Uso en workflow — cambio mínimo

En lugar de:
```yaml
- name: Build inventory
  env:
    GH_TOKEN: ${{ secrets.ORG_INVENTORY_TOKEN }}
  run: python scripts/build-inventory.py
```

Queda:
```yaml
- uses: actions/create-github-app-token@v1
  id: app-token
  with:
    app-id: ${{ secrets.BQN_CICD_APP_ID }}
    private-key: ${{ secrets.BQN_CICD_APP_PRIVATE_KEY }}
    owner: BQN-UY
- name: Build inventory
  env:
    GH_TOKEN: ${{ steps.app-token.outputs.token }}
  run: python scripts/build-inventory.py
```

Dos líneas extra; token fresco en cada run.

---

## 10. Permisos recomendados para `bqn-cicd-automation`

Para cubrir los casos de uso identificados (inventory + propagation libs + futuros workflows):

| Permiso | Nivel | Justificación |
|---|---|---|
| `contents` | read | Para inventory (leer `build.sbt` de cada repo) |
| `contents` | write | Para abrir PRs con bump de versiones (push de branches) |
| `metadata` | read | Requerido por default |
| `pull_requests` | write | Para que `update-on-dispatch.yml` pueda abrir PRs |
| `repository_dispatch` | write | Para emitir eventos entre libs y consumers |

Ninguno a nivel organización. Ningún webhook. Solo 5 permisos, todos acotados.

---

## 11. Plan de transición desde `bqn-sysadmin`

### 11.1 Premisa

`bqn-sysadmin` hoy cubre al menos dos casos identificados:

1. **Scala Steward** (dep updates automáticos en 30+ repos).
2. **Back-merges automatizados** en Jenkins shared library (ej `[hotfix] Update main from X.Y.Z` en `sga`).

Ambos son automatización pura, sin interacción humana. Candidatos perfectos para reemplazar por App.

### 11.2 Fase A — inmediata (crear la App, redireccionar casos nuevos)

1. Crear `bqn-cicd-automation` según §9.1.
2. Usar la App para **casos nuevos**: inventory, propagation libs, deploy v2 workflows.
3. **NO tocar `bqn-sysadmin` todavía.** Sigue funcionando para Scala Steward y Jenkins mientras migramos.

### 11.3 Fase B — migrar Scala Steward

Scala Steward en BQN corre (según patrón de commits) probablemente como un workflow cron o Docker externo que usa PAT de `bqn-sysadmin`. Migrarlo:

1. Revisar cómo está configurado hoy (probablemente un repo con `scala-steward.conf` o GH Action).
2. Cambiar el token que usa por un installation token generado con nuestra App.
3. Validar que abre PRs firmados por `bqn-cicd-automation[bot]`.

### 11.4 Fase C — migrar back-merges Jenkins

Los `[hotfix] Update main from X.Y.Z` en `sga` son Jenkins pushing de vuelta a main. En v2 esto se reemplaza naturalmente: los back-merges los hace el workflow `scala-api-make-release.yml` con `GITHUB_TOKEN` nativo (ya probado en libs v2).

**Cuando Jenkins se retire** (final del rollout v2), este caso de uso desaparece por construcción.

### 11.5 Fase D — deprecar `bqn-sysadmin`

Una vez que:
- Scala Steward usa la App.
- Jenkins está retirado (o al menos no usa `bqn-sysadmin` para pushes).
- No quedan otros workflows que dependan de `bqn-sysadmin`.

**Acciones:**
1. Cambiar rol de `bqn-sysadmin` de `admin` → `member` (reducir privilegios).
2. Revocar todos los PATs activos de la cuenta.
3. Deshabilitar la cuenta (Settings de la cuenta → Account settings → deactivate).
4. **Liberar el seat.**

**No borrar la cuenta.** Conservar el username para que el audit trail histórico siga apuntando a una cuenta reconocible.

### 11.6 Checklist práctico de validación antes de deprecar

Antes de ejecutar Fase D, confirmar:

- [ ] Ningún branch protection lista a `bqn-sysadmin` como reviewer designado.
- [ ] Ningún CODEOWNERS lo menciona.
- [ ] No hay workflow de GH Actions usando secrets que provengan de sus PATs.
- [ ] No hay webhook de org/repo configurado a nombre suyo.
- [ ] No hay repos donde figure como único collaborator (ej repos personales que se hayan transferido).
- [ ] Scala Steward migrado a App.
- [ ] Jenkins retirado de los flujos que hacían pushes.

---

## 12. Riesgos específicos a considerar

### 12.1 Concentración de permisos en una sola App

Si `bqn-cicd-automation` tiene los 5 permisos, un compromiso de la key da acceso amplio. Mitigación conceptual: **dos Apps separadas**, una read-only para inventory (solo `contents:read`), otra permisiva para propagation. Duplica el setup pero reduce blast radius.

**Posición para BQN size:** una sola App en Fase A (simplicidad). Evaluar separar si crecemos o si ISO lo exige.

### 12.2 Dependencia del action `create-github-app-token`

Es el action oficial de GitHub, pero igual introducimos una dependencia externa. Mitigación: pinearlo a SHA específico y revisar al año.

### 12.3 Administración de la App

Pablo + Bruno como admins de la App (misma lista que admins org). Si ambos no están y hay que rotar la key → bloqueo operativo.

Mitigación: procedimiento de rotación documentado, acceso a la App coordinado desde Keeper folder prod-critical (ambos tienen acceso).

### 12.4 Durante Fase A, dos identidades de automatización conviven

Mientras `bqn-sysadmin` sigue corriendo Scala Steward y la App corre los casos nuevos, el audit trail tiene dos fuentes. Es temporal (hasta Fase B) y manejable.

---

## 13. Decisión recomendada

**Ir con GitHub App.** Una sola App para empezar (`bqn-cicd-automation`) con los 5 permisos mínimos del §10.

**Justificación condensada:** cumple ISO A.5.30 (continuidad sin atar a personas) + A.5.17 (tokens efímeros) + A.8.2 (scoping) + A.5.16 (gestión de identidades más limpia) + A.8.15 (audit trail separado). Costo único de 30-60 min de setup. Ahorro: 1 seat GH al deprecar `bqn-sysadmin`, simplificación de rotaciones.

**Plan de ejecución:** Fases A → B → C → D descritas en §11. Fase A es el único prerrequisito para desbloquear activación libs v2 (Fase 4).

---

## 14. Preguntas abiertas (input del equipo)

1. **Una App o dos (read-only + read-write)?** Mi recomendación: una sola para arrancar, pero vale decisión explícita de vos + Bruno.
2. **Scala Steward: cómo corre hoy?** (workflow cron, Docker externo, otra cosa). Saberlo define el esfuerzo de Fase B.
3. **¿Alguien más de BQN tiene acceso operativo a `bqn-sysadmin`?** (Otros admins que usen la cuenta para algo manual.)
4. **Timeline para Fase D (deprecar `bqn-sysadmin`)**: ¿la atamos al retiro de Jenkins, o es independiente?

---

## 15. Referencias

- GitHub docs — About Apps: https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/about-creating-github-apps
- Action oficial `create-github-app-token`: https://github.com/actions/create-github-app-token
- GitHub Apps vs OAuth vs PAT: https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/about-creating-github-apps#comparing-github-apps-to-oauth-apps
- Issue #95 (setup deploy v2) — donde viven los secrets de deploy, separados de estos.
- Issue (pendiente de crear) — activación libs v2 Fase 4, que consume la App una vez creada.
