"""Print the LANGFUSE_* connection snippet a consumer pastes into its (gitignored) .env.

Apps reach Langfuse by service name over `depot-net`, so the host is always the in-network
`http://langfuse-web:3000` (NOT the host-published URL). Keys are per project: stage-2 reuses the
headless-init project keys; other consumers read `<PREFIX>_LANGFUSE_PUBLIC_KEY/_SECRET_KEY` from .env.
"""
from __future__ import annotations

from .compose import REPO, load_apps

LANGFUSE_INTERNAL_HOST = "http://langfuse-web:3000"


def _load_env() -> dict:
    env: dict[str, str] = {}
    p = REPO / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _keys_for(profile: str, env: dict) -> tuple[str, str]:
    if profile == "stage-2":  # the headless-init project
        return (
            env.get("LANGFUSE_INIT_PROJECT_PUBLIC_KEY", "<set LANGFUSE_INIT_PROJECT_PUBLIC_KEY in .env>"),
            env.get("LANGFUSE_INIT_PROJECT_SECRET_KEY", "<set LANGFUSE_INIT_PROJECT_SECRET_KEY in .env>"),
        )
    prefix = profile.upper().replace("-", "")  # stage-3 → STAGE3
    return (
        env.get(f"{prefix}_LANGFUSE_PUBLIC_KEY", f"<create the {profile} project in the UI, set {prefix}_LANGFUSE_PUBLIC_KEY>"),
        env.get(f"{prefix}_LANGFUSE_SECRET_KEY", f"<set {prefix}_LANGFUSE_SECRET_KEY in .env>"),
    )


def snippet(app: str) -> str:
    apps, services = load_apps()
    profile = apps.get(app, {}).get("profile") or app  # accept app key or profile
    if app not in apps:
        for k, v in apps.items():
            if v.get("profile") == app:
                profile = v["profile"]
                break
    pk, sk = _keys_for(profile, _load_env())
    return (
        f"# Langfuse connection for {app} — paste into that repo's gitignored .env, then set AER_TRACING=1\n"
        f"LANGFUSE_HOST={LANGFUSE_INTERNAL_HOST}\n"
        f"LANGFUSE_PUBLIC_KEY={pk}\n"
        f"LANGFUSE_SECRET_KEY={sk}"
    )
