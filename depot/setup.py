"""`depot setup` — first-run onboarding ("doctor"): network, secrets, data dir, prereq checks.

One command turns a clean machine into a ready depot: creates the shared `depot-net`, generates strong
secrets into a gitignored `.env` (from `.env.example`), ensures the local data dir, and checks Docker +
`docker compose` v2 (Langfuse v3's hard prerequisite).
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
from pathlib import Path

from .compose import REPO

NETWORK = "depot-net"

# .env keys that get a freshly generated value (the rest are copied from .env.example as-is).
_GENERATORS = {
    "NEXTAUTH_SECRET": lambda: secrets.token_urlsafe(32),
    "SALT": lambda: secrets.token_urlsafe(32),
    "ENCRYPTION_KEY": lambda: secrets.token_hex(32),  # exactly 64 hex chars
    "POSTGRES_PASSWORD": lambda: secrets.token_urlsafe(24),
    "CLICKHOUSE_PASSWORD": lambda: secrets.token_urlsafe(24),
    "REDIS_AUTH": lambda: secrets.token_urlsafe(24),
    "MINIO_ROOT_PASSWORD": lambda: secrets.token_urlsafe(24),
    "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": lambda: "pk-lf-" + secrets.token_hex(16),
    "LANGFUSE_INIT_PROJECT_SECRET_KEY": lambda: "sk-lf-" + secrets.token_hex(16),
    "LANGFUSE_INIT_USER_PASSWORD": lambda: secrets.token_urlsafe(16),
}


def render_env(example_text: str) -> str:
    """Return .env content: .env.example with the generated keys filled in (pure → unit-testable)."""
    out = []
    for line in example_text.splitlines():
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in _GENERATORS:
                out.append(f"{key}={_GENERATORS[key]()}")
                continue
        out.append(line)
    return "\n".join(out) + "\n"


def _gen_env() -> None:
    env_path = REPO / ".env"
    if env_path.exists():
        print(".env: exists — leaving untouched (delete it to regenerate).")
        return
    example = (REPO / ".env.example").read_text()
    env_path.write_text(render_env(example))
    print(f".env: generated with strong secrets → {env_path}")
    print("   ⚠ set LANGFUSE_INIT_USER_EMAIL before bringing the stack up.")


def _ensure_network(dry_run: bool = False) -> None:
    try:
        exists = subprocess.run(["docker", "network", "inspect", NETWORK], capture_output=True).returncode == 0
    except FileNotFoundError:
        print("network: skipped (docker not found).")
        return
    if exists:
        print(f"network {NETWORK}: exists.")
        return
    print(f"→ docker network create {NETWORK}")
    if not dry_run:
        subprocess.run(["docker", "network", "create", NETWORK])


def _ensure_data_dir() -> None:
    d = os.environ.get("DEPOT_DATA_DIR")
    if not d:
        print("data: using Docker-managed named volumes (local driver).")
        return
    Path(d).mkdir(parents=True, exist_ok=True)
    print(f"data dir: {d} (ensure this is LOCAL disk, not NFS).")


def _check(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def doctor(dry_run: bool = False) -> int:
    print("== depot setup ==")
    docker_ok = shutil.which("docker") is not None
    print("docker:", "OK" if docker_ok else "MISSING")
    print("docker compose v2:", "OK" if _check(["docker", "compose", "version"]) else "MISSING (Langfuse v3 needs it)")
    _ensure_network(dry_run=dry_run)
    _ensure_data_dir()
    _gen_env()
    print("\nNext: depot up --app stage-2   →   depot connect stage-2")
    return 0
