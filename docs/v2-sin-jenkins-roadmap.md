# Hoja de ruta: v2 sin Jenkins (Escenario C)

A partir de 2026-04-13, la dirección de v2 es **eliminar la dependencia de Jenkins**, alineada con el Escenario C del informe `~/projects/bqn/jenkins/docs/informe-jenkins-2026-04.md` (§10).

## Principios

- **v1 + Jenkins quedan congelados** como fallback durante la transición. No se modifican.
- **v2 publica artefactos pero NO deploya** hasta que esté el mecanismo GA-native.
- Los proyectos migrados a v2 viven en **estado "publish-only"** durante el gap entre Hito 1 y Hito 3.
- El composite `shared/jenkins-deploy-trigger` **no se borra** — sigue siendo válido para repos en v1 y como referencia.

## Hitos

### Hito 1 — Cleanup workflows v2 ✅ (este PR)

Quitar Jenkins de los reusable workflows existentes y separar concerns:

- `scala-api-publish-deploy.yml` → renombrado a `scala-api-publish.yml` (sin steps de deploy)
- `scala-api-make-release.yml` → quitado el step "Deploy to production"
- Templates renombrados: `templates/scala-api/publish-and-deploy.yml` → `templates/scala-api/publish.yml`
- Inputs `installation` y `sistema` removidos (sólo aplicaban al deploy)

**Resultado**: v2 publica artefactos a Nexus + crea releases en GitHub. No deploya.

### Hito 2 — Diseño deploy GA-native (pendiente relevamiento)

Tres preguntas a resolver antes de escribir código:

1. **Self-hosted runner GA**: ¿dónde se instala? Candidatos: `DEPLOY_IP`, otro host con red interna, o una VM nueva. El runner necesita acceso a Portainer + DBs + NAS2.
2. **Mecanismo de deploy**: tres opciones limpias:
   - **Portainer API** (HTTP + token) — si los servicios corren en containers gestionados por Portainer
   - **SSH + `docker pull && restart`** — más simple, requiere SSH y Docker en el host destino
   - **SCP + systemd** — para JARs standalone (sin containers)
3. **Modelo de instalaciones**: v1 maneja `sistemas.json` con N instalaciones por sistema. ¿v2 mantiene ese mapping o lo reemplaza?

**Output**: spec corto que define `scala-api-deploy.yml` + composite(s) nuevos.

### Hito 3 — Implementar deploy GA-native (pendiente Hito 2)

Una vez resueltas (1)(2)(3): instalar runner, implementar workflow, validar end-to-end en acp-api. Ahí acp-api pasa a tener flujo completo v2 sin Jenkins.

### Hito 4 — Migrar proyectos v1 → v2 progresivamente (pendiente Hito 3)

Criterio de orden: **bajo riesgo primero** (1 instalación, sin producción). `sga` (16 instalaciones) y `efactura` (10) al final. Por proyecto, el PR de migración replica el que se hizo en acp-api#11:

- Copiar templates v2 a `.github/workflows/` (`ci.yml`, `publish.yml`, `make-release.yml`, `start-release.yml`, `start-hotfix.yml`, `cleanup-snapshots.yml`, `update-next-bump.yml`, `setup-labels.yml`)
- Crear `.github/next-bump` con `minor`
- Limpiar `build.sbt`: remover `publishTo`, `dynverSeparator`, `dynverSonatypeSnapshots`, `nexusUrl`; conservar `credentials` + `NEXUS_USER/PASSWORD` (necesarios para RESOLVER libs internas de Nexus privado)
- Configurar tag protection (GH Settings → Tag protection): `v[0-9]*` y `v*-rc.*` protegidos
- Primer deploy de prueba

### Hito 5 — Apagar deploy v1 (pendiente Hito 4)

Cuando ningún proyecto use deploy v1: eliminar `scala-deploy-*.yml` del repo CI-CD y evaluar si Jenkins queda solo con IDH (converge a Escenario B mínimo o desaparece si IDH también migra).

## Estado actual

| Hito | Estado |
|---|---|
| 1 — Cleanup workflows v2 | ✅ Completado (PR #82) |
| 2 — Spec del deploy GA-native | ✅ Completado (PR #83); §7 del spec (server apps → GH Releases) también ejecutado (PR #85/86) y validado en acp-api (PR #11) |
| 2bis — Respuestas Soporte/IDS (§5.1, §5.2, §5.3) | ⏳ Pendiente relevamiento (input humano) |
| 3 — Implementar deploy GA-native | ⏳ Bloqueado por Hito 2bis |
| 4 — Migrar proyectos a v2 | ⏳ Bloqueado por Hito 3 |
| 5 — Apagar deploy v1 | ⏳ Bloqueado por Hito 4 |

## Modelo v2 operativo hoy (server apps)

Tras PR #85, los server apps tienen:
- `publish.yml` en cada push → GH pre-release `v<NEXT>-snapshot.NNN` (develop) o `vX.Y.Z-rc.NNN` (release/hotfix) con JAR assembly adjunto
- `make-release.yml` manual → release final `vX.Y.Z` + back-merge + reset `.github/next-bump`
- `cleanup-snapshots.yml` cron daily → conserva últimos 3 snapshots por target
- `update-next-bump.yml` en PR merged con label `breaking-change` → escala a `major`

Proyectos migrados: **acp-api** (validado end-to-end con `v0.2.0-snapshot.001`).

## Implicancias inmediatas para repos v2

- **acp-api**: queda en publish-only (publica artefactos a GH Releases pero no deploya). Su auto-deploy a testing/staging vuelve cuando Hito 3 esté listo. Como no está en producción, el gap es aceptable.
- **Nuevas migraciones**: posibles ahora para proyectos que acepten explícitamente vivir en publish-only durante el gap hasta Hito 3. Para proyectos en producción activa, pausar hasta Hito 3.
