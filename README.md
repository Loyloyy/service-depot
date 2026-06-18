# service-depot

**Shared support services for any app** — self-hosted, run once, consumed by many. Currently ships
**Langfuse** (LLM observability) and **SearXNG** (search); an **evals** service is planned. Apps don't
embed these — they connect to a running instance by network + env, the 12-factor way.

```
        ┌─────────────── service-depot (this repo) ───────────────┐
        │  Langfuse (obs)   SearXNG (search)   evals (future) …    │
        └───────────────▲──────────────────▲─────────────────────┘
                        │  depot-net (shared docker network)
        ┌───────────────┴───────┐  ┌───────┴───────────────┐
        │ ai-engineer-research  │  │      poc-foundry      │   … any app
        │  (Stage 2 consumer)   │  │   (Stage 3 consumer)  │
        └───────────────────────┘  └───────────────────────┘
```

One Langfuse instance, a **project per consumer** (e.g. `stage-2-research`, `stage-3-poc`). Sharing is
pure runtime config — each app points at the instance with its own project key. No cross-repo code; no
secrets in any tracked file.

## Two ways to drive it

It's a thin wrapper over `docker compose` profiles. `./depot` is for convenience — **no pip, no venv, no
Python**, just a bash script over `docker compose` (+ `openssl` for `setup`). It echoes every command it
runs, and **raw compose always works** (and is what you want for debugging).

**Easy way — the `./depot` script:**
```bash
./depot setup               # first-run: create depot-net, generate .env secrets, check prereqs
./depot up stage-2          # bring up the services Stage 2 needs (echoes the compose command it runs)
./depot status              # what's running
./depot connect stage-2     # print the LANGFUSE_* snippet to paste into the consumer's .env
./depot logs langfuse-web   # tail a service
./depot down                # stop ALL shared services (add -v to also wipe data)
```
Run `./depot` with no args for an interactive menu: pick a consumer → action.

**Raw way — plain compose (power use + diagnosis):**
```bash
docker network create depot-net          # once (./depot setup does this)
docker compose --profile stage-2 up -d   # or --profile langfuse for just Langfuse
docker compose --profile stage-2 ps
docker compose --profile stage-2 logs -f langfuse-web
docker compose --profile stage-2 down    # `down` is PROFILE-SCOPED — without a profile it stops nothing
```

## Connect an app (e.g. Stage 2)

`./depot connect stage-2` prints exactly what to paste into the consumer's gitignored `.env`:
```
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_PUBLIC_KEY=pk-lf-…
LANGFUSE_SECRET_KEY=sk-lf-…
```
The consumer's app container must be on `depot-net` to resolve `langfuse-web` (the `ai-engineer-research`
app joins it in its base compose). The Langfuse UI is on **http://localhost:3000** (admin user from
`LANGFUSE_INIT_*`).

## Second consumer: `poc-foundry` (Stage 3)

Stage 3 is onboarded **additively** — one shared Langfuse *instance*, a separate *project* per consumer
(a project is just a dashboard + key pair, not a service). `./depot up stage-3` brings up the same
services as Stage 2 (**SearXNG + Langfuse**); the `stage-2` profile is unchanged.

1. **Bring up the services:** `./depot up stage-3` (or raw `docker compose --profile stage-3 up -d`).
2. **Create the project:** in the Langfuse UI (http://localhost:3000), under the `depot` org, create a
   project named **`stage-3-poc`** and generate an API key pair for it.
3. **Record its keys** in depot's gitignored `.env`:
   ```
   STAGE3_LANGFUSE_PUBLIC_KEY=pk-lf-…
   STAGE3_LANGFUSE_SECRET_KEY=sk-lf-…
   ```
4. **Print the snippet:** `./depot connect stage-3` emits the `LANGFUSE_*` block to paste into
   poc-foundry's own gitignored `.env`.
5. **Join the network:** poc-foundry's app container must be on `depot-net` (declare it in poc-foundry's
   base compose) so it can resolve `langfuse-web` and `searxng` by name.

## Prerequisites

- **Docker + `docker compose` v2** (Langfuse v3's stack needs v2; `./depot setup` checks this). No Python
  or pip — `./depot` is a bash script (uses `openssl` for `setup`).
- **Executable bit:** if `git pull` lands `depot` non-executable (common when the repo was committed from a
  Windows filesystem), run `chmod +x depot` once — or just invoke it as `bash depot …`.
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

## Parked — considered, not built (revisit when there's a real signal)

Candidate services deliberately **not** added yet. Recorded so the rationale isn't relitigated; build
only when the trigger below actually fires.

- **devpi** (PyPI pull-through cache) — would speed poc-foundry's per-build `uv sync` and cut egress.
  *Revisit after Stage 3's M2*, once real build frequency is known.
- **verdaccio** (npm mirror) — only if the npm-egress appeal is ever granted; no point before that.
- **evals** service — planned shared service (see the diagram up top); not yet scoped.
- **container-registry pull-through cache** — for the sandbox service images (Milvus / pgvector /
  OpenSearch). Defer until image-pull volume justifies it.

## Troubleshooting (learned the hard way)

- **`langfuse-web` exits with `P1000 / Authentication failed against database`** — a credential mismatch.
  The upstream compose duplicates DB/object-store creds across services with matching *defaults*; if a
  generated secret isn't propagated to its consumer they diverge. This compose derives `DATABASE_URL` and
  the MinIO S3 keys from the primary secrets (`POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`) so they stay
  consistent. If you change a primary secret *after* first boot, the data volume still has the old one →
  reset with `docker compose --profile stage-2 down -v` (wipes volumes), then `./depot up stage-2`.
- **`Invalid environment variables: LANGFUSE_INIT_USER_EMAIL`** — the init admin email must be a *valid*
  email (the `<you@…>` style placeholder fails). `./depot setup` writes a valid default (`admin@example.com`);
  change it in `.env` if you want, then recreate: `./depot up stage-2`.
- **An image pull resets / "connection reset"** — that registry isn't reachable here. All six images pull
  from Docker Hub for broad reachability (notably MinIO is `docker.io/minio/minio`, not `cgr.dev/...`).
- **First boot is slow** — `langfuse-web` runs ~400 DB migrations on first start; "Ready" can take 1–3 min
  after the containers come up. Watch `./depot logs langfuse-web`.
- **Can't open the UI at `localhost:3000`** — the port is on the *server*. Tunnel it **from your local
  machine** (e.g. PuTTY: Connection → SSH → Tunnels, source `3000` → dest `localhost:3000`; or
  `ssh -L 3000:localhost:3000 <user>@<host>` from your laptop), then browse `localhost:3000`.
- **Secrets** are generated locally by `openssl` into the gitignored `.env` — never committed. Anyone who
  clones this repo runs `./depot setup` and gets their *own* fresh secrets; the public repo only ships
  the recipe + placeholders, not the values.
- **`docker compose down` stops nothing** — `down` is **profile-scoped**, and every service here is gated
  by a profile, so a bare `down` matches none. `./depot down` handles this (it enables all profiles); with
  raw compose you must pass one: `docker compose --profile stage-2 down`.
- **Needs `docker compose` v2** — the v1 binary won't run this stack; `./depot setup` flags it.
