"""FastAPI application assembly: routers, static UI, lifecycle management."""
from __future__ import annotations

import logging
import logging.handlers
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import APP_NAME, __version__
from .config import get_config
from .security import ValidationError
from .tasks import TaskManager

log = logging.getLogger("pms.main")


def _setup_logging(cfg) -> None:
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g. tests)
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    filehandler = logging.handlers.RotatingFileHandler(
        cfg.logs_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    filehandler.setFormatter(fmt)
    root.addHandler(console)
    root.addHandler(filehandler)


def boot_cleanup(cfg) -> dict:
    """Remove transient data from previous runs (uploads, thumbs, temp)."""
    removed = {"uploads": 0, "thumbs": 0, "tmp": 0}
    for key, d in (("uploads", cfg.uploads_dir), ("thumbs", cfg.thumbs_dir),
                   ("tmp", cfg.tmp_dir)):
        if not d.exists():
            continue
        for p in d.iterdir():
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink()
                removed[key] += 1
            except OSError:
                pass
    return removed


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    _setup_logging(cfg)
    cfg.ensure_dirs()
    removed = boot_cleanup(cfg)
    log.info("%s v%s starting - http://%s:%d (output: %s)",
             APP_NAME, __version__, cfg.get("host"), cfg.get("port"), cfg.output_dir)
    log.info("Cleaned from previous run: %s", removed)
    app.state.tm = TaskManager(cfg.history_path, int(cfg.get("history_limit")),
                               int(cfg.get("max_concurrent_tasks")))
    yield
    await app.state.tm.shutdown()
    log.info("Shutdown complete (temporary files cleaned)")


app = FastAPI(title=APP_NAME, version=__version__, lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import files, media, pdf, system, tasks_api  # noqa: E402

app.include_router(system.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(pdf.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(tasks_api.router, prefix="/api")


@app.exception_handler(ValidationError)
async def validation_handler(_req: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_handler(_req: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})


# Serve the built React UI (frontend/dist). API routes are registered above
# and therefore take precedence over the static mount.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists() and (_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
else:
    @app.get("/")
    async def _no_ui():
        return JSONResponse(content={
            "app": APP_NAME,
            "status": "API running",
            "hint": "UI not built yet - run: cd frontend && npm install && npm run build",
            "api_docs": "/api/docs",
        })
