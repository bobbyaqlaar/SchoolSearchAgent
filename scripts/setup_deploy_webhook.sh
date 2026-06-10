#!/usr/bin/env bash
# Deploy webhook for CI: native Cloud Build webhook, or Cloud Run relay fallback.
# Prefer ./scripts/setup_github_actions_deploy.sh for WIF-only GitHub Actions deploy.
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
RELAY_SERVICE="${DEPLOY_WEBHOOK_RELAY_SERVICE:-dubai-deploy-webhook}"
RELAY_SA_NAME="${DEPLOY_WEBHOOK_RELAY_SA:-deploy-webhook-relay}"
RELAY_SA_EMAIL="${RELAY_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
DEPLOY_SA_NAME="${GITHUB_ACTIONS_SA_NAME:-github-actions-deploy}"
DEPLOY_SA_EMAIL="${DEPLOY_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
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

WEBHOOK_URL=""
echo "Creating Cloud Build webhook trigger ${TRIGGER_NAME}…"
if gcloud builds triggers create webhook \
  --name="$TRIGGER_NAME" \
  --region="$GCP_REGION" \
  --inline-config=deploy/cloudbuild-ci-deploy.yaml \
  --secret="$SECRET_RESOURCE" \
  --substitutions="$SUBSTITUTIONS" \
  --quiet 2>/dev/null; then
  WEBHOOK_URL="$(gcloud builds triggers describe "$TRIGGER_NAME" \
    --region="$GCP_REGION" \
    --format='value(webhookConfig.url)')"
fi

if [[ -z "$WEBHOOK_URL" ]]; then
  echo "Native Cloud Build webhook unavailable — deploying Cloud Run relay (${RELAY_SERVICE})…"

  if ! gcloud iam service-accounts describe "$RELAY_SA_EMAIL" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$RELAY_SA_NAME" \
      --display-name="Deploy webhook relay — SchoolSearchAgent"
  fi

  grant_role() {
    gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
      --member="serviceAccount:${RELAY_SA_EMAIL}" \
      --role="$1" \
      --quiet >/dev/null 2>&1 || true
  }
  grant_role roles/cloudbuild.builds.editor
  grant_role roles/iam.serviceAccountUser
  grant_role roles/storage.admin
  grant_role roles/serviceusage.serviceUsageConsumer

  gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA_EMAIL" \
    --member="serviceAccount:${RELAY_SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --quiet >/dev/null 2>&1 || true

  IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_REPO}/deploy-webhook-relay:latest"
  gcloud builds submit deploy/webhook-relay \
    --tag="$IMAGE" \
    --quiet

  gcloud run deploy "$RELAY_SERVICE" \
    --project="$GCP_PROJECT_ID" \
    --image="$IMAGE" \
    --region="$GCP_REGION" \
    --platform=managed \
    --service-account="$RELAY_SA_EMAIL" \
    --no-allow-unauthenticated \
    --port=8080 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=3 \
    --set-env-vars="WEBHOOK_TOKEN=${TOKEN},GCP_PROJECT_ID=${GCP_PROJECT_ID},GCP_REGION=${GCP_REGION},GCP_REPO=${GCP_REPO},NEO4J_URI=${NEO4J_URI},DEPLOY_SA=${DEPLOY_SA_EMAIL},GITHUB_REPO=${GITHUB_REPO}" \
    --quiet

  gcloud run services add-iam-policy-binding "$RELAY_SERVICE" \
    --project="$GCP_PROJECT_ID" \
    --region="$GCP_REGION" \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet >/dev/null 2>&1 || true

  RELAY_BASE="$(gcloud run services describe "$RELAY_SERVICE" \
    --project="$GCP_PROJECT_ID" \
    --region="$GCP_REGION" \
    --format='value(status.url)')"
  WEBHOOK_URL="${RELAY_BASE}/deploy"
fi

[[ -n "$WEBHOOK_URL" ]] || die "Could not configure deploy webhook URL"

env -u GITHUB_TOKEN gh secret set DEPLOY_WEBHOOK_URL --repo "$GITHUB_REPO" --body "$WEBHOOK_URL"
env -u GITHUB_TOKEN gh secret set DEPLOY_WEBHOOK_TOKEN --repo "$GITHUB_REPO" --body "$TOKEN"

echo "Webhook deploy configured: ${WEBHOOK_URL}"
