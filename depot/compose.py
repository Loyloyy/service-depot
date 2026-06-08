"""Discover consumers/services and build/run the real `docker compose` commands.

The compose PROFILES are the source of truth; `apps.yaml` just gives friendly names. Every command is
built as an explicit arg list and echoed before running, so the launcher never hides what it does —
the same `docker compose --profile … <action>` works by hand.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO / "docker-compose.yml"
APPS_FILE = REPO / "apps.yaml"

# action → the docker compose verb(s) it maps to.
ACTIONS = {
    "up": ["up", "-d"],
    "down": ["down"],
    "restart": ["restart"],
    "status": ["ps"],
    "logs": ["logs", "-f"],
}


def load_apps() -> tuple[dict, dict]:
    """Return (apps, services) from apps.yaml."""
    data = yaml.safe_load(APPS_FILE.read_text()) or {}
    return data.get("apps", {}) or {}, data.get("services", {}) or {}


def compose_exe() -> list[str]:
    """Prefer `docker compose` (v2 — Langfuse v3 needs it); fall back to `docker-compose` (v1)."""
    if shutil.which("docker"):
        try:
            if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
                return ["docker", "compose"]
        except OSError:
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]  # absent → the run will fail with a clear error


def base_cmd() -> list[str]:
    # Explicit project dir + file so the launcher works from any cwd and reads the repo's .env.
    return [*compose_exe(), "--project-directory", str(REPO), "-f", str(COMPOSE_FILE)]


def resolve_profile(arg: str, apps: dict, services: dict) -> str:
    """Map a consumer/service arg to a compose profile (accepts an app key, a friendly name, or a profile)."""
    if arg in apps:
        return apps[arg]["profile"]
    for v in apps.values():
        if v.get("profile") == arg:
            return v["profile"]
    if arg in services:
        return services[arg]["profile"]
    return arg  # assume it's already a profile name


def build_command(action: str, *, profiles=None, services=None, extra=None) -> list[str]:
    cmd = base_cmd()
    for p in profiles or []:
        cmd += ["--profile", p]
    cmd += ACTIONS.get(action, [action])
    cmd += list(services or [])
    cmd += list(extra or [])
    return cmd


def run(cmd: list[str], *, dry_run: bool = False) -> int:
    """Echo the equivalent compose command, then run it (unless --dry-run)."""
    print("→ " + " ".join(cmd))
    if dry_run:
        return 0
    try:
        return subprocess.run(cmd).returncode
    except FileNotFoundError:
        print("error: `docker` not found on PATH.")
        return 127
