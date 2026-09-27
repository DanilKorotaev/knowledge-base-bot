"""Active query jobs list + cancel (Overview system board / API)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.query_jobs.service import QueryJobService

router = APIRouter(prefix="/jobs", tags=["query-jobs"])


def _job_public(job: Any) -> dict[str, Any]:
    text = (job.query_text or "").strip().replace("\n", " ")
    if len(text) > 120:
        text = text[:117] + "…"
    return {
        "id": job.id,
        "session_id": job.session_id,
        "status": job.status,
        "query_text": text,
        "created_at": job.created_at,
        "started_at": job.started_at,
    }


@router.get("/active")
async def list_active_jobs(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    service = QueryJobService()
    jobs = await service.list_active(user_id=int(user["id"]), limit=limit)
    return {"jobs": [_job_public(j) for j in jobs], "total": len(jobs)}


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    service = QueryJobService()
    cancelled = await service.cancel(job_id, user_id=int(user["id"]))
    if cancelled is None:
        existing = await service.get_job(job_id)
        if existing is None or int(existing.user_id) != int(user["id"]):
            raise APIError("not_found", "Job not found", status_code=404)
        raise APIError(
            "conflict",
            f"Job is already {existing.status}",
            status_code=409,
        )
    return {"ok": True, "job": _job_public(cancelled)}
