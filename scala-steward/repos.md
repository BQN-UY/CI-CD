# Repositorios gestionados por Scala Steward

**Runner actual:** `BQN-UY/scala-steward-action` — no modificar hasta resolver el flujo v2 de librerías.

Este archivo es material de referencia y planificación para la futura migración del runner.
Cuando se migre, el workflow nuevo se agregará a `scala-steward-action` sin tocar los existentes.

Lista consolidada de repos + niveles de librerías para usar como base cuando se haga la migración.
Las dependencias públicas son responsabilidad de Dependabot (configurado en cada repo).
El scope de deps internas estará restringido por el `.scala-steward.conf` de cada proyecto (`com.bqn`, `com.zistemas`).

---

## Aplicaciones

Las aplicaciones no tienen dependencias entre sí — no requieren orden de ejecución.

- zistemas/vc-backoffice
- BQN-UY/sga
- BQN-UY/spa
- BQN-UY/backoffice
- BQN-UY/bsecurity
- BQN-UY/bol-server
- BQN-UY/scanner-server
- BQN-UY/remote-printer-client
- BQN-UY/cotizacion
- BQN-UY/dnlq
- BQN-UY/bcont
- BQN-UY/bfact
- BQN-UY/efactura
- BQN-UY/efactura-consulta
- BQN-UY/bol-web
- BQN-UY/colectivizacion

---

## Librerías — ejecución por niveles

Las librerías forman un árbol de dependencias internas. El criterio de niveles garantiza
que las actualizaciones se propaguen correctamente:

- **Nivel 0** — librerías sin dependencias internas (hojas del árbol)
- **Nivel N** — librerías que dependen de librerías del nivel N-1

Al ejecutar 3 veces por mes (días 1, 12 y 23), cada ejecución propaga las actualizaciones
un nivel más arriba: si el nivel 0 publica una nueva versión el día 1, el nivel 1 la
recibe el día 12, el nivel 2 el día 23, etc.

> **Nota:** el flujo CI/CD v2 para librerías aún no está definido. Este esquema de
> niveles fue diseñado para el modelo v1 y será revisado cuando se aborde la migración
> de librerías a v2. Ver decisión pendiente en memoria del proyecto.

### Nivel 0 — sin dependencias internas

- zistemas/common

### Nivel 1 — dependen de nivel 0

- zistemas/db
- zistemas/redmine
- zistemas/mail
- BQN-UY/vaadin
- BQN-UY/swing
- BQN-UY/ws
- BQN-UY/pdf
- BQN-UY/crypt
- BQN-UY/remote-printer-common

### Nivel 2 — dependen de nivel 1

- BQN-UY/fui
- BQN-UY/remote-printer-server
- BQN-UY/utils
- BQN-UY/common-libs
- BQN-UY/vaadin-app
- BQN-UY/banquinet-common-ui
