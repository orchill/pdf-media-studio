"""System endpoints: health, dependency diagnostics, settings, output folder."""
from __future__ import annotations

import logging
import os
import subprocess
import sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import ConfigError, get_config
from ..services.depsinfo import system_info

log = logging.getLogger("pms.system")
router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/system/info")
async def info():
    return system_info(get_config())


@router.get("/settings")
async def get_settings():
    return get_config().public_dict()


class SettingsPatch(BaseModel):
    patch: dict


@router.put("/settings")
async def put_settings(body: SettingsPatch):
    cfg = get_config()
    try:
        restart = cfg.update(body.patch)
    except ConfigError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    return {"config": cfg.public_dict(), "restart_required": restart}


@router.post("/system/open-output-folder")
async def open_output_folder():
    """Open the output directory in the OS file manager (local use only)."""
    cfg = get_config()
    target = str(cfg.output_dir)
    try:
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            if not subprocess.run(["which", "xdg-open"], capture_output=True).returncode == 0:
                return JSONResponse(status_code=501, content={"detail": "No file manager found (xdg-open missing)"})
            subprocess.Popen(["xdg-open", target])
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Could not open folder: {exc}"})
    return {"opened": target}


@router.post("/system/clear-workspace")
async def clear_workspace(request: Request):
    """Remove cached uploads/thumbnails (refused while tasks are running)."""
    tm = getattr(request.app.state, "tm", None)
    if tm is not None:
        busy = [t.public() for t in tm.tasks.values() if t.status in ("queued", "running")]
        if busy:
            return JSONResponse(status_code=409, content={
                "detail": f"{len(busy)} task(s) still running - cancel them first"})
    cfg = get_config()
    removed = 0
    try:
        for sub in (cfg.uploads_dir, cfg.thumbs_dir, cfg.tmp_dir):
            if not sub.exists():
                continue
            for p in sub.iterdir():
                try:
                    if p.is_file():
                        p.unlink()
                        removed += 1
                    elif p.is_dir():
                        import shutil
                        shutil.rmtree(p, ignore_errors=True)
                        removed += 1
                except OSError:
                    pass
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    log.info("Workspace cleared: %s entries", removed)
    return {"removed": removed}
