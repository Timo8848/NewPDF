from __future__ import annotations

import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from pydantic import BaseModel

from idp.config import Settings, get_settings
from idp.postprocess.analytics import close_connection, init_schema
from idp.services.pipeline import ExtractionPipeline
from idp.utils.logging import configure_logging

configure_logging()


class FieldPayload(BaseModel):
    value: str | float | None
    confidence: float
    valid: bool


class DocumentPayload(BaseModel):
    doc_type: str
    fields: dict[str, FieldPayload]
    validation_summary: dict


class ExtractionResponse(BaseModel):
    request_id: str
    documents: List[DocumentPayload]
    metrics: dict
    analytics: dict


class HealthResponse(BaseModel):
    status: str
    uptime_s: float


START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    app.state.pipeline = ExtractionPipeline()
    try:
        yield
    finally:
        close_connection()


app = FastAPI(title="IDP Service", version="0.2.0", lifespan=lifespan)


def get_service_settings() -> Settings:
    return get_settings()


@app.post("/extract", response_model=ExtractionResponse)
async def extract(file: UploadFile = File(...), settings: Settings = Depends(get_service_settings)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    contents = await file.read()
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = Path(tmp.name)
        result = app.state.pipeline.extract(tmp_path)
        return ExtractionResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", uptime_s=time.time() - START_TIME)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(generate_latest().decode())
