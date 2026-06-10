#!/usr/bin/env bash
# Create or update the nightly KHDA Excel sync Cloud Run Job.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -f .env ]] && set -a && source .env && set +a

GCP_PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
GCP_REGION="${GCP_REGION:-me-central1}"
GCP_REPO="${GCP_REPO:-dubai}"
NEO4J_URI="${NEO4J_URI:-${NEO4J_AURA_URI:-}}"
JOB_NAME="${GCP_SYNC_JOB_NAME:-dubai-sync}"
IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_REPO}/api:latest"

[[ -n "$GCP_PROJECT_ID" ]] || { echo "Set GCP_PROJECT_ID"; exit 1; }
[[ -n "$NEO4J_URI" ]] || { echo "Set NEO4J_URI"; exit 1; }

if gcloud run jobs describe "$JOB_NAME" --region="$GCP_REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB_NAME" \
    --region="$GCP_REGION" \
    --image="$IMAGE" \
    --command=uv \
    --args=run,python,-m,dubai \
    --set-secrets=NEO4J_PASSWORD=neo4j-pass:latest,GITHUB_TOKEN=github-token:latest,LANGCHAIN_API_KEY=langchain-key:latest \
    --set-env-vars="NEO4J_URI=${NEO4J_URI},NEO4J_USER=neo4j,LANGCHAIN_TRACING_V2=true,LANGCHAIN_PROJECT=${LANGCHAIN_PROJECT:-dubai-graph-sync-agent}" \
    --max-retries=1 \
    --task-timeout=30m
else
  gcloud run jobs create "$JOB_NAME" \
    --region="$GCP_REGION" \
    --image="$IMAGE" \
    --command=uv \
    --args=run,python,-m,dubai \
    --set-secrets=NEO4J_PASSWORD=neo4j-pass:latest,GITHUB_TOKEN=github-token:latest,LANGCHAIN_API_KEY=langchain-key:latest \
    --set-env-vars="NEO4J_URI=${NEO4J_URI},NEO4J_USER=neo4j,LANGCHAIN_TRACING_V2=true,LANGCHAIN_PROJECT=${LANGCHAIN_PROJECT:-dubai-graph-sync-agent}" \
    --max-retries=1 \
    --task-timeout=30m
fi

echo "Run manually: gcloud run jobs execute ${JOB_NAME} --region=${GCP_REGION} --wait"
