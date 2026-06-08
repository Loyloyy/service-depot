"""`depot` — the launcher. A thin, transparent menu over `docker compose` profiles.

Interactive (no action) → pick a consumer → pick an action. Or drive it directly:
  depot setup
  depot up --app stage-2        depot status        depot logs --service langfuse-web
  depot down --app stage-2      depot connect stage-2
Every run echoes the equivalent `docker compose --profile … <action>`; `--dry-run` prints without running.
Raw `docker compose --profile … …` works identically — the launcher never hides it.
"""
from __future__ import annotations

import argparse
import sys

from .compose import ACTIONS, build_command, load_apps, resolve_profile, run

_LIFECYCLE = ("up", "down", "restart", "status", "logs")


def _pick(prompt: str, options: list[tuple[str, str]]) -> str | None:
    """Numbered picker (stdlib). options = [(value, label)]. Returns the chosen value or None."""
    if not sys.stdin.isatty():
        return None
    for i, (_, label) in enumerate(options, 1):
        print(f"  [{i}] {label}")
    sel = input(f"{prompt} [number, or q to cancel]: ").strip().lower()
    if not sel or sel == "q" or not sel.isdigit() or not (1 <= int(sel) <= len(options)):
        print("Cancelled." if sel in ("", "q") else "Invalid selection.")
        return None
    return options[int(sel) - 1][0]


def _interactive(apps: dict, services: dict, dry_run: bool) -> int:
    if not apps:
        print("No consumers defined in apps.yaml.")
        return 1
    print("\nservice-depot — bring up shared services\n")
    app_opts = [(k, f"{k}  ({', '.join(v.get('services', []))})  — {v.get('description', '')}")
                for k, v in apps.items()]
    app = _pick("Which consumer?", app_opts)
    if app is None:
        return 0
    action = _pick("Action?", [(a, a) for a in _LIFECYCLE])
    if action is None:
        return 0
    profile = resolve_profile(app, apps, services)
    return run(build_command(action, profiles=[profile]), dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="depot",
        description="Launch shared support services — a thin wrapper over `docker compose` profiles.",
    )
    ap.add_argument("action", nargs="?",
                    choices=["setup", "connect", *_LIFECYCLE],
                    help="omit for an interactive menu")
    ap.add_argument("--app", help="consumer (e.g. stage-2 / stage-2-research) → its compose profile")
    ap.add_argument("--service", help="service profile (e.g. langfuse), or a service name for `logs`")
    ap.add_argument("--dry-run", action="store_true", help="print the compose command without running it")
    args = ap.parse_args(argv)

    apps, services = load_apps()

    if args.action is None:
        return _interactive(apps, services, args.dry_run)

    if args.action == "setup":
        from .setup import doctor
        return doctor(dry_run=args.dry_run)

    if args.action == "connect":
        from .connect import snippet
        print(snippet(args.app or "stage-2"))
        return 0

    # lifecycle: up/down/restart/status/logs
    profiles = []
    if args.app:
        profiles = [resolve_profile(args.app, apps, services)]
    elif args.service and args.action != "logs":
        profiles = [resolve_profile(args.service, apps, services)]
    svc = [args.service] if (args.action == "logs" and args.service) else None
    return run(build_command(args.action, profiles=profiles, services=svc), dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
