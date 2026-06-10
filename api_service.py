"""FastAPI REST microservice.

P1 ships the skeleton: app, DB dependency, CORS, a stable response Envelope, the
health route, a model-list route, and the grade/budget search wired into the
envelope. Phase 2 only registers additional routes — the envelope, dependency,
and middleware stay frozen.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dashboard_queries import DubaiDashboardEngine
from dubai.ask_agent import run_ask
from dubai.cost_tracker import CostTracker
from dubai.langsmith_env import configure_langsmith_tracing
from dubai.langsmith_pricing_sync import maybe_sync_pricing_from_langsmith
from dubai.llm_router import MODEL_REGISTRY, list_models
from dubai.provider_env import configure_llm_provider_env
from dubai.settings import get_settings

settings = get_settings()
configure_llm_provider_env(settings)
configure_langsmith_tracing(settings)
maybe_sync_pricing_from_langsmith(list(MODEL_REGISTRY))

app = FastAPI(
    title="Dubai KHDA School Search Knowledge Graph API",
    description="Granular search across the Dubai private education graph.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_dashboard_db() -> Any:
    db = DubaiDashboardEngine(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    try:
        yield db
    finally:
        db.close()


class Envelope(BaseModel):
    data: list[dict[str, Any]] | dict[str, Any]
    telemetry: dict[str, Any] = {}


class AskRequest(BaseModel):
    question: str
    selected_model: str | None = None


@app.get("/", tags=["System Health"])
def read_root() -> dict[str, str]:
    return {"status": "operational", "engine": "FastAPI + Neo4j Graph Network"}


@app.get("/api/models", tags=["Models"])
def get_models() -> list[str]:
    return list_models()


@app.get("/api/schools/search", response_model=Envelope, tags=["Search"])
def search_schools_by_grade_and_budget(
    max_budget: float | None = Query(None, description="Maximum annual tuition in AED"),
    grade: str | None = Query(None, description="Target class level, e.g. 'Year 7', 'Grade 10'"),
    curriculum: str | None = Query(None, description="e.g. 'UK', 'US', 'IB', 'Indian'"),
    khda_rating: str | None = Query(None, description="KHDA DSIB rating, e.g. 'Outstanding'"),
    neighborhood: str | None = Query(None, description="Dubai neighborhood / location"),
    db: DubaiDashboardEngine = Depends(get_dashboard_db),
) -> Envelope:
    try:
        results = db.search_filtered(
            max_budget=max_budget,
            grade=grade,
            curriculum=curriculum,
            khda_rating=khda_rating,
            neighborhood=neighborhood,
        )
        return Envelope(data=results, telemetry={})
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Database failure: {error}")


@app.get("/api/schools/compare", response_model=Envelope, tags=["Search"])
def compare_schools(
    ids: list[str] = Query(..., description="School ids to compare"),
    db: DubaiDashboardEngine = Depends(get_dashboard_db),
) -> Envelope:
    try:
        return Envelope(data=db.compare_schools(ids), telemetry={})
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Database failure: {error}")


@app.get("/api/facets", response_model=Envelope, tags=["Search"])
def get_facets(db: DubaiDashboardEngine = Depends(get_dashboard_db)) -> Envelope:
    try:
        return Envelope(data=db.facets(), telemetry={})
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Database failure: {error}")


@app.get("/api/schools/{school_id}", response_model=Envelope, tags=["Search"])
def get_school(
    school_id: str, db: DubaiDashboardEngine = Depends(get_dashboard_db)
) -> Envelope:
    try:
        detail = db.get_school_detail(school_id)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Database failure: {error}")
    if detail is None:
        raise HTTPException(status_code=404, detail="School not found")
    return Envelope(data=detail, telemetry={})


@app.post("/api/ask", response_model=Envelope, tags=["Models"])
def ask(
    req: AskRequest,
    db: DubaiDashboardEngine = Depends(get_dashboard_db),
) -> Envelope:
    model_id = req.selected_model or settings.default_model
    if model_id not in list_models():
        raise HTTPException(status_code=422, detail=f"unknown model: {model_id}")
    tracker = CostTracker()
    try:
        result = run_ask(
            req.question,
            model_id=model_id,
            db=db,
            cost_tracker=tracker,
        )
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Model '{model_id}' unavailable: {error}",
        ) from error
    return Envelope(
        data={
            "answer": result.answer,
            "model": model_id,
            "schools": result.schools,
        },
        telemetry=tracker.as_dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_service:app", host="0.0.0.0", port=8000, reload=True)
