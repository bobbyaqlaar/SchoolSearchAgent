#!/usr/bin/env bash
# Optional: Cloud Build webhook trigger (may fail on some regions/projects).
# Prefer ./scripts/setup_github_actions_deploy.sh for GitHub Actions deploy.
#
# Usage:
#   unset GITHUB_TOKEN
#   ./scripts/setup_deploy_webhook.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

GCP_PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}}"
GCP_REGION="${GCP_REGION:-me-central1}"
GCP_REPO="${GCP_REPO:-dubai}"
NEO4J_URI="${NEO4J_URI:-${NEO4J_AURA_URI:-}}"
TRIGGER_NAME="${DEPLOY_WEBHOOK_TRIGGER_NAME:-school-search-agent-deploy}"
WEBHOOK_SECRET_NAME="${DEPLOY_WEBHOOK_SECRET_NAME:-github-deploy-webhook-token}"
GITHUB_REPO="${GITHUB_REPO:-bobbyaqlaar/SchoolSearchAgent}"

die() { echo "ERROR: $*" >&2; exit 1; }

command -v gcloud >/dev/null 2>&1 || die "gcloud not found"
command -v gh >/dev/null 2>&1 || die "gh not found"
command -v openssl >/dev/null 2>&1 || die "openssl not found"

[[ -n "$GCP_PROJECT_ID" && "$GCP_PROJECT_ID" != "(unset)" ]] || die "Set GCP_PROJECT_ID"
[[ -n "$NEO4J_URI" && "$NEO4J_URI" != *localhost* ]] || die "Set NEO4J_URI to Aura (neo4j+s://…)"

gcloud config set project "$GCP_PROJECT_ID" >/dev/null

TOKEN="$(openssl rand -hex 32)"
if gcloud secrets describe "$WEBHOOK_SECRET_NAME" >/dev/null 2>&1; then
  printf '%s' "$TOKEN" | gcloud secrets versions add "$WEBHOOK_SECRET_NAME" --data-file=-
else
  printf '%s' "$TOKEN" | gcloud secrets create "$WEBHOOK_SECRET_NAME" --data-file=-
fi
SECRET_VERSION="$(gcloud secrets versions list "$WEBHOOK_SECRET_NAME" --limit=1 --format='value(name)')"
SECRET_RESOURCE="projects/${GCP_PROJECT_ID}/secrets/${WEBHOOK_SECRET_NAME}/${SECRET_VERSION}"

PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"
GCB_AGENT="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
gcloud secrets add-iam-policy-binding "$WEBHOOK_SECRET_NAME" \
  --member="serviceAccount:${GCB_AGENT}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet >/dev/null 2>&1 || true

SUBSTITUTIONS="_REGION=${GCP_REGION},_REPO=${GCP_REPO},_NEO4J_URI=${NEO4J_URI}"

if gcloud builds triggers describe "$TRIGGER_NAME" --region="$GCP_REGION" >/dev/null 2>&1; then
  gcloud builds triggers delete "$TRIGGER_NAME" --region="$GCP_REGION" --quiet
fi

echo "Creating Cloud Build webhook trigger ${TRIGGER_NAME}…"
if ! gcloud builds triggers create webhook \
  --name="$TRIGGER_NAME" \
  --region="$GCP_REGION" \
  --inline-config=deploy/cloudbuild-ci-deploy.yaml \
  --secret="$SECRET_RESOURCE" \
  --substitutions="$SUBSTITUTIONS" \
  --quiet; then
  die "Cloud Build webhook trigger failed (common in me-central1). Use ./scripts/setup_github_actions_deploy.sh instead."
fi

WEBHOOK_URL="$(gcloud builds triggers describe "$TRIGGER_NAME" \
  --region="$GCP_REGION" \
  --format='value(webhookConfig.url)')"
[[ -n "$WEBHOOK_URL" ]] || die "Could not read webhookConfig.url"

env -u GITHUB_TOKEN gh secret set DEPLOY_WEBHOOK_URL --repo "$GITHUB_REPO" --body "$WEBHOOK_URL"
env -u GITHUB_TOKEN gh secret set DEPLOY_WEBHOOK_TOKEN --repo "$GITHUB_REPO" --body "$TOKEN"

echo "Webhook deploy configured: ${WEBHOOK_URL}"
