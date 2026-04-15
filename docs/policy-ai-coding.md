# Política de uso de asistentes de código IA

> **Estado.** Borrador para revisión interna (Pablo + equipo IDS + Bruno).
> **Entrada en vigor.** Tras aprobación conjunta.
> **Revisión próxima.** 12 meses desde aprobación.
> **Owner.** Pablo Zebraitis (Technical Lead / ISO Officer).

---

## 1. Propósito

BQN adopta formalmente una política sobre el uso de asistentes de código basados en IA (Claude, GitHub Copilot, Cursor, Tabnine, etc.) en el desarrollo de software.

**Objetivos:**

1. **Transparencia** — saber, cuando un cambio es sustancialmente generado por IA, que lo fue.
2. **Responsabilidad** — el humano que firma el merge es el autor responsable del código, independientemente de qué herramienta lo ayudó a producirlo.
3. **Trazabilidad** — que en una auditoría (ISO, DNLQ, DGI, revisión de incidente) podamos reconstruir cómo se desarrolló una porción de código.
4. **Productividad** — no prohibir ni limitar el uso de estas herramientas. Para un equipo de 3 desarrolladores, la IA es multiplicador de fuerza necesario.

La política se inspira en el [marco adoptado por la comunidad del kernel Linux en su versión 7.0 (abril 2026)](https://blog.segu-info.com.ar/2026/04/linus-torvalds-y-los-responsables-del.html), adaptado al tamaño y realidad de BQN.

---

## 2. Alcance

**Aplica a:**

- Todo el código fuente que se integra a ramas de proyectos de la organización BQN-UY: `main`, `develop`, `release/**`, `hotfix/**` y equivalentes.
- Commits creados por miembros del equipo IDS Development (Santi Villar, Ignacio Cabrera, Josefina Silbermann), Technical Lead (Pablo Zebraitis) y cualquier desarrollador que se incorpore.
- Todo asistente de IA capaz de generar, completar o refactorizar código (Claude, Copilot, Cursor, ChatGPT, Gemini, etc.).

**No aplica a:**

- Commits de herramientas automatizadas no-IA (dependabot, Scala Steward, renovate).
- Documentación, emails, tickets internos, presentaciones — por más que se usen herramientas IA para producirlos.
- Código experimental en repos personales (fuera de la org) o en branches sandbox claramente marcadas.

---

## 3. Principios

### 3.1 La IA es una herramienta, no un autor

El código asistido por IA es código del desarrollador que lo integra, igual que el código asistido por autocompletado del IDE o por copy-paste de Stack Overflow. **La responsabilidad técnica y legal siempre recae en el humano que hizo el merge.**

### 3.2 Transparencia sobre uso sustancial

Cuando una porción significativa de un commit fue generada por IA (no solo autocompletado trivial de una línea), **se declara explícitamente vía el trailer `Assisted-by:`** en el mensaje de commit. Ver §6 para el formato.

### 3.3 Sin self-delegación de responsabilidad

Está explícitamente rechazado atribuir defectos, errores o problemas de seguridad a la IA como justificación. "Lo generó Claude/Copilot" no es una causa raíz válida en post-mortem; la causa raíz es que el desarrollador no detectó/revisó adecuadamente la salida de la herramienta antes de mergear.

### 3.4 Uso pragmático, no prohibición

BQN reconoce que asistentes IA mejoran productividad y calidad en tareas como boilerplate, refactors, migraciones, escritura de tests, y documentación. **Se encoraja su uso** dentro del marco de esta política. Prohibir es impracticable (como intentar prohibir el uso de Stack Overflow) y contraproducente.

---

## 4. Prácticas mandatorias

1. **Todo merge a `main` / `develop` pasa por Pull Request con al menos una aprobación humana.**

   Ninguna herramienta IA puede mergear código directamente en ningún escenario. Esto es el control principal — vale igual que la política de PR anterior a esta, solo que aquí se explicita porque algunas herramientas IA (agents) pueden integrar vía API.

2. **La revisión del PR es realizada por un humano distinto del autor.**

   Asistentes IA pueden sugerir comentarios de revisión; no reemplazan la revisión humana.

3. **Declaración del uso de IA en cambios sustanciales vía trailer `Assisted-by:`** (ver §6).

4. **Ningún `Signed-off-by:` ni commit attribution puede indicar a una IA como autor.**

   Los commits llevan la identidad del humano que los produjo (su nombre/email de git config). Las Apps de GitHub (ej: `bqn-cicd-automation[bot]` cuando se implemente) son una excepción aceptada, ya que tienen identidad de bot declarativa, no suplantan a humanos.

5. **No pegar secretos ni datos sensibles en prompts de IA.**

   Tokens, passwords, datos personales de clientes, información comercialmente sensible — no deben formar parte del contexto enviado a servicios IA externos. Esto ya es política general de seguridad; se reitera aquí por relevancia.

---

## 5. Módulos críticos — controles reforzados

Hay módulos cuyo fallo tiene impacto alto en DNLQ, DGI, seguridad, o continuidad del negocio. Para PRs que modifican estos módulos:

**Requisito: 2 aprobaciones humanas en el PR, independientemente de si hubo uso de IA o no.**

| Repo / módulo | Razón |
|---|---|
| `bsecurity-api` | Seguridad de sesiones y autenticación |
| `fui-api` (módulos eFactura) | Integración DGI, datos fiscales |
| `claro-bridge` | Integración con pasarelas externas |
| Cualquier módulo que maneje transacciones DNLQ (venta de juego) | Continuidad operativa + auditoría |
| Cualquier módulo que genere comprobantes fiscales | Requisito DGI |

Justificación: esta regla **no distingue entre código AI-assisted y código hand-written**. El riesgo del módulo existe independientemente de quién/cómo lo escribió. Una regla del tipo "2 approvals solo si hay trailer" es fácil de esquivar (no poner el trailer) y además diferencia controles donde no debería haber diferencia.

El listado es revisable. Ampliar o reducir requiere PR al presente documento, aprobado por Pablo + Bruno.

---

## 6. Convención del trailer `Assisted-by`

### 6.1 Cuándo usarlo

**Sí:**
- Archivos nuevos mayormente generados por IA (ej: un nuevo endpoint, una clase DTO, un test completo).
- Refactors significativos donde la IA hizo la propuesta y el humano la aprobó con ajustes menores.
- Migraciones automáticas (ej: IA convierte código Java → Scala o actualiza sintaxis).
- Scripts de análisis o utilidades generadas end-to-end por IA.

**No:**
- Autocompletado de una línea o de un nombre de variable.
- Sugerencias rechazadas que llevaron al humano a escribir algo distinto.
- Debugging asistido por IA donde la corrección final la escribió el humano.
- Consultas tipo "cómo se hace X en Scala" donde la respuesta guió pero no se copió literal.

**Principio de discernimiento:** si un revisor futuro investigando un bug querría saber que esa porción fue generada por IA → poné el trailer. Si no cambiaría su análisis → no hace falta.

### 6.2 Formato

Sintaxis básica:

```
Assisted-by: <herramienta>[:<modelo>]
```

Ejemplos válidos:

```
Assisted-by: Claude:claude-opus-4-6
Assisted-by: Copilot
Assisted-by: Cursor
Assisted-by: ChatGPT:gpt-4o
Assisted-by: Gemini
```

Si usaste múltiples herramientas en el mismo commit, múltiples líneas:

```
Assisted-by: Claude:claude-opus-4-6
Assisted-by: Copilot
```

Si la herramienta que usás tiene un modelo propio (Claude, ChatGPT), declaralo. Si no (Copilot, Cursor que orquestan modelos por detrás), basta el nombre de la herramienta.

### 6.3 Ubicación en el commit

Va en el **trailer** (al final del mensaje, separado del cuerpo por línea en blanco), igual que `Signed-off-by:` o `Co-authored-by:`:

```
feat(acp-api): agregar endpoint /health con checks de BD y Redis

El endpoint devuelve 200 si ambos backends responden en menos
de 500ms, 503 caso contrario. Usado por el load balancer para
decisiones de routing.

Assisted-by: Claude:claude-opus-4-6
```

### 6.4 Validación

**No hay bloqueo automático de merge por ausencia del trailer.** La adopción es por convención y ética profesional, no por enforcement técnico.

Razón: un workflow que valide presencia del trailer fuerza dos caminos negativos:
- Falsos positivos bloqueantes (commit pequeño genuino marcado como "sospechoso").
- Incentiva no usar IA o agregar trailer innecesariamente, ninguna mejora real.

Lo que sí se hace: **revisión periódica** (ver §7).

---

## 7. Revisión y control

### 7.1 Revisión por PR

Mecanismo estándar. Sin cambios frente a la práctica actual.

### 7.2 Revisión trimestral por ISO Officer

Pablo (ISO Officer) realiza revisión trimestral con:

- Conteo de PRs mergeados en el trimestre.
- Porcentaje con `Assisted-by` presente.
- Correlación cualitativa: ¿hubo incidentes/bugs abiertos en módulos modificados recientemente? De esos, ¿cuál fue el mix de trailers?

Objetivo de la revisión: detectar tendencias, no auditar cada PR. El trimestre es la granularidad mínima para que los números tengan sentido con volumen BQN.

### 7.3 Consecuencias de incumplimiento

La política es de adopción voluntaria con responsabilidad personal. Si un desarrollador omite sistemáticamente el trailer en casos donde debería ponerlo:

1. Conversación directa con el desarrollador (Pablo + dev afectado).
2. Recordatorio de la política y casos donde aplica.
3. Si persiste: escalar al Technical Lead + PM (misma persona hoy).

No hay sanciones disciplinarias automáticas derivadas de esta política. La herramienta de cumplimiento es la cultura, no la burocracia.

### 7.4 Casos de abuso

Distinto del incumplimiento del trailer es el **abuso** (usar IA para producir código no revisado y mergear bajo pretexto de urgencia, o tapar la fuente real). Estos casos se manejan por vía normal de revisión de código + política de RRHH de BQN. Esta política no añade capa nueva para eso.

---

## 8. Roles y responsabilidades

| Rol | Responsabilidad respecto a esta política |
|---|---|
| Desarrollador IDS (Santi, Nacho, Jose, devs futuros) | Seguir los 5 principios de §4; usar el trailer cuando aplique (§6); no pegar secretos en prompts (§4.5); revisar código de otros en PRs |
| Technical Lead / ISO Officer (Pablo) | Owner del documento; revisión trimestral (§7.2); actualización del listado de módulos críticos (§5); canal para dudas y reportes |
| Head of Operational Support (Bruno) | Revisor del documento; validador de que la política no bloquea operación; escalación en casos que requieran visión operativa |
| Soporte Operativo (Jonathan, Elías) | No aplican directamente (no escriben código de producto); contexto de la política como parte de la cultura BQN |

---

## 9. Mapeo a controles ISO 27001:2022

| Control | Aplicación en esta política |
|---|---|
| A.5.37 Documented operating procedures | Este documento es un procedimiento operativo documentado |
| A.6.3 Information security awareness, education and training | La política se comunica durante onboarding y se vincula desde README principal del org |
| A.8.3 Separation of duties | PR review por humano distinto del autor (§4.2) |
| A.8.25 Secure development lifecycle | Reforzado: revisión humana + 2 approvals en módulos críticos (§5) |
| A.8.28 Secure coding | La política refuerza que el humano es responsable de la salida, incluyendo aspectos de seguridad |
| A.8.29 Security testing in development | No afecta directamente — los tests automatizados corren igual sobre código AI o humano |
| A.8.32 Change management | Alineado con branch/tag protection y GH Environments (ver spec v2) |

---

## 10. Casos borde y FAQ

**Q1. Usé GitHub Copilot para completar una función entera. ¿Trailer?**
Sí. Función entera = cambio sustancial.

**Q2. Claude me ayudó a entender un bug y terminé escribiendo la corrección a mano, con el enfoque que Claude sugirió. ¿Trailer?**
No. El código es tuyo. La asistencia intelectual no requiere declaración.

**Q3. Uso Cursor con modo "agent" que genera patches y abre PRs automáticamente. ¿Cómo declaro?**
El PR debe tener el trailer (`Assisted-by: Cursor:<modelo si aplica>`) y la aprobación humana estándar. Si el "agent" mergea directo → viola §4.1.

**Q4. IA me generó los datos de test de un módulo; el código productivo lo escribí yo. ¿Trailer en el commit de los tests?**
Sí. Los tests son código también. Trailer en el commit que agregue los tests (puede ser commit separado del productivo).

**Q5. Olvidé poner el trailer. ¿Qué hago?**
Si el PR no está mergeado → `git commit --amend` o rebase para agregarlo. Si ya está mergeado → no vale reescribir historia; dejar constancia en un comentario del PR ("este cambio fue assisted-by Claude, olvidé trailer") y tenerlo presente para la próxima.

**Q6. Estoy pair-programming con un colega y ambos usamos IA. ¿Quién lo declara?**
Quien haga el commit y sign-off. Si ambos contribuyeron con IA, el trailer único cubre el commit — no se duplica por autor.

**Q7. ¿Esta política aplica a los workflows de GitHub Actions que escribo?**
Sí. El código de los workflows es código BQN. Los workflows que tocan CI/CD son especialmente sensibles — considerarlos como candidatos a 2 approvals si afectan seguridad del pipeline.

---

## 11. Referencias

- **Inspiración:** [Linux Kernel 7.0 — política oficial sobre código asistido por IA (abril 2026)](https://blog.segu-info.com.ar/2026/04/linus-torvalds-y-los-responsables-del.html).
- **ISO 27001:2022** — controles Anexo A referenciados en §9.
- **Resoluciones DNLQ y DGI** — vigentes sobre auditabilidad de software relacionado a juego y facturación electrónica; esta política las refuerza pero no agrega requisitos nuevos.
- **Spec de CI/CD v2:** [`v2-hito2-deploy-spec.md`](./v2-hito2-deploy-spec.md) — modelo de branch/tag protection y Environments relacionados.
- **Identidad de automatizaciones:** [`v2-github-automation-identity.md`](./v2-github-automation-identity.md) — `bqn-cicd-automation[bot]` es la única excepción aceptada de "commits no humanos".

---

## 12. Historial de revisiones

| Versión | Fecha | Cambio | Autor |
|---|---|---|---|
| 0.1 | 2026-04-15 | Borrador inicial | Pablo Zebraitis |
