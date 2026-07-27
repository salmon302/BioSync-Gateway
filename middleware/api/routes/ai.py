# SPDX-License-Identifier: MIT
"""
AI / LLM-RAG Clinical Text Gateway Routes - SRS FR-3.15.

Mounted at /api/ai:
  POST /pulse/narrative           Pulse -> progress-note synthesis (FR-3.15.4)
  POST /clinvar/pathology-report  ClinVar -> Molecular Pathology Report (FR-3.15.5)
  POST /ehr/ingest                EHR ingestion harness (FR-3.15.7)
  GET  /runs/{run_uid}            fetch a persisted output (FR-3.15.6)
  GET  /templates                 list RAG templates (FR-3.15.3)
  GET  /config                    resolved provider configuration (FR-3.15.1)

All LLM inference is dispatched via FastAPI BackgroundTasks, and the blocking
SDK call is offloaded with asyncio.to_thread, keeping the event loop free
(FR-3.15.2 / C6).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ai.llm_gateway import generate_text_async, get_provider_config, persist_run
from ai.rag import get_rag_repo
from api.auth import require_scope
from database import SessionLocal, get_db
from models import ClinicalTextOutput, Observation

logger = logging.getLogger(__name__)

router = APIRouter()

# In-process job registry for polling (single-process simulation gateway).
_jobs: Dict[str, Dict[str, Any]] = {}


# --------------------------------------------------------------------------
# Request / response models
# --------------------------------------------------------------------------
class PulseNarrativeRequest(BaseModel):
    patient_id: Optional[str] = None
    simulation_id: Optional[int] = None
    window_seconds: int = Field(default=60, ge=1, le=3600)
    telemetry: Optional[List[Dict[str, Any]]] = None  # optional explicit samples
    template_id: Optional[str] = None
    max_tokens: int = Field(default=384, ge=1, le=2048)


class ClinVarPathologyRequest(BaseModel):
    variants: List[Dict[str, Any]] = Field(default_factory=list)
    gene: Optional[str] = None  # optional live ClinVar lookup (FR-3.10.2)
    template_id: Optional[str] = None
    patient_id: Optional[str] = None
    max_tokens: int = Field(default=1024, ge=1, le=4096)


class EhrIngestRequest(BaseModel):
    text: str
    expected_signals: List[str] = Field(default_factory=list)
    ehr_endpoint: Optional[str] = None  # override EHR_INGEST_URL


class RunResponse(BaseModel):
    run_uid: str
    status: str
    text_type: Optional[str] = None
    content: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


# --------------------------------------------------------------------------
# Prompt builders
# --------------------------------------------------------------------------
def _aggregate_pulse_telemetry(db: Optional[Session], req: PulseNarrativeRequest) -> Dict[str, float]:
    """Aggregate Pulse numeric telemetry over the window (FR-3.15.4)."""
    channels: Dict[str, List[float]] = {}
    samples = req.telemetry or []
    if not samples and req.patient_id and db is not None:
        # Best-effort pull from observations table within the window.
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=req.window_seconds)
            rows = (
                db.query(Observation)
                .filter(Observation.patient_id == req.patient_id)
                .filter(Observation.timestamp >= cutoff)
                .limit(500)
                .all()
            )
            for r in rows:
                vq = r.value_quantity or {}
                val = vq.get("value")
                code = r.observation_code or "unknown"
                if isinstance(val, (int, float)):
                    channels.setdefault(code, []).append(float(val))
        except Exception as exc:  # pragma: no cover
            logger.warning("Telemetry aggregation failed: %s", exc)
    if not channels and samples:
        for s in samples:
            for k, val in s.items():
                if isinstance(val, (int, float)):
                    channels.setdefault(k, []).append(float(val))
    return {ch: round(sum(v) / len(v), 3) for ch, v in channels.items() if v}


def _build_pulse_prompt(summary: Dict[str, float], context: str) -> str:
    lines = (
        "\n".join(f"- {k}: {v}" for k, v in summary.items())
        or "- (no telemetry available)"
    )
    return (
        "You are synthesizing a clinical progress note from Pulse simulator "
        "telemetry for EHR text-ingestion testing (FR-3.15.4).\n"
        "Use standard medical abbreviations and include brief subjective reasoning.\n\n"
        "== RAG CONTEXT (EHR progress-note rubric) ==\n"
        f"{context}\n\n"
        "== Aggregated Pulse telemetry (mean over window) ==\n"
        f"{lines}\n\n"
        "Write a concise SOAP-style progress note suitable for EHR ingestion."
    )


def _build_pathology_prompt(variants: List[Dict[str, Any]], context: str) -> str:
    variants_json = json.dumps(variants, indent=2, default=str)
    return (
        "You are generating a simulated 'Molecular Pathology Summary Report' "
        "for EHR/LIMS testing (FR-3.15.5). Merge the structured ClinVar variant "
        "data into the reporting template below. Do NOT invent clinical facts "
        "beyond the provided data.\n\n"
        "== RAG CONTEXT (CAP/CLIA molecular pathology template) ==\n"
        f"{context}\n\n"
        "== ClinVar variant data ==\n"
        f"{variants_json}\n\n"
        "Produce the completed Molecular Pathology Summary Report."
    )


# --------------------------------------------------------------------------
# Background workers
# --------------------------------------------------------------------------
async def _run_pulse_narrative(run_uid: str, req: PulseNarrativeRequest, db: Session):
    try:
        repo = get_rag_repo()
        template = repo.get_by_id(req.template_id) if req.template_id else None
        if template is None:
            hits = repo.retrieve("progress note EHR rubric", template_type="ehr_rubric", top_k=1)
            template = hits[0] if hits else None
        context = repo.as_context([template]) if template else ""
        summary = _aggregate_pulse_telemetry(db, req)
        prompt = _build_pulse_prompt(summary, context)
        text = await generate_text_async(prompt, max_tokens=req.max_tokens)
        output = persist_run(
            db,
            prompt,
            text,
            template_id=template.template_id if template else None,
            source_data={"telemetry_summary": summary},
            text_type="progress_note",
            max_tokens=req.max_tokens,
        )
        db.commit()
        _jobs[run_uid] = {
            "status": "completed",
            "output_uid": output.output_uid,
            "text_type": output.text_type,
            "provenance": output.provenance,
            "created_at": output.created_at.isoformat() if output.created_at else None,
        }
    except Exception as exc:
        logger.error("Pulse narrative run %s failed: %s", run_uid, exc)
        _jobs[run_uid] = {"status": "failed", "error": str(exc)}
        try:
            db.rollback()
        except Exception:
            pass


async def _run_pathology_report(run_uid: str, req: ClinVarPathologyRequest, db: Session):
    try:
        variants: List[Dict[str, Any]] = list(req.variants)
        if not variants and req.gene:
            # Optional live ClinVar lookup (FR-3.10.2).
            from external.clinvar import ClinVarClient

            client = ClinVarClient()
            variants = await client.search_variants(req.gene, retmax=5)
        repo = get_rag_repo()
        template = repo.get_by_id(req.template_id) if req.template_id else None
        if template is None:
            hits = repo.retrieve("molecular pathology CAP CLIA", template_type="cap_clia", top_k=1)
            template = hits[0] if hits else None
        context = repo.as_context([template]) if template else ""
        prompt = _build_pathology_prompt(variants, context)
        text = await generate_text_async(prompt, max_tokens=req.max_tokens)
        output = persist_run(
            db,
            prompt,
            text,
            template_id=template.template_id if template else None,
            source_data={"variants": variants, "gene": req.gene},
            text_type="pathology_report",
            max_tokens=req.max_tokens,
        )
        db.commit()
        _jobs[run_uid] = {
            "status": "completed",
            "output_uid": output.output_uid,
            "text_type": output.text_type,
            "provenance": output.provenance,
            "created_at": output.created_at.isoformat() if output.created_at else None,
        }
    except Exception as exc:
        logger.error("Pathology report run %s failed: %s", run_uid, exc)
        _jobs[run_uid] = {"status": "failed", "error": str(exc)}
        try:
            db.rollback()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@router.get("/templates")
async def list_templates(_: Any = Depends(require_scope("ai_read"))):
    """List registered RAG templates (FR-3.15.3)."""
    repo = get_rag_repo()
    return {"count": len(repo.templates), "templates": repo.registry_rows()}


@router.get("/config")
async def provider_config(_: Any = Depends(require_scope("ai_read"))):
    """Show the resolved LLM provider configuration (FR-3.15.1)."""
    return get_provider_config()


@router.post("/pulse/narrative", response_model=RunResponse, status_code=202)
async def pulse_narrative(
    req: PulseNarrativeRequest,
    background: BackgroundTasks,
    _: Any = Depends(require_scope("ai_write")),
):
    """Aggregate Pulse telemetry and synthesize a progress note (FR-3.15.4)."""
    from uuid import uuid4

    run_uid = str(uuid4())
    _jobs[run_uid] = {"status": "queued"}
    bg_db = SessionLocal()  # fresh session for the background task

    async def _worker():
        try:
            await _run_pulse_narrative(run_uid, req, bg_db)
        finally:
            bg_db.close()

    background.add_task(_worker)
    return RunResponse(run_uid=run_uid, status="queued")


@router.post("/clinvar/pathology-report", response_model=RunResponse, status_code=202)
async def clinvar_pathology_report(
    req: ClinVarPathologyRequest,
    background: BackgroundTasks,
    _: Any = Depends(require_scope("ai_write")),
):
    """Merge ClinVar variants into a CAP/CLIA pathology report (FR-3.15.5)."""
    from uuid import uuid4

    run_uid = str(uuid4())
    _jobs[run_uid] = {"status": "queued"}
    bg_db = SessionLocal()

    async def _worker():
        try:
            await _run_pathology_report(run_uid, req, bg_db)
        finally:
            bg_db.close()

    background.add_task(_worker)
    return RunResponse(run_uid=run_uid, status="queued")


@router.post("/ehr/ingest")
async def ehr_ingest(
    req: EhrIngestRequest,
    _: Any = Depends(require_scope("ai_write")),
):
    """EHR ingestion harness (FR-3.15.7).

    Pushes generated text to a downstream EHR/FHIR mapping endpoint and
    validates that critical clinical signals are preserved through the
    text -> structured mapping. When no endpoint is configured, a local
    round-trip simulation validates signal preservation directly.
    """
    import os

    import httpx

    endpoint = req.ehr_endpoint or os.getenv("EHR_INGEST_URL")
    preserved: List[str] = []
    missing: List[str] = []
    mapping: Any = None

    if endpoint:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    endpoint,
                    json={"text": req.text, "expected_signals": req.expected_signals},
                )
                resp.raise_for_status()
                mapping = resp.json()
                mapped_text = json.dumps(mapping, default=str).lower()
                for s in req.expected_signals:
                    (preserved if s.lower() in mapped_text else missing).append(s)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"EHR ingest endpoint error: {exc}")
    else:
        # Local round-trip simulation: signals preserved if present in text.
        low = req.text.lower()
        for s in req.expected_signals:
            (preserved if s.lower() in low else missing).append(s)

    return {
        "passed": len(missing) == 0,
        "endpoint": endpoint or "local-simulation",
        "preserved_signals": preserved,
        "missing_signals": missing,
        "mapping": mapping,
    }


@router.get("/runs/{run_uid}", response_model=RunResponse)
async def get_run(
    run_uid: str,
    db: Session = Depends(get_db),
    _: Any = Depends(require_scope("ai_read")),
):
    """Fetch a persisted LLM text output by run_uid (FR-3.15.6)."""
    job = _jobs.get(run_uid)
    if job and job.get("status") == "completed":
        output = (
            db.query(ClinicalTextOutput)
            .filter(ClinicalTextOutput.output_uid == job["output_uid"])
            .first()
        )
        if output:
            return RunResponse(
                run_uid=run_uid,
                status="completed",
                text_type=output.text_type,
                content=output.content,
                provenance=output.provenance,
                created_at=output.created_at.isoformat() if output.created_at else None,
            )
    if job and job.get("status") == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "run failed"))
    if job and job.get("status") == "queued":
        return RunResponse(run_uid=run_uid, status="queued")
    raise HTTPException(status_code=404, detail="run not found")
