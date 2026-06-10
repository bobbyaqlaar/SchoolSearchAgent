# Aqlaar Dubai School Finder — User Manual

Operational guide for **starting**, **stopping**, **developing**, and **deploying** the KHDA school search platform.

**Architecture:** Next.js web (`web/`) → FastAPI API (`api_service.py`) → Neo4j graph ← LangGraph Excel sync (`python -m dubai`).

| Component | Port | How it runs |
| --- | --- | --- |
| Web UI | `3000` | Node / Next.js |
| REST API | `8000` | Python / Uvicorn |
| Neo4j Browser | `7474` | Docker |
| Neo4j Bolt | `7687` | Docker |

Related docs: [README](../README.md) (full spec) · [README §9](../README.md#9-operations-guide--deploy-start-stop--refresh) (deploy/start/stop) · [ARCHITECTURE](ARCHITECTURE.md) (design, tracing §2.3)

---

## 1. Prerequisites (install once)

| Tool | Min | Purpose |
| --- | --- | --- |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 24+ | Neo4j (required on macOS/Windows) |
| [uv](https://docs.astral.sh/uv/) | 0.4+ | Python deps & commands |
| Node.js | 20+ | Frontend |
| npm | 10+ | Frontend packages |

Optional for Google Cloud production: `gcloud` CLI (`brew install --cask google-cloud-sdk`).

---

## 2. One-time setup

All commands below assume the **repository root**:

```bash
cd /path/to/schoolSearchAgent
```

### 2.1 Create `.env`

Copy variables from [README §5](../README.md#5-security-environment-blueprint-envexample) into `.env` at the repo root. Minimum for local dev:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=choose_a_strong_password

# Free dev LLM (Ask panel)
GITHUB_TOKEN=ghp_your_token
GITHUB_MODELS_BASE_URL=https://models.github.ai/inference

# Frontend → API (baked in at web build time)
NEXT_PUBLIC_API_BASE_URL=http://localhost:3000
```

> **Important:** Use the **same** `NEO4J_PASSWORD` in `.env` and in Docker Compose (`NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`). If you change the password after Neo4j was first created, either reset the volume (§8.2) or keep the original password.

Correct the frontend URL for local dev:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 2.2 Install dependencies

```bash
uv sync --extra providers          # Python backend + optional LLM providers
cd web && npm install && cd ..     # Frontend
```

### 2.3 Initialize the graph schema (first time only)

After Neo4j is running (§3):

```bash
docker exec -i dubai_neo4j_db cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  < scripts/init_constraints.cypher
```

### 2.4 Load school data (first time, or after wipe)

```bash
uv run python -m dubai              # download Excel, parse, MERGE into Neo4j
# Force full re-write of fees:
uv run python -m dubai --force
```

### 2.5 Ask assistant — scope and budget (reference)

| User intent | Behavior |
| --- | --- |
| `UK curriculum schools under 80000` | In scope — searches Dubai schools with UK curriculum, `max_budget_aed` |
| `UK schools with fees greater than 70000` | In scope — uses `min_budget_aed` (cheapest tier must exceed floor) |
| `schools in UK` / `schools of UK` | Out of scope — jurisdiction refusal (foreign location, not curriculum) |
| `rent under 70000` / `rental` | Out of scope — fee-term refusal (KHDA tuition only) |
| `What is the capital of France?` | Out of scope — jurisdiction refusal |

Free local dev: `github:gpt-4o-mini` + `GITHUB_TOKEN`. Other models need `uv sync --extra providers` and the matching API key in `.env`.

---

# DEVELOPMENT

Two dev layouts. **Hybrid (A)** is best for day-to-day coding (hot reload). **Full Docker (B)** mirrors production containers on one machine.

---

## 3. Dev startup — Option A (Hybrid, recommended)

Use **three terminals**. Order matters.

### Step 0 — Start Docker Desktop

On macOS/Windows, open **Docker Desktop** and wait until it shows **Running**. Without this, `docker compose` fails with:

```text
failed to connect to the docker API at unix:///Users/.../docker.sock
```

Verify:

```bash
docker info
```

### Step 1 — Start Neo4j (Terminal 1)

```bash
cd /path/to/schoolSearchAgent
docker compose up -d neo4j
docker compose ps                    # STATUS should become "healthy"
```

Wait ~30s on first boot. Confirm Bolt is up:

```bash
docker logs dubai_neo4j_db --tail 5   # should show "Started."
```

Neo4j Browser (optional): http://localhost:7474 — login `neo4j` / your `NEO4J_PASSWORD`.

### Step 2 — Start the API (Terminal 2)

```bash
cd /path/to/schoolSearchAgent
uv run uvicorn api_service:app --reload --host 127.0.0.1 --port 8000
```

Verify:

```bash
curl -fsS http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/api/facets | head -c 200
```

You should see JSON with `curriculums`, `neighborhoods`, etc. — not a connection error.

### Step 3 — Start the web UI (Terminal 3)

**Hot reload (daily dev):**

```bash
cd /path/to/schoolSearchAgent/web
npm run dev
```

Open **http://localhost:3000** (prefer this hostname over `127.0.0.1` for CORS). Filter dropdowns are populated from a **server-side facet fetch** on first load (`web/app/page.tsx`); if that fails, `SearchClient` retries client-side and shows a loading state until options arrive.

**Production-style local build** (optional):

```bash
cd /path/to/schoolSearchAgent/web
npm run build
node .next/standalone/server.js      # not `npm run start` — project uses standalone output
```

> Standalone mode requires `sharp` (already in `package.json`). Docker copies it automatically.

### Step 4 — Populate or refresh data (when needed)

```bash
cd /path/to/schoolSearchAgent
uv run python -m dubai
```

Run after first setup, after `docker compose down -v`, or when KHDA publishes an updated workbook.

### Dev startup checklist

| Step | Command | URL / check |
| --- | --- | --- |
| Docker running | Docker Desktop open | `docker info` succeeds |
| Neo4j | `docker compose up -d neo4j` | `docker compose ps` → healthy |
| API | `uv run uvicorn api_service:app --reload` | http://localhost:8000/ |
| Web | `cd web && npm run dev` | http://localhost:3000 |
| Data | `uv run python -m dubai` | Search returns schools |

---

## 4. Dev startup — Option B (Full Docker Compose)

Runs Neo4j + sync worker + API + web as containers.

```bash
cd /path/to/schoolSearchAgent
docker compose up -d --build
docker compose ps
```

| Service | Container | Port |
| --- | --- | --- |
| Neo4j | `dubai_neo4j_db` | 7474, 7687 |
| API | `dubai_rest_api_service` | 8000 |
| Web | `dubai_web` | host **3000** → container **8080** (standalone image) |
| Sync worker | `dubai_sync_agent_worker` | (cron inside container) |

First-time only — constraints + manual sync if the worker cron has not fired yet:

```bash
docker exec -i dubai_neo4j_db cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  < scripts/init_constraints.cypher
docker compose exec sync_agent uv run python -m dubai
```

Verify:

```bash
curl -fsS http://localhost:8000/
curl -fsS http://localhost:3000/
```

---

## 5. Dev shutdown

### Option A — Hybrid shutdown

Stop in reverse order. Use **Ctrl+C** in each terminal.

| Order | What | How |
| --- | --- | --- |
| 1 | Web dev server | Ctrl+C in Terminal 3 |
| 2 | API (Uvicorn) | Ctrl+C in Terminal 2 |
| 3 | Neo4j | See below |

**Stop Neo4j but keep data** (recommended between dev sessions):

```bash
docker compose stop neo4j
```

**Stop and remove the Neo4j container** (data kept in Docker volume):

```bash
docker compose down neo4j
```

**Stop everything Compose knows about:**

```bash
docker compose down
```

### Option B — Full Compose shutdown

**Stop all services, keep graph data:**

```bash
docker compose down
```

**Stop all services and delete Neo4j data** (empty graph — re-run sync after):

```bash
docker compose down -v
```

### What keeps running after shutdown?

| After | Still running? |
| --- | --- |
| Ctrl+C web / API | Only those processes stop |
| `docker compose stop neo4j` | Docker Desktop still running; Neo4j stopped |
| `docker compose down` | Containers removed; **volumes kept** |
| `docker compose down -v` | Containers + **Neo4j volume wiped** |
| Quit Docker Desktop | All containers stop |

---

## 6. Dev — testing & evaluation

### Tests

```bash
uv run pytest -q                           # backend
cd web && npm test                         # frontend
```

### Parsing eval (CI suite, LangSmith only)

```bash
uv sync --extra evals
uv run python -m evals.eval_parsing
uv run python -m evals.eval_parsing --skip-ci-gate   # debug, no exit code
```

### QA eval (optional, needs eval extras + LLM key)

```bash
uv sync --extra evals
uv run python -m evals.eval_qa
uv run python -m evals.eval_qa --local     # no LangSmith dataset sync
```

Deterministic Ask guard evaluators (no LLM required for those checks): foreign-location refusal (`schools in/of UK`), rent/rental refusal, false jurisdiction refusal on curriculum searches, off-topic jurisdiction refusal. `semantic_match` needs `sentence-transformers` from the `evals` extra.

Set `LANGCHAIN_API_KEY` and `LANGCHAIN_TRACING_V2=true` in `.env` for LangSmith runs.

---

# PRODUCTION

Production adds: **strong secrets**, **HTTPS**, **correct public URLs**, **scheduled sync**, and **monitoring**.

---

## 7. Production deploy — Option 1 (Docker Compose on a VM)

Best for a single server (on-prem or cloud VM).

### 7.1 Prepare the host

1. Install Docker + Compose.
2. Clone the repo; create production `.env`:
   - Strong `NEO4J_PASSWORD`
   - Real LLM keys (or `GITHUB_TOKEN` for limited traffic)
   - `NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com` (public API URL)
   - `CORS_ORIGINS=https://app.yourdomain.com`
3. Put TLS in front (Caddy, Nginx, or Traefik) terminating HTTPS for `:443` → web `:3000` and API `:8000`.

### 7.2 Build and start

```bash
cd /path/to/schoolSearchAgent
docker compose up -d --build
docker compose ps                      # all services healthy
```

### 7.3 First-run initialization

```bash
docker exec -i dubai_neo4j_db cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  < scripts/init_constraints.cypher
docker compose exec sync_agent uv run python -m dubai
```

### 7.4 Verify production

```bash
curl -fsS https://api.yourdomain.com/
curl -fsS https://api.yourdomain.com/api/facets
# Open https://app.yourdomain.com — filters load, search works
```

### 7.5 Ongoing operations

```bash
docker compose logs -f api_gateway      # tail API
docker compose restart api_gateway      # restart one tier
docker compose exec sync_agent uv run python -m dubai   # manual sync
docker compose up -d --build            # redeploy after git pull
```

---

## 8. Production shutdown — Docker Compose

### 8.1 Graceful stop (keep data, planned maintenance)

```bash
docker compose stop                    # stop all services
# or stop one tier:
docker compose stop api_gateway web
```

Bring back:

```bash
docker compose start
# or
docker compose up -d
```

### 8.2 Full teardown (remove containers, keep volumes)

```bash
docker compose down
```

Graph data survives in the `neo4j_data` volume.

### 8.3 Full reset (delete all graph data)

```bash
docker compose down -v
```

After this, repeat §7.3 (constraints + sync).

### 8.4 VM decommission

```bash
docker compose down -v
docker system prune -a                 # optional: reclaim disk
```

Back up `neo4j_data` before `-v` if you need to preserve the graph.

---

## 9. Production deploy — Google Cloud (Cloud Run)

**Fast path — one script (recommended):**

```bash
# 1. Install & login (once)
brew install --cask google-cloud-sdk
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Neo4j Aura — create a free instance at https://neo4j.com/cloud/aura/
#    Copy the Bolt URI (neo4j+s://….databases.neo4j.io) and password into .env

# 3. Deploy (from repo root)
# NEO4J_PASSWORD, GITHUB_TOKEN, LANGCHAIN_* loaded from .env
# GCP_PROJECT_ID optional — falls back to: gcloud config get-value project

chmod +x scripts/gcp_deploy.sh
./scripts/gcp_deploy.sh
```

The script: enables APIs → creates Artifact Registry → uploads secrets → deploys **API** → deploys **web** (with API URL baked in) → updates API **CORS** to the **exact** deployed web URL (`CORS_ORIGINS=${WEB_URL}`).

> **CORS:** Open the web app at the URL printed by the deploy script (e.g. `https://dubai-web-….run.app`). Alternate Cloud Run URL formats for the same service will fail CORS unless added to `CORS_ORIGINS`.

**LangSmith tracing (production, on by default):** `gcp_deploy.sh` sets `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_PROJECT` on `dubai-api`, mounts `LANGCHAIN_API_KEY` from Secret Manager `langchain-key` (from `.env` `LANGCHAIN_API_KEY` or `LANGSMITH_API_KEY`). API startup calls `configure_langsmith_tracing()` (`dubai/langsmith_env.py`). View traces at [smith.langchain.com](https://smith.langchain.com) under your `LANGCHAIN_PROJECT` (default `dubai-graph-sync-agent`). Details: [ARCHITECTURE §2.3](ARCHITECTURE.md#23-observability--langsmith-tracing).

**Secrets synced to GCP:** `neo4j-pass`, `github-token`, `openai-key`, `google-key`, `groq-key`, `langchain-key` — see [README §9.4](../README.md#94-production--google-cloud-cloud-run--neo4j-aura).

**After deploy — load graph data into Aura:**

```bash
# Point local sync at Aura (same creds as .env)
uv run python -m dubai
```

**Optional nightly sync job:**

```bash
./scripts/gcp_sync_job.sh
gcloud run jobs execute dubai-sync --region=me-central1 --wait
```

### 9.1 Manual / split deploy (alternative)

Phase 1 — API only:

```bash
gcloud builds submit --config deploy/cloudbuild-api.yaml \
  --substitutions=_REGION=me-central1,_REPO=dubai,_NEO4J_URI=neo4j+s://YOUR_AURA_HOST
```

Phase 2 — web (replace API URL):

```bash
API_URL=$(gcloud run services describe dubai-api --region=me-central1 --format='value(status.url)')
gcloud builds submit --config deploy/cloudbuild-web.yaml \
  --substitutions=_REGION=me-central1,_REPO=dubai,_API_URL=${API_URL}
WEB_URL=$(gcloud run services describe dubai-web --region=me-central1 --format='value(status.url)')
gcloud run services update dubai-api --region=me-central1 --update-env-vars=CORS_ORIGINS=${WEB_URL}
```

### 9.2 First-time GCP setup (reference)

```bash
gcloud auth login
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com

gcloud artifacts repositories create dubai \
  --repository-format=docker --location=me-central1

printf '%s' "$OPENAI_API_KEY"  | gcloud secrets create openai-key   --data-file=-
printf '%s' "$NEO4J_PASSWORD"  | gcloud secrets create neo4j-pass   --data-file=-
printf '%s' "$GITHUB_TOKEN"    | gcloud secrets create github-token --data-file=-
```

Provision Neo4j Aura (or a GCE VM) and note the Bolt URI (`neo4j+s://…`).

**URL chicken-and-egg:** deploy API first (§9.1 phase 1), copy its HTTPS URL for the web build (phase 2), then set `CORS_ORIGINS` on the API to the web URL. Prefer `./scripts/gcp_deploy.sh` — it handles all three steps.

### 9.3 Schedule nightly sync

```bash
gcloud run jobs create dubai-sync \
  --image me-central1-docker.pkg.dev/PROJECT_ID/dubai/api:latest \
  --region me-central1 \
  --command uv --args run,python,-m,dubai \
  --set-secrets NEO4J_PASSWORD=neo4j-pass:latest \
  --set-env-vars NEO4J_URI=neo4j+s://YOUR_AURA_HOST

gcloud scheduler jobs create http dubai-sync-trigger \
  --schedule "0 3 * * *" \
  --uri "https://REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/dubai-sync:run" \
  --http-method POST \
  --oauth-service-account-email YOUR_SA@PROJECT_ID.iam.gserviceaccount.com
```

### 9.4 CI/CD from GitHub

**Status:** Pipeline is **operational** — merge to `main` runs all checks then deploys to Cloud Run.

Workflow: [`.github/workflows/llm_regression_tests.yml`](../.github/workflows/llm_regression_tests.yml)

| Step | Job | What runs |
| --- | --- | --- |
| 1 | `unit-tests` | `uv run pytest -v` |
| 2 | `frontend` | `npm test` + `npm run build` |
| 3 | `llm-evals` | `uv run python -m evals.eval_parsing` + **`ci_gate`** |
| 4 | `deploy-production` | Webhook POST **or** WIF + `gcloud builds submit deploy/cloudbuild-ci-deploy.yaml` |

**One-time setup** (from repo root):

```bash
unset GITHUB_TOKEN
./scripts/setup_github_actions_deploy.sh    # WIF + GCP secrets (required for deploy)
./scripts/setup_deploy_webhook.sh           # optional; recommended — sets DEPLOY_WEBHOOK_*
```

| Secret | Required? | Set by |
| --- | --- | --- |
| `LANGCHAIN_API_KEY` | Yes (eval job) | Manual in GitHub → Settings → Secrets |
| `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, `GCP_REGION`, `NEO4J_URI` | Yes (WIF deploy fallback) | `setup_github_actions_deploy.sh` |
| `DEPLOY_WEBHOOK_URL`, `DEPLOY_WEBHOOK_TOKEN` | Optional (preferred deploy path) | `setup_deploy_webhook.sh` |

When webhook secrets are present, CI POSTs to `dubai-deploy-webhook` (Cloud Run relay in `me-central1`); otherwise CI authenticates via WIF and submits the same Cloud Build config directly.

Details: [GITHUB.md](GITHUB.md) · [ARCHITECTURE §3.2](ARCHITECTURE.md#32-ci-harness-github-actions) · [README §7](../README.md#7-continuous-integration--delivery-automation).

**Note:** The webhook URL is for CI deploy triggers only (POST + Bearer token). Open **`dubai-web`** for the school finder UI.

### 9.5 Verify production (GCP)

```bash
curl -fsS https://dubai-api-XXXX.run.app/
curl -fsS https://dubai-api-XXXX.run.app/api/facets
# Open https://dubai-web-XXXX.run.app
```

---

## 10. Production shutdown — Google Cloud

| Goal | Action |
| --- | --- |
| Stop serving traffic (web) | Cloud Run → service → **Manage traffic** → 0% to latest revision, or delete service |
| Stop API | Same for `dubai-api` |
| Pause sync | Disable Scheduler job `dubai-sync-trigger` |
| Scale to zero (default web) | Automatic when idle; API may use `minScale: 1` — set to 0 to stop billing |
| Remove everything | Delete Cloud Run services, Job, Scheduler job, Aura instance |

```bash
gcloud scheduler jobs pause dubai-sync-trigger --location=me-central1
gcloud run services delete dubai-web --region=me-central1
gcloud run services delete dubai-api --region=me-central1
gcloud run jobs delete dubai-sync --region=me-central1
```

Neo4j Aura: pause or delete from the Aura console (data retained on pause per Aura plan).

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `docker.sock` connection refused | Docker Desktop not running | Open Docker Desktop; wait ~30s; retry |
| Neo4j container **Exited (1)** | Stale container state | `docker compose rm -sf neo4j && docker compose up -d neo4j` |
| "Could not load filter options" / empty facet dropdowns | API down or SSR facet fetch failed | Start API (§3 Step 2); redeploy web if prod — needs server-side facet fetch in `page.tsx` |
| "Neo4j is not reachable" | Neo4j down or wrong password | Start Neo4j; match `.env` password to volume |
| `401` / auth errors to Neo4j | Password mismatch | Use original password or `docker compose down -v` + re-init |
| Empty search results | Graph empty | `uv run python -m dubai` |
| Ask panel errors | No LLM key / wrong model | Use `github:gpt-4o-mini` with `GITHUB_TOKEN`; for other providers run `uv sync --extra providers` and set the matching API key |
| Non-GitHub model "unavailable" in prod | Missing provider package or secret | Redeploy with `./scripts/gcp_deploy.sh` (Docker includes `--extra providers`); add keys to `.env` / Secret Manager |
| `github:llama-3.3-70b` multi-tool error | Provider rejects parallel tool calls | Fixed in code via `parallel_tool_calls=False` — redeploy API |
| Ask returns schools ≤70k for "fees greater than 70000" | Wrong budget direction | Fixed: Ask uses `min_budget_aed` — redeploy API |
| Ask searches UK schools for "schools in UK" | Foreign location vs curriculum | Preflight refuses `schools in/of/from UK`; `UK curriculum` still searches Dubai — redeploy API |
| Ask searches for "rent" questions | Rent is not KHDA tuition | Preflight returns fee-term refusal — redeploy API |
| CORS error | Wrong browser origin | Open `http://localhost:3000` locally; in prod use the exact web URL from `gcloud run services describe dubai-web` |
| `sharp` missing on web start | Standalone build | `npm install` in `web/`; use `node .next/standalone/server.js` |
| `npm run dev` from repo root | Wrong directory | `cd web` first |
| `uvicorn` from `web/` | Wrong directory | Run from **repo root** |
| Eval `sentence_transformers` missing | Optional extra not installed | `uv sync --extra evals` |
| Cloud Build `storage.objects.get` 403 | Compute / Cloud Build SA lacks GCS access | Re-run `./scripts/gcp_deploy.sh`; wait 1–2 min for IAM propagation |
| Cloud Build `invalid build.service_account` | Do not set `serviceAccount` in cloudbuild yaml on new GCP projects | Fixed in repo — leave unset; Cloud Build picks default SA |
| Cloud Build `uploadArtifacts` denied | Missing Artifact Registry IAM | Re-run deploy script (grants repo + project roles) |

---

## 12. Quick reference cards

### Dev — start (hybrid)

```bash
# Docker Desktop must be running
docker compose up -d neo4j
uv run uvicorn api_service:app --reload          # repo root, Terminal 2
cd web && npm run dev                            # Terminal 3
uv run python -m dubai                            # first time / refresh
```

### Dev — stop (hybrid)

```bash
# Ctrl+C web and API terminals
docker compose stop neo4j
```

### Prod — start (Compose VM)

```bash
docker compose up -d --build
# first time: constraints + sync (§7.3)
```

### Prod — stop (Compose VM)

```bash
docker compose stop          # keep data
docker compose down          # remove containers, keep volumes
docker compose down -v       # wipe graph
```

### Health checks

```bash
curl -fsS http://localhost:8000/
curl -fsS http://localhost:8000/api/facets
curl -fsS http://localhost:3000/
docker compose ps
```

---

*Last updated: 2026-06-10 — Ask preflight guards, min_budget_aed, SSR facets, multi-provider Docker image, QA guard evaluators, prod CORS URL note.*
