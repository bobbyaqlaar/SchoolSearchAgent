# Dubai Private Education Knowledge Graph Pipeline & REST Microservice
## System Engineering Specification (Phase 1 & Phase 2 Consolidated)

This document serves as the complete functional blueprint, structural data model, testing architecture, and automated continuous delivery matrix for the enterprise-grade Dubai School Analytics Graph Platform.

> **New here?** Use **[§9 Operations Guide](#9-operations-guide--deploy-start-stop--refresh)** below for step-by-step deploy, startup, shutdown, and reload of each tier (web, API, Neo4j) locally and on Google Cloud. The [User Manual](docs/USER_MANUAL.md) adds troubleshooting and evaluation workflows. See [Architecture](docs/ARCHITECTURE.md) for requirements and design. **Publishing to GitHub:** [docs/GITHUB.md](docs/GITHUB.md).

---

## 1. System Architecture Blueprint

The system utilizes a decoupled multi-tier containerized layout linked together over an isolated virtual network bridge.

```text
       [ Responsive Multi-Device Web App UI ] (Phase 2 Frontend Component)
                          │
                          ▼ (HTTPS JSON Payload containing `selected_model` parameter)
       [ FastAPI REST Microservice Middleware Layer ]
                          │
       [ LangGraph Sync Pipeline (Excel parse — no LLM) ]
          ├── 1. Download workbook (DubaiPrivateSchoolsOpenData.xlsx)
          ├── 2. Delta Check Optimization Gateway (Bypass loop if MD5 hashes match)
          ├── 3. Open-Data Excel Parser (workbook rows → SchoolDataModel)
          └── 4. Inline Guardrail Validator (validate_school before MERGE)
                          │
         ┌────────────────┴────────────────┐
         ▼ (If Validated Pass)             ▼ (If Corrupted / Failed Validation)
[ Neo4j Graph Database ]          [ Skip write + record failure to LangSmith ]
   └── Idempotent Cypher MERGE

       [ POST /api/ask — LLM + Neo4j graph tools ]
                          │
         ┌────────────────┴──────────────────┬─────────────────┬────────────────┐
         ▼ (Runtime Dynamic Router Engine)   ▼                 ▼                ▼
[ OpenAI Model Hub ]              [ Anthropic Hub ]     [ Google Hub ]    [ Grok Hub ]
         │                                   │                 │                │
         └────────────────┬──────────────────┴─────────────────┼────────────────┘
                          │                                    │
                          ▼                                    ▼
[ TogetherAI / Groq Hub ]                               [ Local Engine Hub ]
                          │                                    │
                          └──────────────────┬─────────────────┘
                                             ▼
                          [ Token/cost telemetry → API envelope ]
```

---

## 2. Structural Graph Data Model

The Neo4j database topology enforces strict entity constraints to block data duplication during incremental processing executions.

### Node Definitions
*   **`School`**: `{id: String (Unique Slugified Key), name: String, last_sync_hash: String}`
*   **`Location`**: `{neighborhood: String (Unique Key), city: String}`
*   **`Curriculum`**: `{type: String (Unique Key, e.g., 'UK', 'US', 'IB', 'Indian')}`
*   **`InspectionRating`**: `{id: String (Unique Composite, e.g., 'school-id_2025-2026'), academic_year: String, rating: String}`
*   **`FeeStructure`**: `{id: String (Unique Composite, e.g., 'school-id_year-7'), grade: String, tuition_fee: Float, currency: String, last_updated_timestamp: DateTime}`

### Relationship Vectors
*   `(:School) -[:OFFERS]-> (:Curriculum)`
*   `(:School) -[:LOCATED_IN]-> (:Location)`
*   `(:School) -[:RATED]-> (:InspectionRating)`
*   `(:School) -[:HAS_FEES]-> (:FeeStructure)` *Note: Every grade level is mapped as an independent, searchable entity.*

---

## 3. Comprehensive Requirements Catalog

### Functional Requirements
1. **KHDA Open-Data Ingestion**: Download the official **Dubai Private Schools** Excel workbook from [DubaiPrivateSchoolsOpenData.xlsx](https://web.khda.gov.ae/KHDA/media/KHDA/DubaiPrivateSchoolsOpenData.xlsx) (also listed on [KHDA data & statistics](https://web.khda.gov.ae/en/Resources/KHDA-data-statistics)), with local cache fallback at `dubai_open_data_cache/private_schools.xlsx`. No third-party feeds, fact-sheet HTML, PDF scraping, or other KHDA workbooks.
2. **Granular Pricing Breakdown**: Deconstruct and index complex tuition tables into individual class/grade instances.
3. **Incremental State Analysis**: Compute `MD5` content hashes to execute database property updates only when modifications are detected.
4. **Responsive UI Engine**: Cross-device dashboard layout rendering allowing multi-variable filtering by curriculum, budget, area, and grade.
5. **Runtime Model Selection (Ask/Q&A only)**: Expose explicit backend controls on `POST /api/ask` to dynamically pass runtime target requests to specific models. Sync ingestion is deterministic Excel parsing — no LLM. Install optional providers with `uv sync --extra providers`; Docker API image includes them by default (`Dockerfile`).
    *   **OpenAI**: `gpt-4o`, `gpt-4o-mini`
    *   **Google** (registry ids; upstream model `gemini-2.0-flash`): `gemini-1.5-pro`, `gemini-1.5-flash`
    *   **Groq** (registry id `qwen-2.5-72b-instruct`; upstream `qwen/qwen3-32b`): open-source API tier
    *   **xAI Grok** (registry ids; upstream `grok-4.3`, `grok-4.20-0309-non-reasoning`): `grok-2-beta-foundation`, `grok-2-beta-fast`
    *   **GitHub Models** (free dev tier; `parallel_tool_calls=False` for multi-tool stability): `github:gpt-4o-mini`, `github:gpt-4o`, `github:llama-3.3-70b`, `github:deepseek-v3`
    *   **Optional** (uncomment in `dubai/llm_router.py` when keys/backends are configured): Anthropic `claude-3-5-sonnet`, DeepSeek `deepseek-v3` / `deepseek-r1`, local Ollama/vLLM `llama-3.1` / `llama-3.3`, `gemma-2`

### Real-Time Evaluation & Quality Constraints
1. **Ingestion guardrails**: Intercept 100% of parsed sync payloads at the application perimeter via `validate_school()` before committing database changes.
2. **Ask preflight guards**: Intercept out-of-scope Ask questions (`rent`/`rental`, foreign school locations, off-topic) via `preflight_ask_response()` before any LLM or tool call.
3. **Token & Cost Allocation**: Log total input tokens, output tokens, and cost mapping per **Ask** generation loop using in-line performance event triggers across all specified cloud/local models.
4. **Graceful Failure Interception**: Catch exceptions, structural validation breaks, or low schema scores. Instead of throwing stack dumps, intercept the error and emit a user-friendly standard negative response.

### Non-Functional Requirements
1. **Performance**: API p95 latency under 400ms for cached graph queries; streaming token responses for LLM generation paths.
2. **Scalability**: Stateless API and frontend tiers, horizontally scalable behind a load balancer; Neo4j tuned for read-heavy traffic.
3. **Availability**: Target 99.5% uptime with health-checked containers and automatic restart policies.
4. **Security**: Secrets via environment/secret manager, HTTPS-only transport, CORS allow-list, input validation on all routes.
5. **Observability**: Structured logs, LangSmith tracing, and request/cost metrics exported per tier.
6. **Accessibility**: Frontend meets WCAG 2.1 AA (keyboard navigation, ARIA labels, contrast ratios).
7. **Portability**: Identical container images run on local MacBook and Google Cloud with no code changes.

---

## 3.5 Responsive Web Application Front End

A standalone responsive client consumes the FastAPI microservice and renders the school analytics dashboard across desktop, tablet, and mobile breakpoints.

### Technology Stack
*   **Framework**: Next.js (App Router) + React + TypeScript.
*   **Styling**: Tailwind CSS with a mobile-first responsive grid; dark/light theme support.
*   **Data Layer**: React Server Components fetch filter facets on first paint (`web/app/page.tsx` → `initialFacets`); Client Components handle interactive search and retry if SSR fetch fails.
*   **State/Fetching**: Server Actions and typed route handlers for transactional calls to the REST microservice.

### Frontend Functional Requirements
1. **School Search & Discovery**: Full-text and faceted search over indexed schools surfaced from the Neo4j graph.
2. **Multi-Variable Filtering**: Interactive filters by curriculum (`UK`/`US`/`IB`/`Indian`), budget range, neighborhood/area, grade level, and inspection rating.
3. **School Detail View**: Per-school page rendering curriculum, location, **latest KHDA inspection rating** (single academic year from open data), and grade-by-grade fee breakdown.
4. **Comparison Mode**: Side-by-side comparison; select schools via checkboxes on search/Ask results or open `/compare?ids=…`.
5. **Runtime Model Selector**: UI control to pass the `selected_model` parameter to the backend across all six engine matrices.
6. **Live Status & Telemetry Panel**: Display per-request token counts, cost, and selected model returned by the API.
7. **Graceful Error States**: Render user-friendly standard negative responses (no stack traces) when the backend emits a failure payload.
8. **Responsive Layout Engine**: Fluid breakpoints (mobile, tablet, desktop), touch-friendly controls, and skeleton loading states.

### Frontend Non-Functional Requirements
1. **Responsiveness**: Single codebase adapting from 320px mobile to wide desktop with no horizontal scroll.
2. **Performance**: First Contentful Paint under 1.5s on broadband; route-level code splitting and image optimization.
3. **Accessibility**: WCAG 2.1 AA compliance.
4. **Type Safety**: Strict TypeScript, explicit return types on all exported functions and route handlers, no `any`.
5. **Configurability**: Backend base URL injected via `NEXT_PUBLIC_API_BASE_URL` for local vs. cloud targets.

---

## 3.6 REST API Endpoints

All data responses use a consistent `Envelope` shape: `{ "data": ..., "telemetry": { ... } }`. CORS is restricted to the `CORS_ORIGINS` allow-list (default `http://localhost:3000`).

| Method | Path | Purpose | Response `data` |
| --- | --- | --- | --- |
| `GET` | `/` | Health check | service status |
| `GET` | `/api/models` | List selectable model ids (all providers incl. `github:*`) | `string[]` |
| `GET` | `/api/schools/search` | Multi-facet search (`grade`, `max_budget`, `curriculum`, `khda_rating`, `neighborhood`) — ceiling budget only; floor budget (`min_budget`) is Ask-tool-only | `SearchResult[]` |
| `GET` | `/api/schools/{id}` | Full school profile (curricula, latest rating, fee table) | `SchoolDetail` (`404` if missing) |
| `GET` | `/api/schools/compare?ids=a&ids=b` | Side-by-side comparison rows | `CompareRow[]` |
| `GET` | `/api/facets` | Distinct curriculums, neighborhoods, ratings, **grades** for filter UIs | `Facets` |
| `POST` | `/api/ask` | Graph-backed Q&A; body `{ question, selected_model? }` | `{ answer, model, schools[] }` + per-call `telemetry` (`422` on unknown model, `503` if model/key unavailable) |

`POST /api/ask` runs **preflight guards** in `dubai/ask_prompt.py` before any LLM call: rent/rental/lease → fee-term refusal; `schools in/of/from UK` (foreign location) → jurisdiction refusal; off-topic → jurisdiction refusal. In-scope questions route through `get_ask_chat_model()` (disables `parallel_tool_calls` for OpenAI/GitHub/DeepSeek) and LangChain graph tools (`search_schools` with `max_budget_aed` / `min_budget_aed`, budget/rating search, grade search, name lookup). **Budget direction:** under/at most → `max_budget_aed`; above/greater than → `min_budget_aed` (school-level cheapest tier must exceed floor). Tool results populate `schools[]` in `data` for the results table; token counts and `cost_usd` appear in `telemetry`. Per-model rates come from `config/model_pricing.yaml` (see §9.4 **Token pricing**).

---

## 4. Environment Configuration (`pyproject.toml`)

Modern PEP 621 workspace managed via **`uv`**. See the live file for exact pins; summary:

```toml
[project]
name = "schoolsearchagent"
version = "0.1.0"
description = "Dubai KHDA private education knowledge graph pipeline and REST microservice"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",
    "neo4j>=5.15.0",
    "pandas>=2.2.0",
    "openpyxl>=3.1.2",
    "requests>=2.31.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "python-dotenv>=1.0.1",
    "langsmith>=0.1.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.28.0",
]

[project.optional-dependencies]
providers = [  # multi-provider Ask routing only
    "langchain-anthropic>=0.2.0",
    "langchain-google-genai>=2.0.0",
    "langchain-xai>=0.1.0",
    "langchain-groq>=0.2.0",
    "langchain-ollama>=0.2.0",
]
evals = [
    "sentence-transformers>=3.0.0",
    "numpy>=1.26.0",
]
```

Sync CLI: `uv run python -m dubai` (module `dubai/cli.py`).

---

## 5. Security Environment Blueprint (`.env.example`)

Copy this baseline blueprint to a localized `.env` file. Ensure this file is added to your `.gitignore` parameters.

```env
# OpenAI Hub API Access Configurations
OPENAI_API_KEY=sk-proj-placeholder-token-value

# Anthropic Hub API Access Configurations (Phase 2 Multi-LLM Routing)
ANTHROPIC_API_KEY=sk-ant-placeholder-token-value

# Google Gemini Hub API Access Configurations
GOOGLE_API_KEY=AIzaSyPlaceholderTokenValue_xxxx

# xAI Grok Hub API Access Configurations
XAI_API_KEY=xai-placeholder-token-value

# Open-Source API Core Endpoints (TogetherAI, Groq, or DeepSeek API)
TOGETHER_API_KEY=together-placeholder-token-value
GROQ_API_KEY=gsk-placeholder-token-value
DEEPSEEK_API_KEY=sk-deepseek-placeholder-token-value

# GitHub Models — free OpenAI-compatible dev inference (https://models.github.ai/inference)
GITHUB_TOKEN=ghp_placeholder_token_value
GITHUB_MODELS_BASE_URL=https://models.github.ai/inference

# Local Inference Hub Endpoint Configuration (Ollama / Local vLLM instance)
LOCAL_LLM_BASE_URL=http://docker.internal

# Neo4j Production Graph Core Credentials
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_configured_secure_password_here

# LangSmith Observability & Deep Explainability Telemetry
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_placeholder_telemetry_key
# Alias accepted by gcp_deploy.sh when syncing secrets:
# LANGSMITH_API_KEY=lsv2_pt_placeholder_telemetry_key
LANGCHAIN_PROJECT="dubai-graph-sync-agent"

# Ask token pricing (config/model_pricing.yaml). Optional LangSmith sync at API startup:
# SYNC_LANGSMITH_PRICING=true
# SYNC_LANGSMITH_PRICING_WRITE=false
# MODEL_PRICING_PATH=config/model_pricing.yaml
# LANGSMITH_PRICING_PROBES_PATH=config/langsmith_pricing_probes.yaml

# Frontend Web App Configuration (Next.js)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# API CORS allow-list (comma-separated origins)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

---

## 6. Multi-Container Deployment Framework (`docker-compose.yml`)

This multi-container architecture orchestrates your local services and handles internal routing configurations automatically.

```yaml
services:
  # --- Graph database ---
  neo4j:
    image: neo4j:5.15.0-community
    container_name: dubai_neo4j_db
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    networks:
      - dubai_network
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p ${NEO4J_PASSWORD} 'RETURN 1'"]
      interval: 10s
      timeout: 5s
      retries: 5

  # --- LangGraph sync worker ---
  sync_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: dubai_sync_agent_worker
    volumes:
      - .:/app
    env_file:
      - .env
    environment:
      - NEO4J_URI=bolt://neo4j:7687
    depends_on:
      neo4j:
        condition: service_healthy
    networks:
      - dubai_network

  # --- FastAPI REST gateway ---
  api_gateway:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: dubai_rest_api_service
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - NEO4J_URI=bolt://neo4j:7687
    command: uv run uvicorn api_service:app --host 0.0.0.0 --port 8000
    depends_on:
      neo4j:
        condition: service_healthy
    networks:
      - dubai_network
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/ || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 5

  # --- Next.js responsive frontend (standalone image listens on 8080) ---
  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: dubai_web
    ports:
      - "3000:8080"
    environment:
      - NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
    depends_on:
      - api_gateway
    networks:
      - dubai_network

networks:
  dubai_network:
    driver: bridge

volumes:
  neo4j_data:
  neo4j_logs:
```

---

## 7. Continuous Integration & Delivery Automation

GitHub Actions (`.github/workflows/llm_regression_tests.yml`) runs on every PR and merge to `main`:

```yaml
name: CI — Unit, Frontend & LLM Evals
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv python install
      - run: uv sync --frozen --extra providers --extra evals
      - run: uv run pytest -v
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm install && npm test && npm run build
        env:
          NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
  llm-evals:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv python install
      - run: uv sync --frozen --extra providers --extra evals
      - run: uv run python -m evals.eval_parsing
        env:
          LANGCHAIN_TRACING_V2: "true"
          LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}
          LANGCHAIN_PROJECT: "dubai-graph-sync-agent"
  deploy-production:
    needs: [unit-tests, frontend, llm-evals]
    if: github.ref == 'refs/heads/main'
    # ... webhook deploy step
```

The parsing eval needs **LangSmith only** — no LLM provider API key.

---

## 8. Essential Production Maintenance Scripts

DB baseline initializer — run inside the Neo4j browser shell (http://localhost:7474) before first-pass runs (also auto-applied via `scripts/init_constraints.cypher`):

```cypher
// Enforce unique identification data structures across all nodes
CREATE CONSTRAINT unique_school_id IF NOT EXISTS FOR (s:School) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT unique_location_neighborhood IF NOT EXISTS FOR (l:Location) REQUIRE l.neighborhood IS UNIQUE;
CREATE CONSTRAINT unique_curriculum_type IF NOT EXISTS FOR (c:Curriculum) REQUIRE c.type IS UNIQUE;
// Accelerate numerical budget-range lookups across class fee instances
CREATE INDEX fee_lookup_range_idx IF NOT EXISTS FOR (f:FeeStructure) ON (f.tuition_fee, f.grade);
```

Server execution run flags via `uv`:

```bash
# Run localized background sync manually
uv run python -m dubai

# Fire open-data parsing regression eval (LangSmith; ci_gate enforced)
uv run python -m evals.eval_parsing

# Local debug without ci_gate exit code:
uv run python -m evals.eval_parsing --skip-ci-gate

# Launch the REST API locally
uv run uvicorn api_service:app --reload
```

---

## 9. Operations Guide — Deploy, Start, Stop & Refresh

This section is the **step-by-step runbook** for each application tier and for the full stack. Commands assume the **repository root** unless noted.

### 9.0 Component map

| Tier | What it is | Local port | Hybrid dev (recommended) | Full Docker Compose |
| --- | --- | --- | --- | --- |
| **Database** | Neo4j graph | Bolt `7687`, Browser `7474` | `docker compose up -d neo4j` | `docker compose up -d neo4j` |
| **Backend API** | FastAPI + Uvicorn | `8000` | `uv run uvicorn api_service:app --reload` | Container `dubai_rest_api_service` |
| **Frontend** | Next.js web app | `3000` (dev) / `8080` (Cloud Run & Compose container) | `cd web && npm run dev` | Container `dubai_web` → host `:3000` |
| **Data sync** | KHDA Excel → Neo4j | — | `uv run python -m dubai` | Container `dubai_sync_agent_worker` |

**Production (Google Cloud):** API and web run on **Cloud Run**; Neo4j on **Aura** (or a VM). Deploy with `./scripts/gcp_deploy.sh`.

**One-time setup** (all modes):

```bash
cp .env.example .env          # fill NEO4J_PASSWORD, GITHUB_TOKEN, etc. — never commit .env
uv sync --extra providers     # optional LLM providers for non-GitHub models
cd web && npm install && cd ..
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` for local dev. Use the **same** `NEO4J_PASSWORD` in `.env` and in Docker Compose.

---

### 9.1 Local development — Hybrid (recommended)

Best for daily coding: Neo4j in Docker; API and web on the host with **hot reload**.

#### Start — whole stack

| Step | Terminal | Command | Verify |
| --- | --- | --- | --- |
| 0 | — | Open **Docker Desktop** (macOS/Windows) | `docker info` succeeds |
| 1 | 1 | `docker compose up -d neo4j` | `docker compose ps` → neo4j **healthy** (~30s first boot) |
| 2 | 2 | `uv run uvicorn api_service:app --reload --host 127.0.0.1 --port 8000` | `curl -fsS http://127.0.0.1:8000/api/facets` |
| 3 | 3 | `cd web && npm run dev` | Open http://localhost:3000 |
| 4 | any | `uv run python -m dubai` | First time or empty graph only |

#### Start — one component only

| Component | Start command |
| --- | --- |
| **Neo4j only** | `docker compose up -d neo4j` |
| **API only** | `uv run uvicorn api_service:app --reload --host 127.0.0.1 --port 8000` (Neo4j must already be up) |
| **Web only** | `cd web && npm run dev` (API must already be up) |
| **Load / refresh data** | `uv run python -m dubai` (optional: `--force` to rewrite all fees) |

#### Stop — whole stack

Stop in **reverse** order:

| Step | How |
| --- | --- |
| 1 | **Ctrl+C** in the web terminal (`npm run dev`) |
| 2 | **Ctrl+C** in the API terminal (Uvicorn) |
| 3 | `docker compose stop neo4j` — keeps graph data in Docker volume |

#### Stop — one component only

| Component | Stop command |
| --- | --- |
| **Web** | Ctrl+C in web terminal |
| **API** | Ctrl+C in API terminal |
| **Neo4j** | `docker compose stop neo4j` |
| **Remove Neo4j container** (data kept) | `docker compose down neo4j` |

#### Reload / refresh — Hybrid

| Goal | Action |
| --- | --- |
| **API code change** | Save file — Uvicorn `--reload` picks it up automatically |
| **Web code change** | Save file — Next.js dev server hot-reloads |
| **Neo4j config / restart** | `docker compose restart neo4j` |
| **Refresh school data** | `uv run python -m dubai` |
| **Full graph reset** | `docker compose down -v` then repeat first-time init (§9.0 constraints + sync) |

**First-time graph init** (after fresh Neo4j volume):

```bash
docker exec -i dubai_neo4j_db cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  < scripts/init_constraints.cypher
uv run python -m dubai
```

---

### 9.2 Local development — Full Docker Compose

Runs Neo4j, sync worker, API, and web as containers (closer to production).

#### Start — whole stack

```bash
docker compose up -d --build
docker compose ps                    # wait until services are healthy
```

| Service | Container | URL |
| --- | --- | --- |
| Neo4j Browser | `dubai_neo4j_db` | http://localhost:7474 |
| API | `dubai_rest_api_service` | http://localhost:8000 |
| Web | `dubai_web` | http://localhost:3000 |

First time only:

```bash
docker exec -i dubai_neo4j_db cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  < scripts/init_constraints.cypher
docker compose exec sync_agent uv run python -m dubai
```

#### Start — one component only

```bash
docker compose up -d neo4j              # database
docker compose up -d api_gateway        # API (needs healthy neo4j)
docker compose up -d web                # frontend (needs api_gateway)
docker compose up -d sync_agent         # background sync worker
```

#### Stop — whole stack

```bash
docker compose down                     # remove containers; **keeps** neo4j_data volume
docker compose down -v                  # also **wipes** graph data — re-run sync after
```

#### Stop — one component only

```bash
docker compose stop api_gateway         # or: web, neo4j, sync_agent
docker compose start api_gateway        # bring one tier back
```

#### Reload / refresh — Compose

| Goal | Action |
| --- | --- |
| **Rebuild after git pull** | `docker compose up -d --build` |
| **Restart one tier** | `docker compose restart api_gateway` (or `web`, `neo4j`) |
| **Refresh school data** | `docker compose exec sync_agent uv run python -m dubai` |
| **Tail logs** | `docker compose logs -f api_gateway` |

---

### 9.3 Production — Docker Compose on a VM

Single-server deployment with TLS in front (Nginx, Caddy, or Traefik).

#### Deploy / start

1. Clone repo; create production `.env` (strong secrets, public URLs).
2. Set `NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com` and `CORS_ORIGINS=https://app.yourdomain.com`.
3. Build and start:

```bash
docker compose up -d --build
docker compose ps
```

4. First run: constraints + sync (same as §9.2 first-time block).

#### Stop

```bash
docker compose stop                   # planned maintenance; keeps data
docker compose down                   # remove containers; keep volumes
docker compose down -v                # full reset — re-init graph
```

#### Reload / refresh

```bash
docker compose up -d --build                            # redeploy after code changes
docker compose restart api_gateway                      # restart API only
docker compose exec sync_agent uv run python -m dubai    # manual data sync
```

---

### 9.4 Production — Google Cloud (Cloud Run + Neo4j Aura)

Recommended cloud layout:

| Tier | Target | Service name |
| --- | --- | --- |
| Frontend | Cloud Run | `dubai-web` |
| API | Cloud Run | `dubai-api` |
| Graph DB | Neo4j Aura | `neo4j+s://….databases.neo4j.io` |
| Nightly sync (optional) | Cloud Run Job | `dubai-sync` |
| Images | Artifact Registry | `me-central1-docker.pkg.dev/PROJECT/dubai/` |

#### Prerequisites (once)

```bash
brew install --cask google-cloud-sdk
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Create a Neo4j Aura instance at https://neo4j.com/cloud/aura/ and put the Bolt URI and password in `.env`:

```env
NEO4J_URI=neo4j+s://YOUR_AURA_ID.databases.neo4j.io
NEO4J_PASSWORD=your_aura_password
GITHUB_TOKEN=ghp_…
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_…          # or LANGSMITH_API_KEY
LANGCHAIN_PROJECT=dubai-graph-sync-agent
# optional: GCP_PROJECT_ID=YOUR_PROJECT_ID   (falls back to gcloud default project)
```

#### Deploy / start — whole stack

From repo root:

```bash
chmod +x scripts/gcp_deploy.sh
./scripts/gcp_deploy.sh
```

The script: enables GCP APIs → Artifact Registry → syncs secrets → builds & deploys **API** → builds & deploys **web** (API URL baked in) → updates API **CORS**.

**LangSmith tracing in production (enabled by default):** `./scripts/gcp_deploy.sh` turns tracing on for the Cloud Run API:

| Setting | Source | Purpose |
| --- | --- | --- |
| `LANGCHAIN_TRACING_V2=true` | Cloud Run env var on `dubai-api` | Enables LangSmith traces for Ask (`POST /api/ask`) |
| `LANGCHAIN_PROJECT` | Cloud Run env var (from `.env`, default `dubai-graph-sync-agent`) | Groups traces in the LangSmith dashboard |
| `LANGCHAIN_API_KEY` | Secret Manager `langchain-key` (from `.env` `LANGCHAIN_API_KEY` or `LANGSMITH_API_KEY`) | Authenticates trace export |

At API startup, `api_service.py` calls `configure_langsmith_tracing()` (`dubai/langsmith_env.py`) so LangChain reads the same values from the process environment. View live traces at [smith.langchain.com](https://smith.langchain.com) under project **`dubai-graph-sync-agent`** (or your `LANGCHAIN_PROJECT`).

**Token pricing (Ask only):** `CostTracker` reads USD-per-1K-token rates from `config/model_pricing.yaml` via `dubai/model_pricing.py`. LangSmith uses its own price map for trace dashboards — the app cost in `telemetry.cost_usd` is independent.

Optional **LangSmith pricing sync** at API startup (`dubai/langsmith_pricing_sync.py`):

| Setting | Default | Purpose |
| --- | --- | --- |
| `SYNC_LANGSMITH_PRICING` | `false` | `GET /api/v1/model-price-map` → merge rates for models in `MODEL_REGISTRY` |
| `SYNC_LANGSMITH_PRICING_WRITE` | `false` | When `true`, persist merged table to `config/model_pricing.yaml`; when `false`, in-memory cache only |
| `LANGSMITH_PRICING_PROBES_PATH` | `config/langsmith_pricing_probes.yaml` | Maps each registry id to a regex probe string LangSmith recognizes |
| `LANGCHAIN_API_KEY` | — | Required when sync is enabled |

Unmatched models keep existing YAML values. Enable locally or add to `.env` before `./scripts/gcp_deploy.sh` (see deploy script `set-env-vars`).

Optional sync job (`./scripts/gcp_sync_job.sh`) also sets `LANGCHAIN_TRACING_V2=true` for LangGraph sync runs. Local dev: set the same three variables in `.env` and restart Uvicorn.

Load graph data into Aura (from your laptop, using `.env` pointed at Aura):

```bash
uv run python -m dubai
```

Optional scheduled sync:

```bash
./scripts/gcp_sync_job.sh
gcloud run jobs execute dubai-sync --region=me-central1 --wait
```

**GCP Secret Manager keys** (synced from `.env` by `gcp_deploy.sh`):

| Secret | Env var source | Mounted on `dubai-api` |
| --- | --- | --- |
| `neo4j-pass` | `NEO4J_PASSWORD` | `NEO4J_PASSWORD` |
| `github-token` | `GITHUB_TOKEN` | `GITHUB_TOKEN` |
| `openai-key` | `OPENAI_API_KEY` | `OPENAI_API_KEY` |
| `google-key` | `GOOGLE_API_KEY` | `GOOGLE_API_KEY` |
| `groq-key` | `GROQ_API_KEY` | `GROQ_API_KEY` |
| `langchain-key` | `LANGCHAIN_API_KEY` or `LANGSMITH_API_KEY` | `LANGCHAIN_API_KEY` |

Cloud Run services listen on **port 8080** internally (`dubai-api` Uvicorn, `dubai-web` Next standalone). The API Docker image runs `uv sync --extra providers` so OpenAI, Google, Groq, xAI, and GitHub Models work in production when secrets are set. The web image bundles `sharp` for `next/image` in standalone mode and server-fetches facets on the home page for first-paint filter options.

#### Deploy / start — one component only

| Component | Action |
| --- | --- |
| **API only** | `gcloud builds submit --config deploy/cloudbuild-api.yaml --substitutions=_REGION=me-central1,_REPO=dubai` then `gcloud run deploy dubai-api …` (see script for full flags) |
| **Web only** | Build with API URL: `gcloud builds submit --config deploy/cloudbuild-web.yaml --substitutions=_REGION=me-central1,_REPO=dubai,_API_URL=https://…` then `gcloud run deploy dubai-web …` |
| **Database (Aura)** | Managed in Aura console — not deployed by this repo |
| **Data sync only** | `uv run python -m dubai` locally, or `gcloud run jobs execute dubai-sync --region=me-central1 --wait` |

Re-running `./scripts/gcp_deploy.sh` redeploys **both** API and web with latest code.

#### Stop — whole stack

Removes public URLs and stops Cloud Run billing for those services:

```bash
gcloud run services delete dubai-web --region=me-central1 --quiet
gcloud run services delete dubai-api --region=me-central1 --quiet
gcloud run jobs delete dubai-sync --region=me-central1 --quiet    # if created
gcloud scheduler jobs pause dubai-sync-trigger --location=me-central1   # if scheduled
```

Neo4j Aura keeps running until you pause or delete it in the Aura console (separate billing).

#### Stop — one component only

```bash
gcloud run services delete dubai-web --region=me-central1 --quiet   # frontend only
gcloud run services delete dubai-api --region=me-central1 --quiet   # API only
```

Cloud Run scales to **zero** when idle by default (`min-instances=0`); deleting services is the clean way to fully stop public access.

#### Reload / refresh — GCP

| Goal | Action |
| --- | --- |
| **Redeploy API + web after code change** | `./scripts/gcp_deploy.sh` |
| **Refresh school data in Aura** | `uv run python -m dubai` (local, `.env` → Aura) or run `dubai-sync` job |
| **Update secrets** | Edit `.env`, re-run deploy script (re-uploads secrets) |
| **Verify live** | `curl -fsS https://YOUR_API_URL/api/facets` and open web URL |

Get current URLs:

```bash
gcloud run services describe dubai-api --region=me-central1 --format='value(status.url)'
gcloud run services describe dubai-web --region=me-central1 --format='value(status.url)'
```

---

### 9.5 Health checks (all environments)

```bash
# Local API
curl -fsS http://localhost:8000/
curl -fsS http://localhost:8000/api/facets

# Local web
curl -fsS http://localhost:3000/

# Docker
docker compose ps

# GCP (replace with your Cloud Run URLs)
curl -fsS https://dubai-api-XXXX.run.app/api/facets
```

---

### 9.6 Quick reference

| Task | Hybrid dev | Full Compose | GCP |
| --- | --- | --- | --- |
| **Start all** | §9.1 start table | `docker compose up -d --build` | `./scripts/gcp_deploy.sh` |
| **Stop all** | Ctrl+C web/API + `docker compose stop neo4j` | `docker compose down` | Delete `dubai-api` + `dubai-web` services |
| **Restart API** | Ctrl+C → re-run uvicorn | `docker compose restart api_gateway` | Re-run deploy script |
| **Restart web** | Ctrl+C → `npm run dev` | `docker compose restart web` | Re-run deploy script |
| **Restart DB** | `docker compose restart neo4j` | `docker compose restart neo4j` | Aura console |
| **Refresh data** | `uv run python -m dubai` | `docker compose exec sync_agent uv run python -m dubai` | `uv run python -m dubai` or sync job |

For extended troubleshooting, evals, and CI details see [docs/USER_MANUAL.md](docs/USER_MANUAL.md).

---

## 10. Legacy Deployment Matrix (reference)

The platform ships as portable container images that run identically on a local MacBook and on Google Cloud.

### 10.1 Local MacBook (summary)

```bash
# Backend stack (graph, worker, API)
docker compose up -d

# Frontend dev server (Next.js)
cd web && npm install && npm run dev   # http://localhost:3000
```

Apple Silicon: Neo4j community supports `linux/arm64`. For local LLM inference, run Ollama natively and point `LOCAL_LLM_BASE_URL` at `http://host.docker.internal:11434`.

### 10.2 Google Cloud (summary)

| Tier | Google Cloud Target | Notes |
| --- | --- | --- |
| Frontend (Next.js) | **Cloud Run** | Containerized SSR; scales to zero; HTTPS + custom domain. |
| API Gateway (FastAPI) | **Cloud Run** | Stateless; min instances for warm latency. |
| Sync Agent (worker) | **Cloud Run Jobs** + **Cloud Scheduler** | Scheduled incremental crawl/sync runs. |
| Graph Database (Neo4j) | **GCE VM** or **Neo4j Aura** | Persistent disk or managed Aura cluster. |
| Secrets | **Secret Manager** | Inject API keys + Neo4j credentials at runtime. |
| Images | **Artifact Registry** | Stores backend + frontend container images. |

Prefer `./scripts/gcp_deploy.sh` over manual `gcloud run deploy` steps. CI from §7 builds and tests on merge to `main`; wire `DEPLOY_WEBHOOK_URL` for automated promotion.

