"""PDF tool endpoints. Each operation is submitted as a background task and
returns a task id that the UI polls (GET /api/tasks/{id})."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..config import get_config
from ..security import ValidationError, validate_order, validate_rotation
from ..services import pdf_service
from ..tasks import TaskManager
from ..utils import sanitize_stem
from .files import get_upload, upload_path

router = APIRouter()


def _tm(request: Request) -> TaskManager:
    return request.app.state.tm


def _pdf_upload(file_id: str):
    meta = get_upload(file_id)
    if meta.data["kind"] != "pdf":
        raise HTTPException(415, f"'{meta.data['name']}' is not a PDF document")
    return upload_path(meta), meta


def _submit(request: Request, kind: str, title: str, fn, args: tuple,
            meta: dict | None = None) -> dict:
    cfg = get_config()
    cfg.ensure_dirs()
    temp_dir = Path(tempfile.mkdtemp(prefix=f"{kind}-", dir=cfg.tmp_dir))
    tm = _tm(request)

    async def runner(rec):
        return await asyncio.to_thread(fn, rec, *args)

    task_id = tm.submit(kind, title, runner, meta=meta, temp_dir=temp_dir)
    return {"task_id": task_id}


def _clean_output_name(name: str | None) -> str | None:
    if not name:
        return None
    stem = sanitize_stem(name, 80)
    return stem or None


# ----------------------------------------------------------------- models
class MergeIn(BaseModel):
    file_ids: list[str] = Field(min_length=2, max_length=24)
    output_name: str | None = None


class ImageItem(BaseModel):
    id: str
    rotation: int = 0


class ImagesToPdfIn(BaseModel):
    items: list[ImageItem] = Field(min_length=1, max_length=200)
    page_size: str = "a4"                 # a4 a3 a5 letter legal image
    orientation: str = "auto"             # auto portrait landscape
    margin_mm: float = 10.0
    image_dpi: int = 96                   # used when page_size == image
    jpeg_quality: int | None = None       # None = preserve original bytes
    output_name: str | None = None


class EditPagesIn(BaseModel):
    file_id: str
    order: list[int] = Field(min_length=1, max_length=2000)
    rotate: dict[str, int] = Field(default_factory=dict)
    output_name: str | None = None


class SplitIn(BaseModel):
    file_id: str
    mode: str = Field(pattern="^(extract|every_n|ranges)$")
    ranges: str | None = None
    every_n: int | None = Field(default=None, ge=1, le=2000)
    pages: str | None = None
    output_name: str | None = None


class CompressIn(BaseModel):
    file_id: str
    quality: int = Field(default=65, ge=10, le=95)
    dpi_cap: int = Field(default=120, ge=36, le=300)


class SimpleOpIn(BaseModel):
    file_id: str


class ToImagesIn(BaseModel):
    file_id: str
    format: str = Field(default="png", pattern="^(png|jpg|jpeg)$")
    dpi: int = Field(default=150, ge=36, le=600)
    pages: str | None = None


# ------------------------------------------------------------- operations
@router.post("/pdf/merge")
async def merge_pdf(request: Request, body: MergeIn):
    paths = []
    for fid in body.file_ids:
        p, _meta = _pdf_upload(fid)
        paths.append(p)
    return _submit(request, "pdf_merge", f"Merge {len(paths)} PDFs",
                   pdf_service.merge_task, (paths, get_config().output_dir),
                   meta={"inputs": [p.name for p in paths]})


@router.post("/pdf/images-to-pdf")
async def images_to_pdf(request: Request, body: ImagesToPdfIn):
    if body.page_size not in ("a4", "a3", "a5", "letter", "legal", "image"):
        raise HTTPException(400, "Invalid page size")
    if body.orientation not in ("auto", "portrait", "landscape"):
        raise HTTPException(400, "Invalid orientation")
    items = []
    for it in body.items:
        meta = get_upload(it.id)
        if meta.data["kind"] != "image":
            raise HTTPException(415, f"'{meta.data['name']}' is not an image")
        items.append({"id": it.id, "path": str(upload_path(meta)),
                      "rotation": validate_rotation(it.rotation),
                      "format": meta.data.get("format"), "name": meta.data["name"]})
    opts = {"page_size": body.page_size, "orientation": body.orientation,
            "margin_mm": body.margin_mm, "image_dpi": body.image_dpi,
            "jpeg_quality": body.jpeg_quality}
    return _submit(request, "pdf_images", f"Convert {len(items)} images to PDF",
                   pdf_service.images_to_pdf_task,
                   (items, opts, get_config().output_dir))


@router.post("/pdf/pages")
async def edit_pages(request: Request, body: EditPagesIn):
    src, meta = _pdf_upload(body.file_id)
    n = int(meta.data.get("pages") or 0)
    order = validate_order(body.order, n)
    rotate_map = {}
    for k, v in (body.rotate or {}).items():
        try:
            page_no = int(k)
        except ValueError:
            raise HTTPException(400, f"Invalid page key in rotate: {k!r}")
        if page_no in order:
            rotate_map[page_no] = validate_rotation(v)
    return _submit(request, "pdf_pages", f"Edit pages of {meta.data['name']}",
                   pdf_service.edit_pages_task,
                   (src, order, rotate_map, get_config().output_dir,
                    _clean_output_name(body.output_name), meta.data["name"]),
                   meta={"source": meta.data["name"], "kept": len(order), "total": n})


@router.post("/pdf/split")
async def split_pdf(request: Request, body: SplitIn):
    src, meta = _pdf_upload(body.file_id)
    if body.mode == "every_n" and not body.every_n:
        raise HTTPException(400, "'every_n' must be provided for this mode")
    n = int(meta.data.get("pages") or 0)
    if body.mode == "extract":
        from ..security import parse_pages
        parse_pages(body.pages, n)                       # validate now -> HTTP 400
    elif body.mode == "ranges":
        from ..security import parse_page_groups
        parse_page_groups(body.ranges or "", n)          # validate now -> HTTP 400
    return _submit(request, "pdf_split", f"Split {meta.data['name']} ({body.mode})",
                   pdf_service.split_task,
                   (src, body.mode, body.ranges, body.every_n, body.pages,
                    get_config().output_dir, meta.data["name"]),
                   meta={"source": meta.data["name"]})


@router.post("/pdf/compress")
async def compress_pdf(request: Request, body: CompressIn):
    src, meta = _pdf_upload(body.file_id)
    return _submit(request, "pdf_compress", f"Compress {meta.data['name']}",
                   pdf_service.compress_task,
                   (src, body.quality, body.dpi_cap, get_config().output_dir,
                    meta.data["name"]),
                   meta={"source": meta.data["name"]})


@router.post("/pdf/extract-images")
async def extract_images(request: Request, body: SimpleOpIn):
    src, meta = _pdf_upload(body.file_id)
    return _submit(request, "pdf_extract_images", f"Extract images from {meta.data['name']}",
                   pdf_service.extract_images_task,
                   (src, get_config().output_dir, meta.data["name"]),
                   meta={"source": meta.data["name"]})


@router.post("/pdf/to-images")
async def to_images(request: Request, body: ToImagesIn):
    src, meta = _pdf_upload(body.file_id)
    fmt = "jpg" if body.format == "jpeg" else body.format
    return _submit(request, "pdf_to_images", f"Export {meta.data['name']} to images",
                   pdf_service.to_images_task,
                   (src, fmt, body.dpi, body.pages, get_config().output_dir,
                    meta.data["name"]),
                   meta={"source": meta.data["name"], "format": fmt, "dpi": body.dpi})


# ---------------------------------------------------------- page previews
@router.get("/pdf/{file_id}/page/{page_no}/thumbnail")
async def page_thumbnail(file_id: str, page_no: int, width: int = 240):
    from .files import _thumbnail
    meta = get_upload(file_id)
    if meta.data["kind"] != "pdf":
        raise HTTPException(415, "Not a PDF")
    total = int(meta.data.get("pages") or 1)
    if page_no < 1 or page_no > total:
        raise HTTPException(400, f"Page {page_no} out of range (1-{total})")
    return await _thumbnail(file_id, page_no, width)
