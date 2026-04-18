# Identidad de automatizaciones en GitHub — PAT vs Machine User vs GitHub App

> **Movido a `BQN-UY/banquinet`.**
>
> Este documento ahora vive en [`BQN-UY/banquinet/docs/v2-github-automation-identity.md`](https://github.com/BQN-UY/banquinet/blob/main/docs/v2-github-automation-identity.md).
>
> **Razón.** La decisión GitHub App vs PAT vs machine user aplica a cualquier automatización de la organización (Scala Steward, Dependabot, back-merges, bots futuros) — no solo al deploy v2. Se movió a `banquinet` donde corresponde su alcance organizacional. El trigger histórico fue CI/CD v2 libs (Fase 4), de ahí el prefijo `v2-` que puede limpiarse en una cleanup posterior.
>
> **Origen.** Doc creado en este repo en commit [`79bfdd3`](https://github.com/BQN-UY/CI-CD/commit/79bfdd3) (2026-04-16). Movido a banquinet en PR [`BQN-UY/banquinet#4`](https://github.com/BQN-UY/banquinet/pull/4) (2026-04-18). Review del contenido continúa en issue [`#96`](https://github.com/BQN-UY/CI-CD/issues/96) (pendiente de transfer a banquinet).
>
> **Este stub.** Se conserva para estabilidad de live links que apuntan a esta ruta. Puede eliminarse tras 1-2 ciclos de operación sin roturas.
