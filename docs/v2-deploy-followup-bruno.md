# Acta reunión 1:1 Pablo ↔ Bruno — Cierre D2 + D3 deploy v2

> **Fecha:** 2026-04-16
> **Duración:** ~15 min
> **Participantes:** Pablo Zebraitis (Technical Lead / ISO Officer), Bruno Artola (Head of Operational Support)
> **Objetivo:** Cerrar los dos puntos abiertos tras la revisión del 2026-04-15 (PDF firmado por Soporte): D2 "conforme con observaciones" y el hallazgo nuevo en D3 sobre "Producción interna".
> **Resultado:** Ambos puntos cerrados. Se desbloquea Hito 3.
> **Evidencia de acuerdo:** cierre del issue [#98](https://github.com/BQN-UY/CI-CD/issues/98) por parte de Bruno.

---

## Conclusión 1 — D2: Modelo de credenciales (cerrado ✅)

### Decisión

Se adopta el modelo **β (GH primario + Keeper backup)** para la gestión de los 3 org secrets (`PORTAINER_TOKEN_DEPLOY`, `GCHAT_WEBHOOK_TESTING_STAGING`, `GCHAT_WEBHOOK_PRODUCTION`).

### Propietarios operativos

- **Pablo + Bruno** son responsables de la creación, rotación y carga de los 3 secrets en GitHub y su respaldo en Keeper.
- **Jonathan queda designado como backup de Bruno.** Activación contingente: si Bruno no está disponible para una rotación programada o de incidente, Pablo + Jonathan operan el par con elevación temporal de Jonathan a admin GH org, revertida al regreso de Bruno.

### Regla operativa única

En cada rotación (anual o por incidente), se escribe primero al GH org secret y a continuación al folder Keeper correspondiente, **en la misma sesión operativa**. Un único patrón para los 3 secrets.

### Tabla 3-way SoD resultante

| Actor | Puede | No puede |
|---|---|---|
| Pablo / Bruno | Escribir GH secrets + escribir backup en Keeper | Crear tokens en Portainer |
| Jonathan (backup de Bruno) | Rutinario: leer backup Keeper testing-staging. Contingencia: operar como Bruno con elevación temporal a admin GH org | Rutinariamente, escribir GH secrets |
| Soporte | Crear/revocar tokens Portainer, configurar Teams | Ver el valor del secret en GH ni en Keeper |

### Por qué β (resumen)

- GitHub es el lugar donde el equipo ya opera; cargar el secret donde se consume elimina context-switching.
- El write-only de GH actúa como control natural (el valor activo es inviolable salvo sobrescritura intencional).
- Keeper tiene un rol único y claro (backup + ledger), no compite con GH.
- Audit trail doble e independiente: GH org audit log + Keeper access log.
- Portainer y Google Chat siguen siendo fuentes regenerables de último recurso.
- ISO A.5.17 cumplido con 3 capas visibles al auditor.

### Alcance y no-alcance

- **Alcance:** los 3 secrets nuevos de v2. No se toca v1: Jenkins y sus credenciales per-app siguen operando sin cambios.

### Acción de seguimiento

- Actualizar §5.2 del documento de revisión (`docs/v2-deploy-design-proposal-soporte.md`) con el modelo β — **hecho en esta iteración**.

---

## Conclusión 2 — D3: "Producción interna" (deferido)

### Contexto del hallazgo

En la revisión 2026-04-15 Soporte identificó una categoría no modelada por v2: herramientas internas del equipo de Soporte Operativo que no viven en `testing/staging` sino en "servidor de soporte o dev" y que no corresponderían al environment `production` tradicional (herramienta → cliente externo).

### Decisión

- **Fuera de alcance de v2.** Estas herramientas no entran en el rollout de Hito 3/4. Siguen operándose como hoy (Jenkins/manual según corresponda).
- **Dirección tentativa cuando se retome:** modelar un 4to environment `environment: soporte` en `deploy.json`, reflejando explícitamente que son herramientas internas del equipo de Soporte Operativo. Tendrá allowlist, approvers y canal Chat propios, independientes de `production`.
- Detalle de diseño queda abierto — se aborda en una etapa posterior con inventario concreto.

### Acción abierta (sin fecha comprometida)

- Armar inventario de qué herramientas entran en esta categoría (Pablo + Bruno) como insumo previo al diseño del environment `soporte`. Se tratará en una etapa futura.

### Acción de seguimiento

- Actualizar §5.3 del documento de revisión con la decisión de deferment — **hecho en esta iteración**.

---

## Siguientes pasos inmediatos

1. **Bruno cierra el issue [#98](https://github.com/BQN-UY/CI-CD/issues/98)** → queda como evidencia de acuerdo sobre D1–D7 + C1, C2 + cierre de D2 y D3.
2. **Pablo arranca Fase 2 del plan de rollout** (provisioning del runner self-hosted en `docker-soporte`) — sección §8 del documento de revisión.
3. **Issue #95** (Setup GitHub Environments, Secrets y Branch/Tag Protection) queda como el siguiente trabajo táctico — se puede empezar en paralelo con Fase 2.

---

## Anexos

- **Documento de revisión actualizado:** [`docs/v2-deploy-design-proposal-soporte.md`](./v2-deploy-design-proposal-soporte.md) (§5.2, §5.3, §9, §10 modificados post-reunión)
- **Spec técnico canónico v2:** [`docs/v2-hito2-deploy-spec.md`](./v2-hito2-deploy-spec.md)
- **Mapeo ISO afectado por D2:** A.5.15, A.5.17, A.8.2, A.8.3, A.8.15
