"""Create a project profile (projects/<id>.yaml) for a target repo.

This is the "link a repo" step: instead of hand-copying YAML, run

    python -m src.main init-project --repo owner/name

and it writes projects/<id>.yaml, auto-filling owner/name/url/base_branch from
GitHub (via `gh`) when possible. Edit the file afterwards to set test commands
and danger paths for that repo's stack.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

# Per-stack defaults so a fresh profile is usable immediately.
_STACK_PRESETS: dict[str, dict] = {
    "python": {
        "type": "python",
        "commands": {"install": "pip install -e .", "test": "pytest"},
        "danger": [".github/**", "pyproject.toml", "setup.py", "setup.cfg"],
    },
    "node": {
        "type": "node",
        "commands": {"install": "npm install", "test": "npm test"},
        "danger": [".github/**", "package.json", "package-lock.json"],
    },
    "flutter": {
        "type": "flutter_supabase",
        "commands": {"install": "flutter pub get", "analyze": "flutter analyze",
                     "test": "flutter test"},
        "danger": ["supabase/migrations/**", "lib/**/sync/**", "lib/**/queue/**",
                   "android/**", "ios/**", "pubspec.yaml"],
    },
    "generic": {
        "type": "generic",
        "commands": {"test": "echo 'set your test command'"},
        "danger": [".github/**"],
    },
}


def _gh_repo_info(full_name: str) -> Optional[dict]:
    """Return {owner, name, url, base_branch} from `gh`, or None if unavailable."""
    try:
        proc = subprocess.run(
            ["gh", "repo", "view", full_name, "--json",
             "name,owner,defaultBranchRef,url"],
            capture_output=True, text=True, encoding="utf-8",
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    data = json.loads(proc.stdout)
    return {
        "owner": data["owner"]["login"],
        "name": data["name"],
        "url": data.get("url", f"https://github.com/{full_name}") + ".git",
        "base_branch": (data.get("defaultBranchRef") or {}).get("name", "main"),
    }


def _yaml_list(items: list[str], indent: str = "    ") -> str:
    if not items:
        return " []"
    return "\n" + "\n".join(f'{indent}- "{it}"' for it in items)


def build_profile_yaml(
    *,
    project_id: str,
    owner: str,
    name: str,
    url: str,
    base_branch: str,
    stack: str,
) -> str:
    preset = _STACK_PRESETS.get(stack, _STACK_PRESETS["generic"])
    cmd_lines = "\n".join(f"  {k}: \"{v}\"" for k, v in preset["commands"].items())
    danger = _yaml_list(preset["danger"], indent="    ")
    return f"""project:
  id: {project_id}
  name: {name}
  type: {preset['type']}

repo:
  owner: {owner}
  name: {name}
  url: {url}
  base_branch: {base_branch}

branch_prefix: "ai-task/"

labels:
  task: ai-task
  pending: pending

commands:
{cmd_lines}

paths:
  danger:{danger}
  readonly: []

context_file: AI_PROJECT_CONTEXT.md
workspace_dir: workspace
"""


def init_project(
    repo: str,
    *,
    project_id: Optional[str] = None,
    stack: str = "python",
    base_branch: Optional[str] = None,
    out_dir: str | Path = "projects",
    overwrite: bool = False,
) -> Path:
    """Write projects/<id>.yaml for `repo` (owner/name). Returns the path."""
    if "/" not in repo:
        raise ValueError("repo must be 'owner/name'")
    owner, name = repo.split("/", 1)

    info = _gh_repo_info(repo)
    if info:
        owner, name = info["owner"], info["name"]
        url = info["url"]
        base = base_branch or info["base_branch"]
    else:
        url = f"https://github.com/{repo}.git"
        base = base_branch or "main"

    pid = project_id or name.replace(".", "-").lower()
    out = Path(out_dir) / f"{pid}.yaml"
    if out.exists() and not overwrite:
        raise FileExistsError(f"{out} already exists (use --overwrite to replace)")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        build_profile_yaml(project_id=pid, owner=owner, name=name, url=url,
                           base_branch=base, stack=stack),
        encoding="utf-8",
    )
    return out


# --- Smart "run <path>" resolution ----------------------------------------

def _git_remote_full_name(repo_dir: Path) -> Optional[str]:
    """Return 'owner/name' from a local repo's origin remote, or None."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
            capture_output=True, text=True, encoding="utf-8",
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    url = proc.stdout.strip()
    # Normalise both forms:
    #   git@github.com:owner/name.git  /  https://github.com/owner/name(.git)
    url = url.removesuffix(".git")
    if url.startswith("git@"):
        # git@host:owner/name
        _, _, path = url.partition(":")
    else:
        # https://host/owner/name  ->  keep last two segments
        path = "/".join(url.rstrip("/").split("/")[-2:])
    if path.count("/") == 1 and all(path.split("/")):
        return path
    return None


def _find_profile_for_repo(full_name: str, out_dir: str | Path = "projects") -> Optional[Path]:
    """Return an existing projects/*.yaml whose repo matches full_name, or None."""
    import yaml
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return None
    for yml in sorted(out_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        repo = data.get("repo") or {}
        if f"{repo.get('owner')}/{repo.get('name')}" == full_name:
            return yml
    return None


def resolve_profile(
    target: str,
    *,
    stack: str = "python",
    out_dir: str | Path = "projects",
) -> Path:
    """Resolve a `run <path>` argument to a project profile (projects/<id>.yaml).

    `target` may be:
      * a profile file        -> projects/sandbox.yaml  (used as-is)
      * a GitHub repo          -> owner/name             (find or create profile)
      * a local repo directory -> ./my-app or C:\\path   (read git origin -> repo)

    Returns the path to the profile. Creates one (via init_project) when a repo is
    given but no matching profile exists yet.
    """
    p = Path(target)

    # 1. An explicit profile YAML file.
    if p.suffix.lower() in (".yaml", ".yml") and p.is_file():
        return p

    # 2. A local directory: derive owner/name from its git origin remote.
    if p.is_dir():
        full_name = _git_remote_full_name(p)
        if not full_name:
            raise ValueError(
                f"'{target}' is a directory but has no GitHub 'origin' remote. "
                f"The bot needs a GitHub repo to push branches and open PRs."
            )
    # 3. Otherwise treat it as a GitHub repo 'owner/name'.
    elif "/" in target and not p.exists():
        full_name = target.strip().strip("/")
    else:
        raise ValueError(
            f"Cannot resolve '{target}'. Use a profile (projects/x.yaml), a "
            f"GitHub repo (owner/name), or a local repo directory."
        )

    # Reuse an existing profile for this repo, else create one.
    existing = _find_profile_for_repo(full_name, out_dir=out_dir)
    if existing is not None:
        return existing
    return init_project(full_name, stack=stack, out_dir=out_dir)
