# Jenkins — Integración con CI/CD v2

Referencia de la integración entre GitHub Actions y Jenkins vía el plugin
[Generic Webhook Trigger (GWT)](https://plugins.jenkins.io/generic-webhook-trigger/).

---

## Visión general

Cada ambiente (`testing`, `staging`, `production`) tiene un job Jenkins dedicado
con su propio token GWT. La action `shared/jenkins-deploy-trigger` construye la URL con
el token como query param `?token=`, lo que hace que GWT rutee el request
exclusivamente al job que coincide con ese token.

```
GitHub Actions
  → POST /invoke?token=<TESTING_TOKEN>  → deploy-nexus-testing    ✅
                                         → deploy-nexus-staging    (token no coincide, ignora)
                                         → deploy-nexus-production (token no coincide, ignora)
```

---

## Org secrets en GitHub

Los secrets se configuran a nivel organización en
**BQN-UY → Settings → Secrets → Actions** y están disponibles en todos los
repositorios de la org sin necesidad de configurarlos repo a repo.

| Secret | Valor |
|---|---|
| `JENKINS_DEPLOY_URL` | `https://jenkins.bqn.uy/generic-webhook-trigger/invoke` |
| `JENKINS_DEPLOY_TESTING_TOKEN` | Token del job `deploy-nexus-testing` en Jenkins |
| `JENKINS_DEPLOY_STAGING_TOKEN` | Token del job `deploy-nexus-staging` en Jenkins |
| `JENKINS_DEPLOY_PRODUCTION_TOKEN` | Token del job `deploy-nexus-production` en Jenkins |

`JENKINS_DEPLOY_URL` es el mismo endpoint para los tres ambientes.
El token es lo único que difiere y es lo que GWT usa para rutear.

---

## Org variables en GitHub

Además de los secrets, cada repo de proyecto necesita la variable:

| Variable | Descripción |
|---|---|
| `SISTEMA` | Nombre del sistema/servicio (ej. `payments-api`). Lo usa Jenkins para saber qué artefacto desplegar. |

Se configura en **BQN-UY/\<repo\> → Settings → Variables → Actions** o a nivel org
si todos los repos usan el mismo nombre de sistema.

---

## Mecanismo de ruteo por token

El GWT plugin autentica y rutea en un solo paso usando el query param `?token=`.
No se usa `Authorization` header porque GWT no lo procesa por defecto.

```
POST https://jenkins.bqn.uy/generic-webhook-trigger/invoke?token=TOKEN_TESTING
Content-Type: application/json

{
  "environment":  "testing",
  "ref":          "abc1234...",
  "actor":        "pablo-zebraitis",
  "sistema":      "payments-api",
  "version":      "1.5.0+3-abc1234",
  "issue_number": ""
}
```

En el job Jenkins, `ENVIRONMENT` puede estar hardcodeado o derivarse del nombre
del job — **nunca se lee del payload** para determinar a qué ambiente desplegar.
El token es la única fuente de verdad del destino.

---

## Action: `shared/jenkins-deploy-trigger`

```yaml
- uses: BQN-UY/CI-CD/.github/actions/shared/jenkins-deploy-trigger@v2
  with:
    environment:  testing          # testing | staging | production
    service-url:  ${{ secrets.JENKINS_DEPLOY_URL }}
    token:        ${{ secrets.JENKINS_DEPLOY_TESTING_TOKEN }}
    sistema:      ${{ vars.SISTEMA }}           # opcional — nombre del servicio
    version:      ${{ steps.publish.outputs.version }}  # opcional — versión del artefacto
    issue-number: ""               # opcional — ticket asociado al deploy
```

### Inputs

| Input | Requerido | Descripción |
|---|---|---|
| `environment` | ✅ | `testing` \| `staging` \| `production` |
| `service-url` | ✅ | URL base del webhook GWT |
| `token` | ✅ | Token GWT — va como `?token=` en la URL |
| `sistema` | — | Nombre del sistema a desplegar |
| `version` | — | Versión del artefacto (dynver snapshot o tag release) |
| `installation` | — | Instalaciones destino (coma-separado). Vacío = `auto_deploy` en todas. Solo relevante en deploys manuales a production. |
| `issue-number` | — | Número de issue/ticket asociado |

---

## Uso por workflow

### `publish-and-deploy.yml` — deploy automático (testing / staging)

```yaml
- name: Publish snapshot to Nexus
  id: publish
  shell: bash
  run: |
    sbt publish
    echo "version=$(sbt -batch -error 'print dynver')" >> "$GITHUB_OUTPUT"
  env:
    NEXUS_USER:     ${{ secrets.NEXUS_USER }}
    NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
    NEXUS_URL:      ${{ secrets.NEXUS_URL }}

- name: Deploy to testing
  if: github.ref == 'refs/heads/develop' || startsWith(github.ref, 'refs/heads/release/')
  uses: BQN-UY/CI-CD/.github/actions/shared/jenkins-deploy-trigger@v2
  with:
    environment: testing
    service-url: ${{ secrets.JENKINS_DEPLOY_URL }}
    token:       ${{ secrets.JENKINS_DEPLOY_TESTING_TOKEN }}
    sistema:     ${{ vars.SISTEMA }}
    version:     ${{ steps.publish.outputs.version }}

- name: Deploy to staging
  if: startsWith(github.ref, 'refs/heads/hotfix/')
  uses: BQN-UY/CI-CD/.github/actions/shared/jenkins-deploy-trigger@v2
  with:
    environment: staging
    service-url: ${{ secrets.JENKINS_DEPLOY_URL }}
    token:       ${{ secrets.JENKINS_DEPLOY_STAGING_TOKEN }}
    sistema:     ${{ vars.SISTEMA }}
    version:     ${{ steps.publish.outputs.version }}
```

### `make-release.yml` — deploy a production (manual)

```yaml
- name: Deploy to production
  uses: BQN-UY/CI-CD/.github/actions/shared/jenkins-deploy-trigger@v2
  with:
    environment:  production
    service-url:  ${{ secrets.JENKINS_DEPLOY_URL }}
    token:        ${{ secrets.JENKINS_DEPLOY_PRODUCTION_TOKEN }}
    sistema:      ${{ vars.SISTEMA }}
    version:      ${{ steps.version.outputs.tag }}
    installation: ${{ inputs.installation }}   # vacío = auto_deploy
```

---

## Aislamiento de credenciales

El aislamiento entre ambientes se da en dos capas:

| Capa | Mecanismo |
|---|---|
| GitHub | `environment: production` en el job — requiere aprobación manual (reviewers) antes de ejecutar. `publish-and-deploy.yml` nunca tiene acceso al token de production. |
| Jenkins | Cada token corresponde a un único job. Un token de testing no puede disparar el job de production. |

### Configurar aprobación manual para production

En **BQN-UY/CI-CD → Settings → Environments → production**:
- Required reviewers: `equipo-soporte` (o el equipo que corresponda)

El job `make-release` declara `environment: production` — GitHub bloquea la
ejecución hasta que un reviewer apruebe desde la UI o por email.
Esto agrega una segunda línea de defensa antes del input stage de Jenkins.

---

## Jobs Jenkins requeridos

| Job | Token secret | Ambiente |
|---|---|---|
| `deploy-nexus-testing` | `JENKINS_DEPLOY_TESTING_TOKEN` | testing |
| `deploy-nexus-staging` | `JENKINS_DEPLOY_STAGING_TOKEN` | staging |
| `deploy-nexus-production` | `JENKINS_DEPLOY_PRODUCTION_TOKEN` | production |

Cada job recibe el payload JSON via GWT y tiene `ENVIRONMENT` hardcodeado
(o derivado del nombre del job) — no del campo `environment` del payload.

---

## Resumen del flujo de seguridad

```
GitHub Actions
  → token TESTING   → GWT rutea a deploy-nexus-testing   → ENVIRONMENT=testing  (fijo en job)
  → token STAGING   → GWT rutea a deploy-nexus-staging   → ENVIRONMENT=staging  (fijo en job)
  → token PROD      → GWT rutea a deploy-nexus-production → ENVIRONMENT=production (fijo en job)
```

El campo `environment` en el payload es informativo (para logs/auditoría).
El destino real lo determina el token, no el payload.
