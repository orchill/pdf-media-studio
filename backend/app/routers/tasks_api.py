"""Task monitoring endpoints: list, status, log, cancel, remove."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _tm(request: Request):
    return request.app.state.tm


@router.get("/tasks")
async def list_tasks(request: Request, limit: int = 50, status: str | None = None, kind: str | None = None):
    return _tm(request).list_tasks(limit=limit, status=status, kind=kind)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    rec = _tm(request).get(task_id)
    if rec is None:
        # allow archived history entries to be fetched
        for entry in _tm(request).history:
            if entry.get("id") == task_id:
                return entry
        raise HTTPException(404, "Task not found")
    return rec.public()


@router.get("/tasks/{task_id}/log")
async def task_log(task_id: str, request: Request):
    rec = _tm(request).get(task_id)
    if rec is None:
        raise HTTPException(404, "Task not found (logs are kept for this session only)")
    return {"id": task_id, "log": rec.log}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request):
    ok = _tm(request).cancel(task_id)
    if not ok:
        rec = _tm(request).get(task_id)
        status = rec.status if rec else "unknown"
        raise HTTPException(409, f"Task cannot be cancelled (status: {status})")
    return {"cancelled": task_id}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, request: Request):
    ok = _tm(request).remove(task_id)
    if not ok:
        raise HTTPException(409, "Task is still running - cancel it first")
    return {"removed": task_id}
