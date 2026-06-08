# service-depot

**Shared support services for any app** — self-hosted, run once, consumed by many. Currently ships
**Langfuse** (LLM observability); **SearXNG** (search) and an **evals** service are planned. Apps don't
embed these — they connect to a running instance by network + env, the 12-factor way.

```
        ┌─────────────── service-depot (this repo) ───────────────┐
        │  Langfuse (obs)   SearXNG (search)   evals (future) …    │
        └───────────────▲──────────────────▲─────────────────────┘
                        │  depot-net (shared docker network)
        ┌───────────────┴───────┐  ┌───────┴───────────────┐
        │ ai-engineer-research  │  │  stage-3 PoC builder  │   … any app
        │  (Stage 2 consumer)   │  │   (future consumer)   │
        └───────────────────────┘  └───────────────────────┘
```

One Langfuse instance, a **project per consumer** (e.g. `stage-2-research`, `stage-3-poc`). Sharing is
pure runtime config — each app points at the instance with its own project key. No cross-repo code; no
secrets in any tracked file.

## Two ways to drive it

It's a thin wrapper over `docker compose` profiles. The launcher is for convenience; **raw compose always
works** (and is what you want for debugging).

**Easy way — the `depot` launcher:**
```bash
pip install -e .            # installs the `depot` command (Python ≥3.9)
depot setup                 # first-run: create depot-net, generate secrets into .env, make data dir, check prereqs
depot up --app stage-2      # bring up the services Stage 2 needs (echoes the compose command it runs)
depot status                # what's running + health + URLs
depot connect stage-2       # print the LANGFUSE_* snippet to paste into the consumer's .env
depot logs langfuse-web     # tail a service
depot down --app stage-2
```
Interactive (no args) pops a menu: pick a consumer → action. `--dry-run` prints the command without running.

**Raw way — plain compose (power use + diagnosis):**
```bash
docker network create depot-net          # once (depot setup does this)
docker compose --profile stage-2 up -d   # or --profile langfuse for just Langfuse
docker compose --profile stage-2 ps
docker compose --profile stage-2 logs -f langfuse-web
docker compose --profile langfuse down
```

## Connect an app (e.g. Stage 2)

`depot connect stage-2` prints exactly what to paste into the consumer's gitignored `.env`:
```
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_PUBLIC_KEY=pk-lf-…
LANGFUSE_SECRET_KEY=sk-lf-…
```
The consumer's app container must join `depot-net` to resolve `langfuse-web` (see that repo's compose
override). The Langfuse UI is on **http://localhost:3000** (admin user from `LANGFUSE_INIT_*`).

A second consumer (stage-3): create a `stage-3-poc` project in the Langfuse UI, record its keys in `.env`
(`STAGE3_LANGFUSE_*`), then `depot connect stage-3`.

## Prerequisites

- **Docker + `docker compose` v2** (Langfuse v3's stack needs v2; `depot setup` checks this).
- **Local disk** for the stateful volumes (Postgres/ClickHouse/MinIO). Named volumes use Docker's
  data-root (local by default). If your data-root is on NFS, relocate it or set `DEPOT_DATA_DIR` to a
  local path — **ClickHouse/MinIO misbehave on NFS**.

## Data & security

- All secrets live only in the gitignored `.env` (generate with `depot setup`). Tracked files use
  `${VAR}` refs + `# CHANGEME` placeholders — never real secrets.
- Telemetry is **off** (`TELEMETRY_ENABLED=false`). Only `langfuse-web` (:3000) and `minio` (:9090) are
  exposed; the backing stores bind to `127.0.0.1` and stay on the internal network.
- Stack adapted from Langfuse's official v3 self-host compose; bump image tags only after a changelog
  review.
