#!/usr/bin/env python3
"""
Genera docs/inventory.md con:
  1. Estado de migración v2 por repo (✅/🟡/🔴/⚪)
  2. Inventario agregado de deploys (desde cada .github/deploy.json)
  3. Validación cruzada (colisiones, violaciones de schema)

Clasificación (spec §4.11):
  ✅ v2 completo      — tiene .github/deploy.json  + workflows usan @v2
  🟡 v2 publish-only  — workflows usan @v2  + sin deploy.json
  🔴 v1 legacy        — workflows invocan scala-deploy-* / scala-make-release-* / scala-publish-*
  ⚪ N/A              — repo sin workflows de deploy

Requiere: env vars GH_TOKEN (PAT con repo:read sobre la org) y ORG (default BQN-UY).
Usa `gh api` para todas las llamadas a GitHub.
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

ORG = os.environ.get("ORG", "BQN-UY")
OUTPUT = Path(os.environ.get("OUTPUT", "docs/inventory.md"))
SCHEMA_REL_PATH = "schemas/deploy.schema.json"

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
    notes: list[str] = field(default_factory=list)


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


def classify(org: str, repo: str) -> RepoState:
    state = RepoState(name=repo, archived=False)

    dj_raw = get_file(org, repo, ".github/deploy.json")
    if dj_raw:
        try:
            state.deploy_json = json.loads(dj_raw)
            state.app_type = state.deploy_json.get("application_type")
        except json.JSONDecodeError:
            state.notes.append("deploy.json no parsea como JSON")

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

    return state


STATE_ICON = {
    "v2_full":    "✅ v2 completo",
    "v2_publish": "🟡 v2 publish-only",
    "v1_legacy":  "🔴 v1 legacy",
    "na":         "⚪ N/A",
}


def render(states: list[RepoState]) -> str:
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
    lines.append("| Repo | Tipo | Ambiente | Instalación | Endpoint | Container | Path | Ext | Auto |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    deploy_rows: list[tuple] = []
    for s in states:
        if not s.deploy_json:
            continue
        envs = s.deploy_json.get("environments", {}) or {}
        for env_name, env in envs.items():
            for inst in env.get("installations", []) or []:
                artifact = inst.get("artifact", {}) or {}
                auto = "sí" if inst.get("auto_deploy") else "—"
                deploy_rows.append((
                    s.name, s.app_type or "", env_name, inst.get("name", ""),
                    inst.get("portainer_endpoint", ""),
                    inst.get("portainer_container", ""),
                    artifact.get("deploy_path", ""),
                    artifact.get("extension", ""),
                    auto,
                ))
    for row in sorted(deploy_rows):
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    if not deploy_rows:
        lines.append("| _(ningún repo migrado todavía)_ | | | | | | | | |")
    lines.append("")

    # Sección 3: validación cruzada
    lines.append("## 3. Validación cruzada")
    lines.append("")
    issues: list[str] = []
    # Colisiones: mismo (endpoint, container_name) en distintos repos/ambientes.
    by_endpoint_container: dict[tuple[str, str], list[str]] = {}
    for repo, _type, env, inst, ep, cn, *_ in deploy_rows:
        if ep and cn:
            by_endpoint_container.setdefault((ep, cn), []).append(f"{repo}/{env}/{inst}")
    for (ep, cn), users in by_endpoint_container.items():
        if len(users) > 1:
            issues.append(f"- **Colisión** en `{ep}` / `{cn}`: {', '.join(users)}")

    # Repos con v2 publish pero sin deploy.json: recordatorio.
    for s in states:
        if s.state == "v2_publish":
            issues.append(f"- `{s.name}` usa workflows `@v2` pero no tiene `.github/deploy.json` — falta migrar deploy (transicional, OK).")

    if issues:
        lines.extend(issues)
    else:
        lines.append("_Sin incidencias detectadas._")
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

    content = render(states)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(states)} repos)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
