"""Authenticated deploy webhook → gcloud builds submit (CI relay for me-central1)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="SchoolSearchAgent deploy webhook")


class DeployPayload(BaseModel):
    ref: str = Field(default="refs/heads/main")
    repo: str = Field(default="bobbyaqlaar/SchoolSearchAgent")
    sha: str | None = None


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _branch_from_ref(ref: str) -> str:
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        return ref[len(prefix) :]
    return ref


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
@app.post("/deploy")
def deploy(
    payload: DeployPayload,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    token = _required("WEBHOOK_TOKEN")
    project_id = _required("GCP_PROJECT_ID")
    region = os.environ.get("GCP_REGION", "me-central1")
    repo_name = os.environ.get("GCP_REPO", "dubai")
    neo4j_uri = _required("NEO4J_URI")
    deploy_sa = os.environ.get("DEPLOY_SA", "").strip()

    expected = f"Bearer {token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    branch = _branch_from_ref(payload.ref)
    archive_url = f"https://github.com/{payload.repo}/archive/refs/heads/{branch}.tar.gz"

    workdir = tempfile.mkdtemp(prefix="deploy-src-")
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(archive_url)
            response.raise_for_status()
            tar_path = os.path.join(workdir, "src.tar.gz")
            with open(tar_path, "wb") as handle:
                handle.write(response.content)
            with tarfile.open(tar_path, "r:gz") as archive:
                members = archive.getmembers()
                if not members:
                    raise HTTPException(status_code=400, detail="Empty archive")
                top = members[0].name.split("/", 1)[0]
                archive.extractall(workdir)
            source_root = os.path.join(workdir, top)
            config_path = os.path.join(source_root, "deploy", "cloudbuild-ci-deploy.yaml")
            if not os.path.isfile(config_path):
                listing = ", ".join(sorted(os.listdir(source_root))[:20])
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing cloudbuild config under {source_root}: {listing}",
                )

        submit_cmd: list[str] = [
            "gcloud",
            "builds",
            "submit",
            f"--project={project_id}",
            f"--region={region}",
            "--config=deploy/cloudbuild-ci-deploy.yaml",
            f"--substitutions=_REGION={region},_REPO={repo_name},_NEO4J_URI={neo4j_uri}",
            "--async",
            "--format=value(id)",
            ".",
        ]
        if deploy_sa:
            submit_cmd.insert(-1, f"--service-account=projects/{project_id}/serviceAccounts/{deploy_sa}")

        proc = subprocess.run(
            submit_cmd,
            check=False,
            capture_output=True,
            text=True,
            cwd=source_root,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "gcloud builds submit failed").strip()
            raise HTTPException(status_code=500, detail=detail[:2000])

        build_id = proc.stdout.strip()
        return {"buildId": build_id, "branch": branch, "repo": payload.repo}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
