#!/usr/bin/env bash
# Wire GitHub Actions deploy-production → Cloud Build via Workload Identity Federation.
#
# Usage:
#   unset GITHUB_TOKEN
#   ./scripts/setup_github_actions_deploy.sh

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
NEO4J_URI="${NEO4J_URI:-${NEO4J_AURA_URI:-}}"
SA_NAME="${GITHUB_ACTIONS_SA_NAME:-github-actions-deploy}"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
GITHUB_REPO="${GITHUB_REPO:-bobbyaqlaar/SchoolSearchAgent}"
POOL_ID="${WIF_POOL_ID:-github-pool}"
PROVIDER_ID="${WIF_PROVIDER_ID:-github-provider}"

die() { echo "ERROR: $*" >&2; exit 1; }

command -v gcloud >/dev/null 2>&1 || die "gcloud not found"
command -v gh >/dev/null 2>&1 || die "gh not found — brew install gh"

[[ -n "$GCP_PROJECT_ID" && "$GCP_PROJECT_ID" != "(unset)" ]] || die "Set GCP_PROJECT_ID"
[[ -n "$NEO4J_URI" && "$NEO4J_URI" != *localhost* ]] || die "Set NEO4J_URI to Aura (neo4j+s://…)"

gcloud config set project "$GCP_PROJECT_ID" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"

if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  echo "Creating service account ${SA_EMAIL}…"
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="GitHub Actions — SchoolSearchAgent deploy"
fi

grant_role() {
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$1" \
    --quiet >/dev/null 2>&1 || true
}

echo "Granting deploy roles to ${SA_EMAIL}…"
grant_role roles/cloudbuild.builds.editor
grant_role roles/run.admin
grant_role roles/iam.serviceAccountUser
grant_role roles/artifactregistry.writer
grant_role roles/secretmanager.secretAccessor
grant_role roles/storage.admin
grant_role roles/serviceusage.serviceUsageConsumer

echo "Enabling required GCP APIs…"
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --quiet

if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
  --location=global >/dev/null 2>&1; then
  echo "Creating workload identity pool ${POOL_ID}…"
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --location=global \
    --display-name="GitHub Actions pool"
fi

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  echo "Creating workload identity provider ${PROVIDER_ID}…"
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --location=global \
    --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub Actions provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == 'bobbyaqlaar'"
fi

WIF_MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$WIF_MEMBER" \
  --quiet >/dev/null

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo "Setting GitHub secrets on ${GITHUB_REPO}…"
env -u GITHUB_TOKEN gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "$GITHUB_REPO" --body "$WIF_PROVIDER"
env -u GITHUB_TOKEN gh secret set GCP_SERVICE_ACCOUNT --repo "$GITHUB_REPO" --body "$SA_EMAIL"
env -u GITHUB_TOKEN gh secret set GCP_PROJECT_ID --repo "$GITHUB_REPO" --body "$GCP_PROJECT_ID"
env -u GITHUB_TOKEN gh secret set GCP_REGION --repo "$GITHUB_REPO" --body "$GCP_REGION"
env -u GITHUB_TOKEN gh secret set NEO4J_URI --repo "$GITHUB_REPO" --body "$NEO4J_URI"

echo ""
echo "GitHub Actions deploy (WIF) configured on ${GITHUB_REPO}:"
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "  GCP_SERVICE_ACCOUNT, GCP_PROJECT_ID, GCP_REGION, NEO4J_URI"
