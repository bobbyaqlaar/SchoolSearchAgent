# Publishing to GitHub

Checklist to add **Aqlaar Dubai School Finder** (`schoolSearchAgent`) to a GitHub repository safely.

Related: [README](../README.md) · [USER_MANUAL](USER_MANUAL.md) · [ARCHITECTURE](ARCHITECTURE.md)

---

## 1. Before you push

| Check | Action |
| --- | --- |
| **Secrets** | Ensure `.env` is **not** staged (listed in `.gitignore`). Use [`.env.example`](../.env.example) as the template. |
| **API keys in history** | If `.env` was ever committed, rotate all keys before publishing. |
| **Open-data cache** | `dubai_open_data_cache/` is gitignored — workbook is downloaded at sync time. |
| **Branch name** | CI triggers on **`main`** (see `.github/workflows/llm_regression_tests.yml`). Use `main`, not `master`. |

---

## 2. Create the repository on GitHub

1. GitHub → **New repository** (empty — no README, no `.gitignore`; this repo already has them).
2. Note the remote URL, e.g. `git@github.com:YOUR_ORG/SchoolSearchAgent.git`.

---

## 3. Initial commit and push

From the project root:

```bash
cd /path/to/schoolSearchAgent

cp .env.example .env    # then edit .env locally — do not commit

git add .
git status              # confirm .env is NOT listed
git commit -m "Initial commit: KHDA school search platform"

git branch -M main
git remote add origin git@github.com:YOUR_ORG/SchoolSearchAgent.git
git push -u origin main
```

If the repo already has a remote:

```bash
git remote set-url origin git@github.com:YOUR_ORG/SchoolSearchAgent.git
git push -u origin main
```

---

## 4. GitHub Actions secrets

Settings → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Required for | Notes |
| --- | --- | --- |
| `LANGCHAIN_API_KEY` | `llm-evals` job + `ci_gate` | LangSmith API key — parsing eval fails without it |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `deploy-production` | WIF provider — `./scripts/setup_github_actions_deploy.sh` |
| `GCP_SERVICE_ACCOUNT` | `deploy-production` | CI deploy service account email |
| `GCP_PROJECT_ID` | `deploy-production` | GCP project id |
| `GCP_REGION` | `deploy-production` | Default `me-central1` if omitted in workflow |
| `NEO4J_URI` | `deploy-production` | Aura Bolt URI (`neo4j+s://…`) |

**One-shot setup (recommended):**

```bash
unset GITHUB_TOKEN          # GitHub Models token shadows gh auth
./scripts/setup_github_actions_deploy.sh
```

Optional Cloud Build webhook (if supported in your region): `./scripts/setup_deploy_webhook.sh` sets `DEPLOY_WEBHOOK_URL` + `DEPLOY_WEBHOOK_TOKEN`.

The **`unit-tests`** and **`frontend`** jobs need no secrets.

Without `LANGCHAIN_API_KEY`, the parsing eval job fails and PRs cannot merge if you require that check.

---

## 5. CI pipeline (what runs on every PR)

Workflow: [`.github/workflows/llm_regression_tests.yml`](../.github/workflows/llm_regression_tests.yml)

| Job | Command | Gate |
| --- | --- | --- |
| `unit-tests` | `uv run pytest -v` | Required |
| `frontend` | `npm test` + `npm run build` | Required |
| `llm-evals` | `uv run python -m evals.eval_parsing` | Required (after unit-tests); **`ci_gate`** enforces score thresholds |
| `deploy-production` | `gcloud builds submit deploy/cloudbuild-ci-deploy.yaml` | **`main` only**, all jobs green |

See [ARCHITECTURE §5.3](ARCHITECTURE.md#53-layer-c--deploy-gate-ci_gate) for how `ci_gate` works.

---

## 6. Recommended GitHub settings

- **Branches** → protect `main`: require PR, require status checks (`unit-tests`, `frontend`, `llm-evals`).
- **Actions** → General → allow actions for this repository.
- **Dependabot** (optional): enable for `npm` and `uv`/pip ecosystems.

---

## 7. After publish

- Run CI on the first push; fix any failures before inviting collaborators.
- For manual GCP deploy from your laptop, see [README §9.4](../README.md#94-production--google-cloud-cloud-run--neo4j-aura) — `./scripts/gcp_deploy.sh`.

---

## 8. What stays local / out of git

| Path / file | Reason |
| --- | --- |
| `.env` | Live credentials |
| `.venv/` | Python virtualenv |
| `web/node_modules/`, `web/.next/` | Node build artifacts |
| `dubai_open_data_cache/` | Downloaded KHDA workbook |
| `logs/` | Sync cron logs |
| `.cursor/` | IDE metadata |
