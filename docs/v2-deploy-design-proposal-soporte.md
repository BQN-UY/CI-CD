# Propuesta de diseño Deploy v2 — Documento de evaluación con Soporte Operativo

> **Estado:** Borrador para revisión conjunta Desarrollo ↔ Soporte Operativo.
> **Autores:** Pablo Zebraitis (Technical Lead / ISO Officer).
> **Destinatarios:** Bruno Artola (Head of Operational Support), Jonathan Correa Paiva (Analista Operativo), Elías Severino (Analista Operativo).
> **Fecha:** 2026-04-15.
> **Objetivo del documento:** Alcanzar alineamiento explícito sobre el diseño de la migración de deploy v1 (Jenkins) → v2 (GitHub Actions) **antes** de iniciar la implementación de Hito 3.

---

## Índice

1. [Contexto y principio rector](#1-contexto-y-principio-rector)
2. [Cómo leer este documento](#2-cómo-leer-este-documento)
3. [Diferencias clave v1 vs v2](#3-diferencias-clave-v1-vs-v2)
4. [Actores del proceso de deploy v2](#4-actores-del-proceso-de-deploy-v2)
5. [Decisiones cerradas entre Desarrollo para revisar con Soporte](#5-decisiones-cerradas-entre-desarrollo-para-revisar-con-soporte)
    - 5.1 [Restart siempre forzado](#51-restart-siempre-forzado)
    - 5.2 [Modelo de credenciales](#52-modelo-de-credenciales-org-level-secrets--keeper--portainer-team-scoping)
    - 5.3 [Allowlist de repos que pueden deployar a producción](#53-allowlist-de-repos-que-pueden-deployar-a-producción)
    - 5.4 [Sistemas piloto](#54-sistemas-piloto)
    - 5.5 [Approvers de producción y fusible SoD](#55-approvers-de-producción-y-fusible-sod)
    - 5.6 [Paths de artefactos vía Docker API](#56-paths-de-artefactos-vía-docker-api)
    - 5.7 [Auto-deploy opt-in per-instalación](#57-auto-deploy-opt-in-per-instalación)
6. [Consultas pendientes ya enviadas al canal](#6-consultas-pendientes-ya-enviadas-al-canal)
    - 6.1 [Arquitectura del runner (A / B / C)](#61-arquitectura-del-runner-a--b--c)
    - 6.2 [Identificación de containers en `deploy.json`](#62-identificación-de-containers-en-deployjson)
7. [Consideraciones transversales](#7-consideraciones-transversales)
    - 7.1 [Controles ISO 27001 aplicados](#71-controles-iso-27001-aplicados)
    - 7.2 [Concurrencia de deploys](#72-concurrencia-de-deploys)
    - 7.3 [Rollback y recuperación](#73-rollback-y-recuperación)
    - 7.4 [Retención y auditoría](#74-retención-y-auditoría)
    - 7.5 [Fallos del sistema Portainer](#75-fallos-del-sistema-portainer)
    - 7.6 [Requisitos de red del runner](#76-requisitos-de-red-del-runner)
8. [Plan de rollout](#8-plan-de-rollout)
9. [Matriz de decisiones — tabla de revisión](#9-matriz-de-decisiones--tabla-de-revisión)
10. [Conformidades](#10-conformidades)

---

## 1. Contexto y principio rector

### 1.1 Alcance

Este documento cubre el diseño del **deploy de server apps** (APIs Scala/Pekko, WARs tomcat, servidores Python) en la v2 del CI/CD de BQN. Fuera de alcance: client apps (BPos/GPos/IDH), librerías internas (siguen publicando a Nexus), y restore de base de datos.

### 1.2 Principio rector del diseño

Cualquier decisión de arquitectura debe cumplir **simultáneamente** tres criterios; si uno no se cumple, se descarta:

1. **Simple de operar para Soporte Operativo** — Soporte debe poder ejecutar deploys, rollbacks e investigar incidentes sin depender del equipo de Desarrollo.
2. **Defendible ante ISO 27001** — los controles aplicables (A.5.15, A.5.17, A.8.3, A.8.15, A.8.32) deben poder mapearse a mecanismos concretos del pipeline.
3. **Sostenible con el equipo actual** — 7 personas totales, 2 admins de GH org, 1 Technical Lead con rol dividido. Ninguna decisión puede descansar en rotaciones/auditorías que requieran tiempo que el equipo no tiene.

### 1.3 Diferencia respecto al Hito 2 previo

El [spec técnico](./v2-hito2-deploy-spec.md) describe el **qué** (artefactos en GH Releases, versionado `vX.Y.Z[-snapshot|-rc].NNN`, etc.). Este documento describe el **cómo operativo** (runner, credenciales, aprobaciones, notificaciones) y busca la conformidad de Soporte **antes** de codificar el Hito 3.

---

## 2. Cómo leer este documento

Cada sección 5.x sigue la estructura:

- **Propuesta:** decisión tomada entre los autores del documento.
- **Análisis:** opciones consideradas y por qué se descartaron las alternativas.
- **Implicancias para Soporte:** qué cambia operativamente respecto a v1.
- **Pedido a Soporte:** pregunta concreta o validación esperada.

Las secciones 6.x son **consultas ya formuladas en el canal** reproducidas aquí para contexto completo — la respuesta la dará Soporte en el chat o en la revisión de este documento.

Todas las decisiones son **revisables**. Si Soporte identifica una razón operativa o normativa que invalide algo, se re-abre la discusión.

---

## 3. Diferencias clave v1 vs v2

| Concepto | v1 (actual, Jenkins) | v2 (propuesto, GitHub Actions) | Por qué cambia |
|---|---|---|---|
| Orquestador | Jenkins central + agentes por host | GitHub Actions + runner self-hosted | Eliminar punto único de mantenimiento legacy |
| Config de instalaciones | `sistemas.json` centralizado en repo `jenkins` | `.github/deploy.json` en cada repo | La configuración de deploy vive con la app que se deploya |
| Fuente de artefactos | NAS/FTP (descarga vía `remoteTarget`) | GitHub Releases (descarga vía `gh release download`) | Inmutabilidad, auditoría nativa, eliminar dependencia NAS |
| Copia del artifact | `cp` a `/opt/webapps/...` o `home container` del host | `PUT /containers/{id}/archive` vía Docker API (Portainer proxy) | Desacopla el CI/CD del layout del host |
| Restart del container | Jenkins → script → `docker restart` | Portainer API `POST /containers/{id}/restart` | Unificado, auditable, vía Teams de Portainer |
| Credenciales | FTP + SSH + token Portainer (per-app, user `github` FreeIPA) | Org-level secrets GH + mismo token Portainer + Keeper como source of truth | Menos secrets a rotar, SoD natural Keeper/GH/Portainer |
| Aprobación producción | Job Jenkins `DeployApp` (admins, soporte, auxiliar_soporte) | GH Environment `production` con required reviewers | Nativo de la plataforma, auditable por GitHub |
| Notificaciones Chat | Webhooks por app, desde Jenkins | Webhooks unificados por ambiente, desde el workflow | Deploy-Testing/Staging y Deploy-Production siguen siendo 2 canales |
| Rollback | Redeploy de versión anterior vía Jenkins | Redeploy de tag anterior vía `workflow_dispatch` | Mismo concepto, ejecutado por GH en vez de Jenkins |

---

## 4. Actores del proceso de deploy v2

Identificación explícita de quién participa en qué etapa. Base para el análisis de **Separación de Deberes (ISO A.8.3)**.

| Actor | Rol en el proceso v2 |
|---|---|
| Equipo IDS Development (Santi, Nacho, Jose) | **Ninguna participación directa en el deploy.** Desarrollan, mergean PRs a `main`, pushean a `develop`. El CI reacciona automáticamente. Nunca triggerean, nunca aprueban. |
| Pablo Zebraitis | Technical Lead, ISO Officer, admin GH org, admin Keeper. Approver de producción. Puede disparar `make-release` y aprobar deploys prod. |
| Bruno Artola | Head of Operational Support, admin GH org, admin Keeper. Approver de producción. Puede disparar `make-release` y aprobar. |
| Jonathan Correa Paiva | Analista Operativo, acceso Keeper (testing/staging). Approver de producción. |
| Elías Severino | Analista Operativo. Approver de producción. |

**Universo de actores humanos en el deploy v2: 4 personas** (Pablo + Bruno + Jonathan + Elías). Este dato condiciona todo el análisis de SoD que sigue.

---

## 5. Decisiones cerradas entre Desarrollo para revisar con Soporte

### 5.1 Restart siempre forzado

**Propuesta.** Todo deploy v2 termina con `POST /containers/{id}/restart` incondicional tras escribir el artifact. No hay flag ni opt-out.

**Análisis.**

Se consideraron tres opciones:

| Opción | Descripción | Resultado |
|---|---|---|
| i. Restart siempre forzado | Incondicional, sin config | **Elegida** |
| ii. Restart opt-out | Default `true`, flag `restart: false` por instalación | Descartada |
| iii. Restart opt-in | Default `false` (hot-reload), flag `restart: true` | Descartada |

Razones para elegir i:

- **Scala/Pekko requiere restart obligatorio** — no hay hot-reload confiable. Ya es mandatorio para la mayoría del stack BQN.
- **Tomcat hot-reload es anti-pattern conocido** — leaks de classloader (PermGen, sockets, threads), estados en memoria inconsistentes, fallas silenciosas difíciles de diagnosticar. Es legado de la era WAR 2000s que la filosofía de containers ("cattle, not pets") descartó.
- **Determinismo > eficiencia de downtime** — con 2 analistas operativos, debuggear un "fantasma de hot-reload fallido" consume más tiempo que aceptar 5-30s de downtime por deploy.
- **Menos superficie de configuración = menos bugs operativos.** Cada flag en `deploy.json` es una decisión que Soporte debe mantener mentalmente al diagnosticar.
- **ISO A.8.32 (Change management)** exige cambios "controlados y reversibles". Restart explícito marca un punto claro antes/después en logs. Hot-reload deja estado ambiguo.

Si eventualmente apareciera un caso que requiere zero-downtime, la solución correcta es **rolling deploy con múltiples réplicas + load balancer**, no hot-reload. Esto es una feature nueva (no un flag de `deploy.json`) y se trataría en un ticket aparte.

**Implicancias para Soporte.**

- Todo deploy implica ~5-30s de downtime del container actualizado. Apps BQN hoy no tienen SLA de 99.99% → aceptable.
- Si hay un caso actual donde NO se reinicia el container tras reemplazar jar/war (ej: mantener conexiones de larga duración, estado en memoria), debe documentarse → indicaría que v2 necesita rolling para ese caso específico.

**Pedido a Soporte.**

> ¿Existe hoy algún sistema donde explícitamente NO se reinicia el container tras reemplazar el jar/war, y donde eso sea operativamente crítico (ej: requiere mantener estado en memoria, conexiones de larga duración, sesiones stateful)? Si no, queda restart siempre como regla v2.

---

### 5.2 Modelo de credenciales (org-level secrets + Keeper + Portainer Team scoping)

**Propuesta.** Un único juego de credenciales org-level con allowlist de repos, source of truth en Keeper Security, y scoping de privilegio real del lado de Portainer (Teams).

```text
Keeper Security (source of truth)                Quién accede
├── folder "prod-critical"                        Pablo + Bruno
│   └── Portainer token prod, webhook prod
└── folder "testing-staging"                      Pablo + Bruno + Jonathan
    └── Portainer token, webhooks

GitHub org secrets (copia para deployment-time)   Quién provisiona
├── PORTAINER_TOKEN_DEPLOY                        Pablo + Bruno
├── GCHAT_WEBHOOK_TESTING_STAGING                 Pablo + Bruno
└── GCHAT_WEBHOOK_PRODUCTION                      Pablo + Bruno

Portainer (privilege enforcement)                 Quién configura Teams
└── Team "deploy-apps" → endpoints/containers     Soporte Operativo
```

**Análisis.**

Tres modelos evaluados:

| Modelo | GH scope | Token scope | Total secrets | Blast radius de leak |
|---|---|---|---|---|
| A. Per-repo + per-app token | Secret por repo (~30) | Un token por app en Portainer | ~90 | Mínimo (1 repo afectado) |
| B. Org-level + global token | Todos los repos de la org | Token único potente | 3 | Máximo (toda la org) |
| C. Org-level selected + Team-scoped token | Allowlist explícita de repos | Token único, Team en Portainer limita endpoints | 3 | Medio (repos en allowlist + alcance del Team) |

Dimensiones del análisis:

- **Seguridad real vs. auditoría:** en v1 BQN ya usa el usuario `github` de FreeIPA para todos los tokens por app. Entonces "un token por app" en v1 es mayormente trazabilidad, no aislamiento real de privilegio. El privilegio real ya lo controla Portainer Teams. Multiplicar tokens no agrega aislamiento adicional; solo multiplica el trabajo de rotación.
- **Auditoría:** GH Actions ya registra qué workflow/repo ejecutó qué llamada al token. El "audit trail por token distinto" es redundante con eso.
- **Rotación realista:** para ISO A.5.17 (authentication info gestionada) se espera rotación anual. Con 2 admins GH y tamaño de equipo 7, **90 secrets × rotación = ~1 día-persona/año** que realistamente no se va a hacer. **3 secrets × rotación = 30 minutos** que sí se hace. Un control que no se ejecuta es teatro.
- **Keeper como capa adicional:** Keeper ya aporta segregación de acceso a credenciales por nivel (folders prod-critical vs testing-staging). Esto es un control ISO A.5.17 independiente de cuántos secrets haya en GH.
- **Vectores de leak considerados y su mitigación real:**
    - PR malicioso que exfiltra secret → mitigado por branch protection + required reviews, no por cantidad de secrets.
    - Log leak (print accidental) → GH Actions redacta automáticamente.
    - Runner comprometido → en ejecución tiene lo que tiene; cantidad de secrets no cambia exposición.
    - Insider malicioso → universo de 4 actores en el proceso, confianza base.
    - **Rotación olvidada → aquí sí cambia radicalmente:** menos secrets = más probabilidad de rotar.

Control SoD emergente (3-way):

| Actor | Puede | No puede |
|---|---|---|
| Pablo / Bruno | Ver en Keeper, escribir a GH secrets | Crear tokens en Portainer (Soporte) |
| Jonathan | Ver testing/staging en Keeper | Escribir GH secrets (no es admin org) |
| Soporte | Crear/revocar tokens Portainer, configurar Teams | Ver los secrets finales en GH |

Esta estructura **no fue diseñada ad-hoc para v2** — emerge de herramientas ya instaladas (Keeper, GH roles, Portainer). Vale formalizarla como control ISO existente.

Mapeo ISO:

| Control | Cómo se cumple |
|---|---|
| A.5.15 Access control / need-to-know | Allowlist de repos + Portainer Team scoping + folders Keeper |
| A.5.17 Authentication info | Keeper como gestión centralizada; rotación anual viable |
| A.8.2 Privileged access | Portainer Team define qué endpoints/containers puede tocar el token |
| A.8.3 SoD | 3-way Keeper/GH/Portainer, sin diseño extra |
| A.8.15 Logging | Keeper logs + GH Actions logs + Portainer logs = triple trail |

**Implicancias para Soporte.**

- Soporte configura un único `Team "deploy-apps"` en Portainer que define los endpoints/containers que el pipeline puede tocar.
- El token vive en Keeper (folder según nivel). Soporte lo regenera allí cuando toca rotarlo; Pablo/Bruno lo propagan a GH secrets.
- Onboarding de un repo nuevo: agregar repo al allowlist de los 3 org secrets (1 minuto, GH UI). No se crean tokens ni webhooks nuevos.

**Pedido a Soporte.**

> ¿Hay algún requisito operativo o normativo (DNLQ, DGI, otra auditoría externa) que obligue a mantener un token Portainer distinto por aplicación? El modelo v2 propuesto consolida en un token único con scoping vía Teams; si existe un requisito que lo invalide, volvemos al modelo per-app y dimensionamos el costo de rotación.

---

### 5.3 Allowlist de repos que pueden deployar a producción

**Propuesta.** Un repo está en el allowlist de los 3 org secrets (`PORTAINER_TOKEN_DEPLOY`, `GCHAT_WEBHOOK_TESTING_STAGING`, `GCHAT_WEBHOOK_PRODUCTION`) **si y solo si** declara al menos una instalación con `environment: production` en `.github/deploy.json`.

Tentativamente, los 3 secrets comparten el mismo allowlist.

**Análisis.**

Tipos de repo en la org BQN-UY y su participación en deploy:

| Tipo | Ejemplo | ¿En allowlist? |
|---|---|---|
| Server apps Scala/Pekko | `acp-api`, `bol-api`, `bsecurity-api`, `fui-api` | Sí |
| Server apps tomcat/.war | `colectivizacion`, `dnlq_consulta` | Sí |
| Librerías internas | libs Scala publicadas a Nexus | No (nunca deployan, solo publican a Nexus) |
| Repos de infra/config | `CI-CD`, `docker`, `jenkins` (legacy) | No |
| Repos de documentación / templates | `templates` | No |
| Client apps (mobile/desktop) | BPos, GPos (Flutter) | No (fuera de alcance v2) |
| Repos experimentales / sandbox | POCs, tests | No |

Por qué el criterio es auditable:

- La presencia de `environment: production` en `deploy.json` es **verificable automáticamente** (un job que escanee la org).
- El allowlist de GH secrets se puede mantener sincronizado contra esa lista (manual al principio, con reconciliación automática si el volumen crece).
- Cumple ISO A.5.15 (need-to-know): un repo sin `environment: production` declarado no tiene motivo legítimo para ver `GCHAT_WEBHOOK_PRODUCTION`.

Por qué esto es un fail-safe contra errores, no solo contra ataques:

- Escenario: se agrega por error `environment: production` a un `deploy.json` de un repo experimental con `executable_path` apuntando a un container prod real. Sin allowlist el workflow podría ejecutarlo. Con allowlist, el repo no tiene el secret y el workflow falla explícitamente.

Caso "testing sí, prod nunca":

- Si existe un server app que deploya a testing/staging pero **nunca** va a producción (herramienta interna, banco de pruebas), requiere 2 allowlists separados: `testing-staging` más amplio, `production` más chico.
- Hipótesis preliminar: no existe hoy ese caso en BQN. Si existe, se documenta.

**Implicancias para Soporte.**

- Mantenimiento del allowlist: manual por Pablo/Bruno al onboarding de cada repo. Nadie más puede agregar repos (control A.8.2).
- Si Soporte detecta un repo que debería deployar y no lo hace (el workflow falla por secret faltante), contactar a Pablo/Bruno para incorporar al allowlist.

**Pedido a Soporte.**

> (Pregunta 1) ¿Existe hoy algún server app que esté en testing/staging pero que **nunca** vaya a ir a producción (herramienta interna, banco de pruebas, etc.)? Si sí, listar — va en allowlist de testing/staging pero NO en el de prod.
>
> (Pregunta 2) ¿Algún repo "en transición" (aún no prod pero lo será pronto) que convenga tratar distinto mientras tanto?

---

### 5.4 Sistemas piloto

**Propuesta.** Dos pilotos secuenciales antes del rollout masivo:

1. **Piloto 1 — `acp-api`** (scala-api / pekko). Ya validado en Hito 2 para build + publish de artifacts. En Hito 3 valida el patrón completo de deploy: descarga GH Release → escritura vía Docker API → restart vía Portainer → notificación Chat.
2. **Piloto 2 — `colectivizacion`** (tomcat / .war). Valida el segundo patrón principal de stack BQN (.war en tomcat).

Criterio de éxito **común a ambos pilotos** para promover al rollout masivo:

- [ ] ≥3 deploys consecutivos exitosos en testing.
- [ ] ≥1 deploy exitoso en staging.
- [ ] ≥1 rollback practicado (redeploy de un tag anterior vía `workflow_dispatch`).
- [ ] Soporte confirma operabilidad autónoma (un analista operativo ejecuta y monitorea un deploy end-to-end sin asistencia de Desarrollo).

**Análisis.**

Piloto 1: `acp-api` ya tiene infraestructura v2 (build reusable workflow, GH Releases con snapshots). Añadir el deploy encima es incremental.

Piloto 2 (por qué `colectivizacion` sobre `dnlq_consulta`): decisión de Pablo basada en conocimiento operativo del sistema. Ambos cumplen el criterio "tomcat/.war sin mucho riesgo" sugerido por Soporte en el relevamiento.

**Implicancias para Soporte.**

- Durante el piloto, los deploys v1 **se mantienen en paralelo** (Jenkins sigue funcionando). Si el piloto v2 falla, se retoma v1 sin drama.
- Soporte debe disponer de ventana para 3-5 deploys de prueba en testing durante 1-2 semanas por piloto. No es tiempo full-time; son deploys puntuales coordinados.
- El rollback practicado es **requisito** — no solo "el deploy exitoso funciona" sino "cuando algo sale mal, la recuperación funciona". ISO A.5.30 (continuidad).

**Pedido a Soporte.**

> ¿Está disponible una ventana operativa (próximas 2-3 semanas) para iterar 3-5 deploys testing de `acp-api` + 3-5 deploys testing de `colectivizacion`? ¿Algún hito operativo de BQN (cierre, feriado, release mayor) que convenga esquivar para programar los pilotos?

---

### 5.5 Approvers de producción y fusible SoD

**Propuesta.**

```yaml
GitHub Environment: production
  Required reviewers:
    - Pablo Zebraitis
    - Bruno Artola
    - Jonathan Correa Paiva
    - Elías Severino
  Prevent self-review: OFF   # ver análisis
  Required approvals: 1
  Wait timer: 0 min
  Deployment branches: protected tags matching v[0-9]*

GitHub Environment: staging
  Required reviewers: (vacío — auto-deploy)
  Deployment branches: release/**, hotfix/**

GitHub Environment: testing
  Required reviewers: (vacío — auto-deploy cuando auto_deploy: true)
  Deployment branches: develop
```

**Fusible de self-approval (alerta + justificación + registro):**

Un step adicional en el workflow de deploy producción detecta cuando el aprobador coincide con el originador del trigger. Si coinciden:

1. Notificación al canal `Deploy - Production`:
    ```text
    ⚠️ Self-approval detectado (ISO A.8.3 advisory)
    Deploy: <app> <tag> → production
    Originador: <usuario>
    Aprobador: <mismo usuario>
    Justificación operativa: <texto obligatorio>
    Registro: <link al run de GH Actions>
    ```
2. El campo "Justificación operativa" se pide como `workflow_dispatch input`. Si el aprobador coincide con el originador, el campo se valida como obligatorio (no puede estar vacío).
3. Log persistente del evento en el job output (retención 90 días default de GH Actions, configurable).
4. Revisión trimestral por ISO Officer (Pablo) en el comité del SGSI, para confirmar que los eventos de self-approval (si hubo alguno) estuvieron justificados.

**El fusible no bloquea el deploy.** Solo deja traza.

**Análisis.**

Tres opciones consideradas para el caso "Pablo en el pool":

| Opción | Descripción | Resultado |
|---|---|---|
| i. Pablo en approvers, sin restricción técnica, con fusible | Permite aprobar propios deploys, deja evidencia | **Elegida** |
| ii. Pablo fuera del pool para deploys prod | SoD cristalina, 3 approvers | Descartada |
| iii. "Prevent self-review" activado (bloqueo técnico) | GitHub bloquea self-approve | Descartada |

Razones:

- **Descartamos ii** (Pablo fuera del pool): con 4 approvers reales y equipo de 7, la probabilidad de que ninguno esté disponible ante un hotfix es baja pero no nula. Bloquear a Pablo técnicamente introduce **riesgo operativo de no poder desplegar un fix crítico** — riesgo mayor que una self-approval ocasional y auditada.
- **Descartamos iii** (bloqueo técnico "Prevent self-review"): en la práctica BQN no ha habido self-approvals (dato fáctico de v1). El fusible **es más valioso que el bloqueo** porque deja **evidencia positiva** de no-ocurrencia, más la alerta si ocurriera. Un bloqueo técnico no deja traza cuando falla silenciosamente.
- **Elegimos i con fusible:** ISO A.8.3 admite explícitamente **alternative controls** (monitoreo compensatorio) cuando el tamaño del equipo no permite SoD estricta. El fusible cumple esto literalmente.

Compromisos formales asociados a la decisión:

- La política interna es "no self-approve salvo excepción documentada" (aunque no esté bloqueado técnicamente).
- Pablo, como ISO Officer, asume el rol de supervisor de esta regla y se compromete a revisión trimestral del log de self-approvals en el comité de SGSI.
- Si ISO Officer detecta abuso del fusible (ej: self-approval rutinario), se escala a bloqueo técnico (Opción iii).

Exclusión del equipo de desarrollo:

- El equipo IDS Development (Santi, Nacho, Jose) **no entra al pool de approvers en v2**. Esto es regla explícita, no accidente. En v1 tampoco están, pero no estaba documentado como política.
- La separación dev / ops se mantiene estricta: dev escribe código, ops opera el deploy.

**Implicancias para Soporte.**

- Flujo típico de un deploy a prod:
    1. Alguien de los 4 approvers dispara `make-release` (workflow_dispatch) → crea tag `vX.Y.Z`.
    2. Tag dispara el workflow de deploy a production → pendiente de aprobación.
    3. Cualquiera de los otros 3 approvers aprueba → deploy procede.
    4. Si el mismo que disparó aprueba → fusible se activa, deploy procede con alerta visible y justificación registrada.
- Staging y testing no requieren aprobación humana (auto-deploy). Los tags de staging (`v*-rc.*`) ya son auditados por tag protection; los de testing (`v*-snapshot.*`) son efímeros.

**Pedidos a Soporte.**

> (1) ¿La lista de approvers (Pablo, Bruno, Jonathan, Elías) es correcta en v2?
>
> (2) ¿Una sola aprobación es suficiente, o consideran que operaciones críticas (eFactura, bsecurity-api) deberían requerir 2?
>
> (3) ¿De acuerdo con el mecanismo de fusible (alerta + justificación obligatoria + revisión trimestral por ISO Officer) como reemplazo de un bloqueo técnico rígido?
>
> (4) ¿Staging y testing auto-deploy sin aprobación humana les cierra operativamente? (Cualquier instalación puede marcarse `auto_deploy: false` si un caso específico lo requiere — ver 5.7.)

---

### 5.6 Paths de artefactos vía Docker API

**Propuesta.** `executable_path` en `deploy.json` es el path **dentro del container** donde cae el jar/war, no en el host. El workflow escribe mediante `PUT /containers/{id}/archive` a través del proxy Docker API de Portainer.

Ejemplos:

```json
// Caso Scala/Pekko
"executable_path": "/app/lib/acp-api.jar"

// Caso Tomcat WAR
"executable_path": "/usr/local/tomcat/webapps/colectivizacion.war"
```

**Análisis.**

v1 acopla el deploy al layout del host:

- Jars en el "home del container" (bind-mounted).
- Wars centralizados en `/opt/webapps` del host.

Mantener esa heterogeneidad en v2 obliga al pipeline a conocer la infraestructura. Desacoplar vía Docker API tiene ventajas:

- Al CI/CD no le importa cómo está montado el host.
- El path que el dev escribe en `deploy.json` es el path **que la app "ve"** dentro del container — más intuitivo.
- Cambiar un bind mount (ej: migración de `/opt/webapps` a otra ubicación) es transparente al deploy.

Edge case: **hot-reload de tomcat**. En v1, reemplazar un `.war` en `webapps/` puede desencadenar auto-explode/reload por tomcat. La propuesta 5.1 (restart siempre forzado) hace irrelevante este comportamiento: en v2 el restart es explícito, no dependemos de que tomcat detecte el cambio.

Dependencia: **esta propuesta requiere que Opción C del runner (consulta 6.1) sea viable.** Si Soporte confirma que `executable_path` está bind-mounted al container en todos los casos, Opción C funciona; si hay casos de paths no bind-mounted, caeríamos a SSH (Opción A) y esta propuesta seguiría siendo válida semánticamente (seguiría siendo path intra-container) pero la implementación usaría SCP en vez de Docker API.

**Implicancias para Soporte.**

- El dev que agrega una instalación a `deploy.json` escribe el path del container, no el path del host. Si Soporte coordina con el dev el valor, se necesita claridad de "qué path ve la aplicación al leer el jar/war".
- El mapping host ↔ container deja de ser responsabilidad del pipeline y queda 100% en el `docker-compose.yml` del stack.

**Pedido a Soporte.** Parte de la consulta 6.1 (arquitectura del runner); no requiere pregunta adicional aquí.

---

### 5.7 Auto-deploy opt-in per-instalación

**Propuesta.** Cada instalación de `deploy.json` declara explícitamente `auto_deploy: true` o lo omite. El default es `false` (solo deploy manual).

```yaml
installations:
  - id: acp-testing
    environment: testing
    stack: acp_services
    service: acp-api
    executable_path: /app/lib/acp-api.jar
    auto_deploy: true          # opt-in explícito

  - id: sga-testing-crl
    environment: testing
    stack: sga_services
    service: sga-testing-crl
    executable_path: /app/lib/sga.jar
    # sin auto_deploy → solo manual
```

**Mecánica.**

- **Auto-deploy ON:** workflow de deploy se dispara en `release.published` (filtrado por pattern de tag: `v*-snapshot.*` → testing; `v*-rc.*` → staging).
- **Auto-deploy OFF:** ese trigger se saltea esa instalación puntual. Deploy manual siempre disponible vía `workflow_dispatch`.
- **Production:** nunca auto-deploy, ya es regla dura (5.5); no necesita flag.

**Notificación "⏸️ deploy pendiente"** (nuevo caso en v2, no existe en v1):

Cuando se publica un snapshot/RC pero la instalación tiene `auto_deploy: false`, el workflow notifica al canal correspondiente:

```text
⏸️ Deploy manual pendiente
Repo: bqn-uy/sga-api
Ambiente: TESTING
Instalación: sga_testing_crl (sga_services / sga-testing-crl)
Versión disponible: v1.2.0-snapshot.015
Disparar deploy: <link directo al workflow_dispatch con tag pre-rellenado>
```

Enrutamiento de canales:

| Environment | Canal Google Chat |
|---|---|
| testing, staging | Deploy - Testing/Staging |
| production | Deploy - Production |

**Análisis.**

Relevamiento de Soporte confirmó que hoy en v1 **no hay auto-deploy por default**; es opt-in vía flag en `sistemas.json` (casos `sga_testing_crl`, `sga_testing_lpi` explícitamente OFF). La propuesta v2 preserva esta semántica exacta, trasladándola a `deploy.json`.

Granularidad del flag: per-instalación. Otras granularidades consideradas:

| Granularidad | Resultado |
|---|---|
| Per instalación | **Elegida** — máxima flexibilidad, refleja la realidad operativa |
| Per ambiente (`auto_deploy_testing: true`) | Descartada — no cubre el caso CRL/LPI (OFF dentro de testing) |
| Global por repo | Descartada — demasiado grosero |

**Implicancias para Soporte.**

- El comportamiento v2 es idéntico al v1 para instalaciones ya marcadas como no-auto-deploy: seguirán requiriendo deploy manual.
- **Nuevo:** cuando hay un snapshot/RC nuevo pendiente, Soporte recibe notificación automática en el canal. Hoy en v1 hay que chequear manualmente; en v2 el mensaje llega solo con link directo.

**Pedido a Soporte.**

> ¿El formato propuesto del mensaje `⏸️ Deploy manual pendiente` les sirve? ¿Prefieren incluir/excluir alguna información (ej: commit SHA, autor del commit, changelog)? Este formato se puede iterar sin cambios de schema.

---

## 6. Consultas pendientes ya enviadas al canal

Las dos siguientes son consultas ya formuladas en el canal de chat al equipo de Soporte. Se reproducen aquí para que puedan evaluarse en conjunto con el resto del documento. **La respuesta a estas dos consultas condiciona parte del diseño.**

### 6.1 Arquitectura del runner (A / B / C)

**Contexto.** El relevamiento marcó Opción B (un runner por host) por descartar NAS compartido, pero queremos validar si hay una alternativa mejor antes de provisionar N runners.

**Tres opciones identificadas:**

- **A) 1 runner único + SSH/SCP a los hosts.** Espejo del modelo Jenkins actual. Pros: 1 solo host para mantener. Contras: credenciales SSH nuevas a N hosts; el runner es SPOF.

- **B) 1 runner por host** (lo marcado en el relevamiento). Pros: acceso directo al FS local, sin SSH. Contras: provisioning y upgrade del runner × N hosts; superficie de credenciales distribuida (cada host-runner con su token o uno compartido que amplía blast radius), registración/rotación × N.

- **C) 1 runner único + Docker API vía Portainer** (sin SSH, sin per-host). Si `executable_path` está bind-mounted al container, el copy se hace con `PUT /containers/{id}/archive` contra la Docker API que Portainer ya proxya — mismo token que usaríamos para el restart.

    Pros de C:
    - Runner 100% network-only, vive en un solo host (docker-soporte).
    - Credenciales centralizadas: un único token Portainer cubre descarga + copia al container + restart. No aparece ninguna credencial nueva para mover el artifact a cada host.
    - Sin provisioning por host: sumar un sistema nuevo no requiere tocar infraestructura, solo su `deploy.json`.
    - Auditoría unificada: todo el deploy pasa por Portainer (ya es el punto de control actual).

**Pregunta concreta para decidir:**

> Para todos los server-apps actuales, ¿el `executable_path` está bind-mounted dentro del container? ¿O hay casos donde el path vive en el host pero NO está montado (ej `/opt/webapps` centralizado que varios tomcats bindean después)?
>
> - Si todos están bind-mounted → C es viable y es la más limpia.
> - Si hay casos tipo `/opt/webapps` centralizado → C no aplica para esos, y probablemente convenga A sobre B por overhead operativo.

---

### 6.2 Identificación de containers en `deploy.json`

**Contexto.** El relevamiento mencionó que la mayoría de containers se nombran automáticamente como `<stack>-<servicio>-<replica>` (ej `spa_services-spa-api-1`) y que el único stack con réplicas múltiples hoy es `tcp_server`.

Para que `deploy.json` no quede atado a nombres frágiles, la propuesta es identificar por stack + service (más opcionalmente réplicas), resolviendo el nombre real del container en runtime vía las labels de compose (`com.docker.compose.project` / `.service`), que son estables por contrato.

**Esquema propuesto:**

```yaml
installations:
  - environment: testing
    portainer_endpoint: docker-soporte
    stack: spa_services
    service: spa-api
    replicas: [1, 2]        # opcional; omitido = todas las del servicio
    executable_path: /opt/.../app.jar
```

**Dos preguntas para validar:**

> (1) ¿Confirman que **hoy** `tcp_server` es el único caso con múltiples réplicas, y que en el corto/mediano plazo no esperan sumar más stacks replicados? (Queremos dimensionar si el campo `replicas` es nice-to-have o algo que usaremos seguido.)
>
> (2) ¿Hay algún container que NO esté gestionado por un stack de compose (ej Portainer mismo, o contenedores standalone creados a mano)? Si es así, esos no tendrían labels de compose y habría que identificarlos por nombre explícito — queremos saber si vale soportar ese caso o si todos los server-apps están siempre dentro de un stack.

---

## 7. Consideraciones transversales

### 7.1 Controles ISO 27001 aplicados

Tabla consolidada del mapeo de decisiones a controles ISO. Sirve como base para documentación del SGSI.

| Control | Requisito | Aplicación en v2 |
|---|---|---|
| A.5.15 Access control | Principio de need-to-know | Allowlist de repos + Portainer Team scoping + folders Keeper segregados por nivel |
| A.5.17 Authentication information | Credenciales gestionadas | Keeper como source of truth; 3 secrets a rotar anualmente (viable con equipo de 7) |
| A.5.30 ICT continuity | Capacidad de recuperación | Rollback documentado (redeploy tag anterior); v1 Jenkins sigue como fallback durante transición |
| A.8.2 Privileged access rights | Gestionados formalmente | Allowlist controlado por Pablo/Bruno; Portainer Teams definidos por Soporte; Keeper roles |
| A.8.3 SoD | Separación de deberes (o alternative controls) | 3-way Keeper/GH/Portainer; equipo IDS fuera del deploy; fusible + revisión trimestral como alternative control |
| A.8.15 Logging | Trazabilidad de eventos | Keeper logs + GH Actions logs (90 días) + Google Chat audit trail + Portainer logs |
| A.8.25 Secure development | SDLC seguro | Branch protection; tag protection `v*`, `v*-rc.*`; security-scan action en CI |
| A.8.32 Change management | Cambios controlados y reversibles | Required reviewers prod; restart explícito; tag inmutable como identidad del change set |

### 7.2 Concurrencia de deploys

Propuesta: cada workflow de deploy usa `concurrency: deploy-${{ installation_id }}`. Esto implica:

- Dos pushes consecutivos al mismo ambiente/instalación se **encolan** (no se cancelan).
- Dos instalaciones distintas pueden deployar en paralelo (no se bloquean entre sí).
- Perder un deploy intermedio por cancelación sería peor que esperar 30 segundos al siguiente.

### 7.3 Rollback y recuperación

**Mecanismo.** `workflow_dispatch` del workflow de deploy con input `tag: vX.Y.Z-anterior`. No hay lógica nueva; es literalmente un deploy del tag anterior. El artifact ya existe en GitHub Releases (inmutable por tag protection), se descarga y se despliega igual que un deploy normal.

**Procedimiento a documentar para Soporte** (a expandir en un runbook):

1. Identificar el tag de la versión anterior estable (GH Releases del repo).
2. En GitHub Actions → Deploy workflow → Run workflow → especificar `tag: vX.Y.Z-anterior` + `environment: production`.
3. Aprobar el deploy como cualquier otro deploy prod.
4. Verificar sanidad del servicio.
5. **Si hubo migración de BD:** restaurar backup de BD antes de redeploy (procedimiento existente, no cambia en v2).

**ISO A.5.30.** El procedimiento debe estar documentado en el runbook de Soporte y probado al menos una vez por piloto antes del rollout (ver 5.4).

### 7.4 Retención y auditoría

- **Logs de GitHub Actions:** 90 días (default). Configurable hasta 400 días si el SGSI lo requiere. Propuesta: mantener default 90 días.
- **GitHub Releases:** permanentes hasta delete manual (tag protection en `v*` impide borrado accidental).
- **Portainer logs:** según política actual de Soporte.
- **Keeper logs:** según política actual de Keeper.
- **Google Chat mensajes:** retención según política Workspace BQN.

El cruce de los 4 orígenes permite reconstruir cualquier deploy en ≤90 días con detalle completo.

### 7.5 Fallos del sistema Portainer

Si Portainer está caído durante un deploy:

- El workflow falla explícitamente (HTTP error al token o timeout).
- Se envía notificación al canal correspondiente con el detalle del error.
- Soporte interviene manualmente: investigar Portainer, y una vez restaurado, reintentar el deploy (re-run del job en GH Actions).

No se implementa retry automático complejo. Un deploy fallido queda visible, Soporte actúa. Esto es más simple y auditable que una cadena de retries que podría enmascarar el problema real.

### 7.6 Requisitos de red del runner

Si se confirma Opción C del punto 6.1, el runner vive en `docker-soporte` (10.190.2.49) y requiere acceso saliente a:

- `api.github.com` (HTTPS 443) — operaciones GitHub API
- `objects.githubusercontent.com` (HTTPS 443) — descarga de release artifacts
- `docker-soporte.local.bqn.uy` (HTTPS/443 local) — Portainer API (local al host)
- Canal Google Chat webhooks (HTTPS 443) — notificaciones

**No se requieren** reglas Forti nuevas si el host ya tiene el acceso a internet habilitado y es el que hoy corre Portainer. Si más adelante aparece un endpoint Docker remoto fuera de 10.190.2.0, se habilita regla puntual.

---

## 8. Plan de rollout

Cronograma tentativo (a ajustar según disponibilidad operativa de Soporte).

| Fase | Actividad | Actores | Duración estimada |
|---|---|---|---|
| 0 | **Revisión y firma de este documento** | Bruno, Jonathan, Elías, Pablo | 1 semana |
| 1 | Resolver consultas 6.1 (runner) y 6.2 (containers) | Soporte + Pablo | Incluida en fase 0 |
| 2 | Provisioning del runner self-hosted en `docker-soporte` | Soporte + Pablo | 1-2 días |
| 3 | Implementación de workflows deploy v2 (composite actions + reusable workflows) | Pablo | 3-5 días |
| 4 | **Piloto 1 — `acp-api` en testing** | Pablo + Soporte | 1-2 semanas (iteración de deploys) |
| 5 | **Piloto 1 — `acp-api` en staging + rollback practicado** | Pablo + Soporte | 3-5 días |
| 6 | Validación de criterios de éxito piloto 1 | Bruno + Pablo (go/no-go) | 1 día |
| 7 | **Piloto 2 — `colectivizacion` en testing** | Pablo + Soporte | 1-2 semanas |
| 8 | **Piloto 2 — `colectivizacion` en staging + rollback practicado** | Pablo + Soporte | 3-5 días |
| 9 | Validación de criterios de éxito piloto 2 | Bruno + Pablo (go/no-go) | 1 día |
| 10 | **Rollout gradual por olas** al resto de server apps | Pablo + Soporte | 4-8 semanas |
| 11 | Retiro formal de Jenkins como sistema activo (queda como archivo) | Pablo + Soporte | 1 día |

Durante todas las fases, **Jenkins v1 sigue disponible como fallback** (decisión 7.3 del relevamiento).

---

## 9. Matriz de decisiones — tabla de revisión

Para facilitar la revisión. Soporte puede marcar cada fila con ✅ (conforme), ⚠️ (conforme con observaciones), o ❌ (no conforme + comentario).

| # | Decisión | Resumen | Sección | Conformidad |
|---|---|---|---|---|
| D1 | Restart siempre forzado | Incondicional tras escribir el artifact; sin flag | 5.1 | ⬜ |
| D2 | Modelo de credenciales Model C refinado | 3 org secrets + Keeper + Portainer Team scoping | 5.2 | ⬜ |
| D3 | Allowlist de repos prod por `environment: production` en `deploy.json` | Criterio objetivo, auditable | 5.3 | ⬜ |
| D4 | Pilotos `acp-api` + `colectivizacion` | Secuenciales, con criterios de éxito explícitos | 5.4 | ⬜ |
| D5 | Approvers prod + fusible SoD | 4 personas, self-approve permitido con alerta+justificación | 5.5 | ⬜ |
| D6 | Paths intra-container en `deploy.json` | Desacopla del layout del host | 5.6 | ⬜ |
| D7 | Auto-deploy opt-in per-instalación | Default `false`, notificación "⏸️ pendiente" automática | 5.7 | ⬜ |
| C1 | Arquitectura del runner (A/B/C) | Propuesta: C si bind mounts lo permiten | 6.1 | ⬜ respuesta a pregunta |
| C2 | Identificación de containers | Por stack+service+replicas (no por nombre) | 6.2 | ⬜ respuesta a preguntas |

---

## 10. Conformidades

Firma/visto de las partes indica alineamiento con las decisiones del documento. Reservas u observaciones específicas se indican por fila en la matriz anterior.

| Rol | Nombre | Fecha | Conformidad |
|---|---|---|---|
| Head of Operational Support | Bruno Artola | | |
| Analista Operativo | Jonathan Correa Paiva | | |
| Analista Operativo | Elías Severino | | |
| Technical Lead / ISO Officer | Pablo Zebraitis | | |

---

## Anexo A — Glosario abreviado

- **GA / GitHub Actions:** plataforma de CI/CD de GitHub, reemplaza a Jenkins en v2.
- **Composite action:** acción reutilizable dentro del repo `BQN-UY/CI-CD`.
- **Reusable workflow:** workflow parametrizable invocado desde múltiples repos.
- **SoD:** Separation of Duties, control ISO A.8.3.
- **Portainer Team:** agrupación en Portainer que define permisos de acceso a endpoints/containers.
- **Keeper folder:** carpeta compartida en Keeper Security con acceso segregado por rol.
- **`deploy.json`:** archivo `.github/deploy.json` por repo que declara instalaciones (environment, stack, service, path, flags).
- **Executable path:** path **dentro del container** donde vive el jar/war activo de la app.
- **Allowlist de org secrets:** lista explícita de repos de la org que tienen acceso a un secret org-level dado.

---

## Anexo B — Enlaces internos

- Spec técnico canónico v2: [`docs/v2-hito2-deploy-spec.md`](./v2-hito2-deploy-spec.md)
- Hoja de ruta v2 sin Jenkins: [`docs/v2-sin-jenkins-roadmap.md`](./v2-sin-jenkins-roadmap.md)
- Guía de migración Scala: [`docs/scala-migration-v2.md`](./scala-migration-v2.md)
- Relevamiento Soporte (PDF entregado 2026-04-14): archivo compartido por Drive.
