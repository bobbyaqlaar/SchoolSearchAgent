#!/usr/bin/env bash
# Deploy Aqlaar Dubai platform to Google Cloud Run (API + web + optional sync job).
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (`gcloud auth login`)
#   - Billing enabled on the GCP project
#   - Neo4j Aura (or reachable Neo4j) — set NEO4J_URI to neo4j+s://…
#   - Root `.env` with NEO4J_PASSWORD, GITHUB_TOKEN (and optional OPENAI_API_KEY)
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   export GCP_REGION=me-central1          # optional, default me-central1
#   export NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
#   ./scripts/gcp_deploy.sh
#
# Or load from .env:
#   set -a && source .env && set +a && ./scripts/gcp_deploy.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  # pydantic-settings uses NEO4J_USER; tolerate legacy NEO4J_USERNAME in .env
  NEO4J_USER="${NEO4J_USER:-${NEO4J_USERNAME:-neo4j}}"
fi

GCP_PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}}"
GCP_REGION="${GCP_REGION:-me-central1}"
GCP_REPO="${GCP_REPO:-dubai}"
NEO4J_URI="${NEO4J_URI:-${NEO4J_AURA_URI:-}}"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}==>${NC} $*"; }
die() { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

command -v gcloud >/dev/null 2>&1 || die "gcloud not found. Install: brew install --cask google-cloud-sdk"

if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | grep -q .; then
  die "Not logged in. Run: gcloud auth login"
fi

if [[ -z "$GCP_PROJECT_ID" || "$GCP_PROJECT_ID" == "(unset)" ]]; then
  die "Set GCP_PROJECT_ID in .env, or run: gcloud config set project PROJECT_ID"
fi

if [[ -z "$NEO4J_URI" || "$NEO4J_URI" == *REPLACE* ]]; then
  die "Set NEO4J_URI to your Aura Bolt URI (neo4j+s://….databases.neo4j.io)"
fi

if [[ "$NEO4J_URI" == *localhost* || "$NEO4J_URI" == *127.0.0.1* ]]; then
  die "NEO4J_URI must be your Aura URI for GCP deploy, not localhost. Create Aura at https://neo4j.com/cloud/aura/"
fi

if [[ -z "${NEO4J_PASSWORD:-}" ]]; then
  die "Set NEO4J_PASSWORD in .env or environment"
fi

log "Project: $GCP_PROJECT_ID  Region: $GCP_REGION  Neo4j: $NEO4J_URI"
gcloud config set project "$GCP_PROJECT_ID" >/dev/null

log "Enabling required APIs (idempotent)…"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  --quiet

log "Ensuring Artifact Registry repo ${GCP_REPO}…"
if ! gcloud artifacts repositories describe "$GCP_REPO" \
  --location="$GCP_REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$GCP_REPO" \
    --repository-format=docker \
    --location="$GCP_REGION" \
    --description="KHDA school search images"
fi

PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"
RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
GCB_AGENT="service-${PROJECT_NUMBER}@gcb-cloudbuild-iam.gserviceaccount.com"

grant_project_role() {
  local member="$1"
  local role="$2"
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="$member" \
    --role="$role" \
    --quiet >/dev/null 2>&1 || true
}

log "Granting Cloud Build + Cloud Run IAM (fixes storage / Artifact Registry 403)…"
# Legacy default compute SA — used by Cloud Build on many projects when no SA is specified
grant_project_role "serviceAccount:${RUN_SA}" "roles/storage.objectAdmin"
grant_project_role "serviceAccount:${RUN_SA}" "roles/logging.logWriter"
grant_project_role "serviceAccount:${RUN_SA}" "roles/artifactregistry.writer"
grant_project_role "serviceAccount:${RUN_SA}" "roles/cloudbuild.builds.builder"
# Cloud Build worker SA + Google-managed agent
grant_project_role "serviceAccount:${CLOUDBUILD_SA}" "roles/storage.admin"
grant_project_role "serviceAccount:${CLOUDBUILD_SA}" "roles/run.admin"
grant_project_role "serviceAccount:${CLOUDBUILD_SA}" "roles/iam.serviceAccountUser"
grant_project_role "serviceAccount:${CLOUDBUILD_SA}" "roles/artifactregistry.writer"
grant_project_role "serviceAccount:${CLOUDBUILD_SA}" "roles/secretmanager.secretAccessor"
grant_project_role "serviceAccount:${CLOUDBUILD_SA}" "roles/cloudbuild.builds.builder"
grant_project_role "serviceAccount:${GCB_AGENT}" "roles/cloudbuild.serviceAgent"

# Repository-level Artifact Registry access (required for image push on some org policies)
if gcloud artifacts repositories describe "$GCP_REPO" --location="$GCP_REGION" >/dev/null 2>&1; then
  for sa in "$CLOUDBUILD_SA" "$RUN_SA"; do
    gcloud artifacts repositories add-iam-policy-binding "$GCP_REPO" \
      --location="$GCP_REGION" \
      --member="serviceAccount:${sa}" \
      --role="roles/artifactregistry.writer" \
      --quiet >/dev/null 2>&1 || true
  done
fi

# Bucket-level binding (some org policies require explicit bucket IAM)
CLOUDBUILD_BUCKET="${GCP_PROJECT_ID}_cloudbuild"
if gcloud storage buckets describe "gs://${CLOUDBUILD_BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets add-iam-policy-binding "gs://${CLOUDBUILD_BUCKET}" \
    --member="serviceAccount:${RUN_SA}" \
    --role="roles/storage.objectAdmin" \
    --quiet >/dev/null 2>&1 || true
  gcloud storage buckets add-iam-policy-binding "gs://${CLOUDBUILD_BUCKET}" \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/storage.objectAdmin" \
    --quiet >/dev/null 2>&1 || true
fi

ensure_secret() {
  local name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    log "Skipping secret ${name} (empty value)"
    return 0
  fi
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    log "Secret ${name} exists — adding new version"
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=-
  else
    log "Creating secret ${name}"
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=-
  fi
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${RUN_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null 2>&1 || true
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null 2>&1 || true
}

log "Syncing secrets to Secret Manager…"
LANGCHAIN_API_KEY="${LANGCHAIN_API_KEY:-${LANGSMITH_API_KEY:-}}"
LANGCHAIN_PROJECT="${LANGCHAIN_PROJECT:-dubai-graph-sync-agent}"
SYNC_LANGSMITH_PRICING="${SYNC_LANGSMITH_PRICING:-false}"
SYNC_LANGSMITH_PRICING_WRITE="${SYNC_LANGSMITH_PRICING_WRITE:-false}"
ensure_secret "neo4j-pass" "${NEO4J_PASSWORD}"
ensure_secret "github-token" "${GITHUB_TOKEN:-unused}"
ensure_secret "openai-key" "${OPENAI_API_KEY:-unused}"
ensure_secret "google-key" "${GOOGLE_API_KEY:-unused}"
ensure_secret "groq-key" "${GROQ_API_KEY:-unused}"
ensure_secret "langchain-key" "${LANGCHAIN_API_KEY:-unused}"

log "Phase 1/3 — Build & push API image (Cloud Build)…"
gcloud builds submit --project="$GCP_PROJECT_ID" --config deploy/cloudbuild-api.yaml \
  --substitutions="_REGION=${GCP_REGION},_REPO=${GCP_REPO}"

API_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_REPO}/api:latest"
log "Deploying API to Cloud Run…"
gcloud run deploy dubai-api \
  --project="$GCP_PROJECT_ID" \
  --image="$API_IMAGE" \
  --region="$GCP_REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --command=uv \
  --args=run,uvicorn,api_service:app,--host,0.0.0.0,--port,8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --set-secrets=NEO4J_PASSWORD=neo4j-pass:latest,GITHUB_TOKEN=github-token:latest,OPENAI_API_KEY=openai-key:latest,GOOGLE_API_KEY=google-key:latest,GROQ_API_KEY=groq-key:latest,LANGCHAIN_API_KEY=langchain-key:latest \
  --set-env-vars="NEO4J_URI=${NEO4J_URI},NEO4J_USER=neo4j,CORS_ORIGINS=http://localhost:3000,LANGCHAIN_TRACING_V2=true,LANGCHAIN_PROJECT=${LANGCHAIN_PROJECT},SYNC_LANGSMITH_PRICING=${SYNC_LANGSMITH_PRICING},SYNC_LANGSMITH_PRICING_WRITE=${SYNC_LANGSMITH_PRICING_WRITE}" \
  --quiet

API_URL="$(gcloud run services describe dubai-api \
  --region="$GCP_REGION" \
  --format='value(status.url)')"
log "API URL: ${API_URL}"

log "Phase 2/3 — Build & push web image (API URL baked into Next.js)…"
gcloud builds submit --project="$GCP_PROJECT_ID" --config deploy/cloudbuild-web.yaml \
  --substitutions="_REGION=${GCP_REGION},_REPO=${GCP_REPO},_API_URL=${API_URL}"

WEB_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_REPO}/web:latest"
log "Deploying web to Cloud Run…"
gcloud run deploy dubai-web \
  --project="$GCP_PROJECT_ID" \
  --image="$WEB_IMAGE" \
  --region="$GCP_REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --quiet

WEB_URL="$(gcloud run services describe dubai-web \
  --region="$GCP_REGION" \
  --format='value(status.url)')"
log "Web URL: ${WEB_URL}"

log "Phase 3/3 — Update API CORS to allow web origin…"
gcloud run services update dubai-api \
  --region="$GCP_REGION" \
  --update-env-vars="CORS_ORIGINS=${WEB_URL}" \
  --quiet

log "Deploy complete."
echo ""
echo "  Web:  ${WEB_URL}"
echo "  API:  ${API_URL}"
echo ""
echo "Next steps:"
echo "  1. Open ${WEB_URL} — filters should load if Neo4j has data"
echo "  2. Run initial sync (Cloud Run Job or locally against Aura):"
echo "       NEO4J_URI=${NEO4J_URI} uv run python -m dubai"
echo "  3. Optional — create scheduled sync job:"
echo "       ./scripts/gcp_sync_job.sh"
