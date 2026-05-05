#!/usr/bin/env python3
"""
Genera dos artefactos a partir del scan de repos de la org:

  docs/inventory.md (humano):
    1. Estado de migración v2 por repo (✅/🟡/🔴/⚪)
    2. Inventario agregado de deploys (desde cada .github/deploy.json)
    3. Validación cruzada — colisiones de la cuádrupla
       (portainer_endpoint, portainer_stack, portainer_service, portainer_replica)
       y violaciones de schema (cada deploy.json validado contra
       schemas/deploy.schema.json)
    4. Grafo de libs internas (publishers + consumers)

  config/lib-graph.json (máquina, consumido por scala-lib-make-release):
    { "publishers": { "BQN-UY/fui": {"groupId": "com.bqn", "artifactId": "fui"}, ... },
      "consumers":  { "BQN-UY/fui": ["BQN-UY/acp-api", ...], ... } }

Clasificación de migración (spec §4.11):
  ✅ v2 completo      — tiene .github/deploy.json  + workflows usan @v2
  🟡 v2 publish-only  — workflows usan @v2  + sin deploy.json
  🔴 v1 legacy        — workflows invocan scala-deploy-* / scala-make-release-* / scala-publish-*
  ⚪ N/A              — repo sin workflows de deploy

Requiere: env vars GH_TOKEN (PAT con repo:read sobre la org) y ORG (default BQN-UY).
Dependencia: jsonschema (Draft 2020-12). Usa `gh api` para todas las llamadas a GitHub.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

ORG = os.environ.get("ORG", "BQN-UY")
OUTPUT = Path(os.environ.get("OUTPUT", "docs/inventory.md"))
GRAPH_OUTPUT = Path(os.environ.get("GRAPH_OUTPUT", "config/lib-graph.json"))
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/deploy.schema.json"


def load_schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


SCHEMA_VALIDATOR: Draft202012Validator = load_schema_validator()

# Orgs Maven consideradas internas para el grafo de libs.
# Configurable via env INTERNAL_GROUPS (CSV), default cubre los dos en uso.
INTERNAL_GROUPS: tuple[str, ...] = tuple(
    g.strip() for g in os.environ.get("INTERNAL_GROUPS", "com.bqn,com.zistemas").split(",")
    if g.strip()
)

# Regex para parsear build.sbt (heurístico, line-based — no parsea sbt completo).
RE_NAME = re.compile(r'^\s*name\s*:=\s*"([^"]+)"', re.MULTILINE)
RE_ORG = re.compile(
    r'^\s*(?:ThisBuild\s*/\s*)?organization\s*:=\s*"([^"]+)"',
    re.MULTILINE,
)
# "groupId" %% "artifactId" % "X.Y.Z"  — captura groupId y artifactId.
RE_LIBDEP = re.compile(r'"([\w.-]+)"\s*%%\s*"([\w.-]+)"\s*%\s*"[^"]+"')

# Patrones que detectan uso de workflows de este mismo repo (CI-CD).
RE_V2 = re.compile(r"BQN-UY/CI-CD/\.github/workflows/[a-z0-9_-]+\.yml@v2")
RE_V1 = re.compile(
    r"BQN-UY/CI-CD/\.github/workflows/"
    r"(scala-deploy-|scala-make-release-|scala-publish-snapshot-|scala-ci\.yml)"
)


def sh(args: list[str], *, quiet_on_fail: bool = False) -> str:
    """Run a subprocess, return stdout. Raise on error.
    quiet_on_fail: no print stderr when the process fails (for expected 404s)."""
    try:
        r = subprocess.run(args, check=True, capture_output=True, text=True)
        return r.stdout
    except subprocess.CalledProcessError as e:
        if not quiet_on_fail:
            sys.stderr.write(f"ERROR running {args}:\n{e.stderr}\n")
        raise


def gh_api(path: str, *, paginate: bool = False, quiet_on_fail: bool = False) -> str:
    args = ["gh", "api", path]
    if paginate:
        args.append("--paginate")
    return sh(args, quiet_on_fail=quiet_on_fail)


@dataclass
class RepoState:
    name: str
    archived: bool
    state: str = "unknown"  # v2_full | v2_publish | v1_legacy | na
    app_type: str | None = None
    deploy_json: dict | None = None
    schema_errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # Grafo de libs internas (poblado al parsear build.sbt; None si no es Scala)
    publishes: tuple[str, str] | None = None  # (groupId, artifactId) si publica como lib interna
    depends_on: list[tuple[str, str]] = field(default_factory=list)  # [(groupId, artifactId), ...]


def list_repos(org: str) -> list[dict]:
    out = gh_api(f"orgs/{org}/repos?per_page=100", paginate=True)
    # `gh api --paginate` concatenates pages as separate JSON arrays.
    repos: list[dict] = []
    # Split concatenated arrays: gh emits `][` between pages, normalize.
    normalized = out.replace("][", ",")
    for item in json.loads(normalized):
        repos.append(item)
    return repos


def get_file(org: str, repo: str, path: str) -> str | None:
    """Return file content as string, or None if not found."""
    try:
        raw = gh_api(f"repos/{org}/{repo}/contents/{path}", quiet_on_fail=True)
    except subprocess.CalledProcessError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list) or "content" not in data:
        return None
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def list_workflow_files(org: str, repo: str) -> list[str]:
    try:
        raw = gh_api(f"repos/{org}/{repo}/contents/.github/workflows", quiet_on_fail=True)
    except subprocess.CalledProcessError:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    return [it["name"] for it in items if it.get("name", "").endswith((".yml", ".yaml"))]


def parse_sbt(content: str) -> tuple[tuple[str, str] | None, list[tuple[str, str]]]:
    """Extrae (publishes, depends_on) de un build.sbt.

    publishes: (groupId, artifactId) si declara `name :=` y `organization :=`
               en una org interna. None si no califica como lib publisher.
    depends_on: lista de (groupId, artifactId) con orgs internas referenciadas
                en `libraryDependencies` (deduplicada, sin versión).
    """
    name_m = RE_NAME.search(content)
    org_m = RE_ORG.search(content)
    publishes: tuple[str, str] | None = None
    if name_m and org_m and org_m.group(1) in INTERNAL_GROUPS:
        publishes = (org_m.group(1), name_m.group(1))

    deps: set[tuple[str, str]] = set()
    for m in RE_LIBDEP.finditer(content):
        gid, aid = m.group(1), m.group(2)
        if gid in INTERNAL_GROUPS:
            deps.add((gid, aid))
    # Una lib no se considera consumer de sí misma.
    if publishes:
        deps.discard(publishes)

    return publishes, sorted(deps)


def classify(org: str, repo: str) -> RepoState:
    state = RepoState(name=repo, archived=False)

    dj_raw = get_file(org, repo, ".github/deploy.json")
    if dj_raw:
        try:
            state.deploy_json = json.loads(dj_raw)
            state.app_type = state.deploy_json.get("application_type")
        except json.JSONDecodeError:
            state.notes.append("deploy.json no parsea como JSON")

    if state.deploy_json is not None:
        for err in sorted(SCHEMA_VALIDATOR.iter_errors(state.deploy_json), key=lambda e: list(e.path)):
            location = ".".join(str(p) for p in err.path) or "(root)"
            state.schema_errors.append(f"`{location}`: {err.message}")

    workflows = list_workflow_files(org, repo)
    uses_v2 = False
    uses_v1 = False
    for wf in workflows:
        content = get_file(org, repo, f".github/workflows/{wf}")
        if not content:
            continue
        if RE_V2.search(content):
            uses_v2 = True
        if RE_V1.search(content):
            uses_v1 = True

    if state.deploy_json and uses_v2:
        state.state = "v2_full"
    elif uses_v2:
        state.state = "v2_publish"
    elif uses_v1:
        state.state = "v1_legacy"
    elif not workflows:
        state.state = "na"
        state.notes.append("sin workflows")
    else:
        state.state = "na"

    # Grafo de libs: parsear build.sbt si existe.
    sbt = get_file(org, repo, "build.sbt")
    if sbt:
        state.publishes, state.depends_on = parse_sbt(sbt)

    return state


def build_lib_graph(states: list[RepoState], org: str) -> dict:
    """Construye el grafo publishers/consumers a partir de los RepoState parseados."""
    publishers: dict[str, dict[str, str]] = {}
    coord_to_repo: dict[tuple[str, str], str] = {}
    for s in states:
        if s.publishes:
            full = f"{org}/{s.name}"
            gid, aid = s.publishes
            publishers[full] = {"groupId": gid, "artifactId": aid}
            coord_to_repo[s.publishes] = full

    consumers: dict[str, list[str]] = {full: [] for full in publishers}
    for s in states:
        consumer_full = f"{org}/{s.name}"
        for coord in s.depends_on:
            lib_full = coord_to_repo.get(coord)
            if lib_full and consumer_full not in consumers[lib_full]:
                consumers[lib_full].append(consumer_full)
    for k in consumers:
        consumers[k].sort()

    return {"publishers": publishers, "consumers": consumers}


STATE_ICON = {
    "v2_full":    "✅ v2 completo",
    "v2_publish": "🟡 v2 publish-only",
    "v1_legacy":  "🔴 v1 legacy",
    "na":         "⚪ N/A",
}


def render(states: list[RepoState], lib_graph: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("# Inventario v2 (generado automáticamente)")
    lines.append("")
    lines.append(f"_Última actualización: {now} · org: `{ORG}`_")
    lines.append("")
    lines.append("Generado por `.github/workflows/inventory.yml` (cron semanal). No editar a mano. Fuente: `scripts/build-inventory.py`.")
    lines.append("")

    # Sección 1: estado de migración
    lines.append("## 1. Estado de migración v2")
    lines.append("")
    counts = {"v2_full": 0, "v2_publish": 0, "v1_legacy": 0, "na": 0}
    lines.append("| Repo | Estado | `application_type` | Notas |")
    lines.append("|---|---|---|---|")
    order = {"v2_full": 0, "v2_publish": 1, "v1_legacy": 2, "na": 3}
    for s in sorted(states, key=lambda r: (order.get(r.state, 99), r.name)):
        counts[s.state] += 1
        notes = "; ".join(s.notes) if s.notes else ""
        app = f"`{s.app_type}`" if s.app_type else ""
        lines.append(f"| [{s.name}](https://github.com/{ORG}/{s.name}) | {STATE_ICON[s.state]} | {app} | {notes} |")
    lines.append("")
    total_deployable = counts["v2_full"] + counts["v2_publish"] + counts["v1_legacy"]
    pct = 0 if total_deployable == 0 else round(100 * counts["v2_full"] / total_deployable)
    lines.append(
        f"**Progreso**: {counts['v2_full']} ✅ / {counts['v2_publish']} 🟡 / "
        f"{counts['v1_legacy']} 🔴 / {counts['na']} ⚪ — **{pct}% completo** "
        f"(sobre {total_deployable} repos deployables)"
    )
    lines.append("")

    # Sección 2: inventario de deploys
    lines.append("## 2. Inventario de deploys")
    lines.append("")
    lines.append("| Repo | Tipo | Ambiente | Instalación | Endpoint | Stack | Service | Replica | Executable path | Auto |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    deploy_rows: list[tuple] = []
    for s in states:
        if not s.deploy_json:
            continue
        envs = s.deploy_json.get("environments", {}) or {}
        for env_name, env in envs.items():
            for inst in env.get("installations", []) or []:
                auto = "sí" if inst.get("auto_deploy") else "—"
                deploy_rows.append((
                    s.name, s.app_type or "", env_name, inst.get("name", ""),
                    inst.get("portainer_endpoint", ""),
                    inst.get("portainer_stack", ""),
                    inst.get("portainer_service", ""),
                    inst.get("portainer_replica", 1),
                    inst.get("executable_path", ""),
                    auto,
                ))
    for row in sorted(deploy_rows):
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    if not deploy_rows:
        lines.append("| _(ningún repo migrado todavía)_ | | | | | | | | | |")
    lines.append("")

    # Sección 3: validación cruzada
    lines.append("## 3. Validación cruzada")
    lines.append("")
    issues: list[str] = []
    # Colisiones: misma cuádrupla (endpoint, stack, service, replica) en distintos repos/ambientes.
    by_target: dict[tuple[str, str, str, int], list[str]] = {}
    for repo, _type, env, inst, ep, stack, service, replica, _path, _auto in deploy_rows:
        if ep and stack and service:
            by_target.setdefault((ep, stack, service, replica), []).append(f"{repo}/{env}/{inst}")
    for (ep, stack, service, replica), users in by_target.items():
        if len(users) > 1:
            issues.append(
                f"- **Colisión** en `{ep}` / `{stack}` / `{service}` / replica `{replica}`: {', '.join(users)}"
            )

    # Errores de schema: cada repo con violaciones se reporta individualmente.
    for s in states:
        if s.schema_errors:
            errs = "\n  - ".join(s.schema_errors)
            issues.append(f"- **Schema drift** en `{s.name}/.github/deploy.json`:\n  - {errs}")

    # Repos con v2 publish pero sin deploy.json: recordatorio.
    for s in states:
        if s.state == "v2_publish":
            issues.append(f"- `{s.name}` usa workflows `@v2` pero no tiene `.github/deploy.json` — falta migrar deploy (transicional, OK).")

    if issues:
        lines.extend(issues)
    else:
        lines.append("_Sin incidencias detectadas._")
    lines.append("")

    # Sección 4: grafo de libs internas
    lines.append("## 4. Grafo de libs internas")
    lines.append("")
    lines.append(
        f"Orgs Maven consideradas internas: {', '.join(f'`{g}`' for g in INTERNAL_GROUPS)}. "
        "Fuente: parsing line-based de cada `build.sbt` (no soporta `val FuiVersion = \"...\"` ni multi-módulo)."
    )
    lines.append("")
    publishers = lib_graph["publishers"]
    consumers = lib_graph["consumers"]
    if not publishers:
        lines.append("_(ningún repo identificado como publisher de lib interna)_")
    else:
        lines.append("| Lib | groupId:artifactId | # consumers | Consumers |")
        lines.append("|---|---|---|---|")
        for lib_full in sorted(publishers):
            meta = publishers[lib_full]
            cs = consumers.get(lib_full, [])
            cs_links = ", ".join(f"[{c.split('/', 1)[-1]}](https://github.com/{c})" for c in cs) or "_—_"
            lines.append(
                f"| [{lib_full.split('/', 1)[-1]}](https://github.com/{lib_full}) | "
                f"`{meta['groupId']}:{meta['artifactId']}` | {len(cs)} | {cs_links} |"
            )
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    repos = list_repos(ORG)
    repos = [r for r in repos if not r.get("archived") and not r.get("fork")]
    # Skip the CI-CD repo itself — no se auto-inventaria.
    repos = [r for r in repos if r["name"] != "CI-CD"]

    states: list[RepoState] = []
    for r in repos:
        print(f"Scanning {r['name']}...", file=sys.stderr)
        try:
            states.append(classify(ORG, r["name"]))
        except Exception as e:  # pragma: no cover - defensive
            print(f"  error: {e}", file=sys.stderr)
            states.append(RepoState(name=r["name"], archived=False, state="na", notes=[f"error: {e}"]))

    lib_graph = build_lib_graph(states, ORG)
    content = render(states, lib_graph)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(states)} repos)", file=sys.stderr)

    GRAPH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_OUTPUT.write_text(
        json.dumps(lib_graph, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {GRAPH_OUTPUT} ({len(lib_graph['publishers'])} publishers)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
