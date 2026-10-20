"""File upload/management: workspace storage, probing, thumbnails, downloads.

Uploads live in <data>/uploads as {id}.bin with a JSON sidecar {id}.json
containing probed metadata. Client-supplied filenames are stored in the
sidecar only and sanitized before reuse - they never touch the filesystem.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import fitz
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError

from ..config import get_config
from ..security import ValidationError, ensure_within
from ..services import pdf_service
from ..utils import new_id, now_iso, sanitize_stem

log = logging.getLogger("pms.files")
router = APIRouter()

IMAGE_FORMATS = {"PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF"}
IMAGE_MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp",
              "GIF": "image/gif", "BMP": "image/bmp", "TIFF": "image/tiff"}


class Sidecar:
    def __init__(self, data: dict):
        self.data = data

    def __getattr__(self, item):
        try:
            return self.data[item]
        except KeyError:
            raise AttributeError(item)


def _sidecar_path(file_id: str) -> Path:
    if not file_id or any(c in file_id for c in "/\\.%"):
        raise HTTPException(400, "Invalid file id")
    return get_config().uploads_dir / f"{file_id}.json"


def get_upload(file_id: str) -> Sidecar:
    path = _sidecar_path(file_id)
    if not path.exists():
        raise HTTPException(404, "File not found (it may have been cleared)")
    try:
        return Sidecar(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        raise HTTPException(500, "Upload metadata is corrupted")


def upload_path(meta: Sidecar) -> Path:
    p = get_config().uploads_dir / f"{meta.data['id']}.bin"
    if not p.exists():
        raise HTTPException(404, "File content is missing")
    return p


# ------------------------------------------------------------------ upload
@router.post("/upload")
async def upload(request: Request, files: list[UploadFile] = File(...)):
    cfg = get_config()
    cfg.ensure_dirs()
    max_bytes = cfg.max_upload_bytes
    results = []
    for file in files[:24]:  # hard cap per request
        declared = request.headers.get("content-length")
        if declared and int(declared) > max_bytes * (len(files) + 2):
            raise HTTPException(413, f"Request too large (limit {cfg.get('max_upload_mb')} MB)")
        raw_name = file.filename or "upload"
        fid = new_id()
        dest = cfg.uploads_dir / f"{fid}.bin"
        size = 0
        too_big = False
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    too_big = True
                    break
                out.write(chunk)
        if too_big:
            dest.unlink(missing_ok=True)
            raise HTTPException(413, f"'{raw_name}' exceeds the {cfg.get('max_upload_mb')} MB upload limit")

        # probe content (never trust extensions)
        with dest.open("rb") as fh:
            head = fh.read(2048)
        meta: dict
        if head.startswith(b"%PDF-"):
            try:
                doc = fitz.open(str(dest))
                pages = doc.page_count
                enc = bool(doc.needs_pass)
                doc.close()
            except Exception:
                dest.unlink(missing_ok=True)
                raise HTTPException(415, f"'{raw_name}' is not a readable PDF (corrupted?)")
            if enc:
                dest.unlink(missing_ok=True)
                raise HTTPException(415, f"'{raw_name}' is password-protected")
            meta = {"kind": "pdf", "pages": pages, "format": "PDF"}
        else:
            try:
                with Image.open(dest) as im:
                    im.load()
                    fmt = (im.format or "").upper()
                    width, height = im.size
                    if fmt not in IMAGE_FORMATS:
                        raise UnidentifiedImageError()
            except (UnidentifiedImageError, Exception):
                dest.unlink(missing_ok=True)
                raise HTTPException(415, f"'{raw_name}' is not a supported image "
                                         f"(PNG, JPEG, WebP, GIF, BMP, TIFF)")
            meta = {"kind": "image", "pages": 1, "format": fmt,
                    "width": width, "height": height}
        meta.update({"id": fid, "name": sanitize_stem(raw_name, 120) or "file",
                     "orig_name": raw_name[:200], "size": size,
                     "ext": Path(raw_name).suffix.lower()[:10],
                     "uploaded_at": now_iso()})
        (cfg.uploads_dir / f"{fid}.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        results.append(meta)
        log.info("uploaded %s kind=%s size=%d", fid[:8], meta["kind"], size)
    if not results:
        raise HTTPException(400, "No files received")
    return results


# -------------------------------------------------------------- management
@router.get("/files")
async def list_files():
    cfg = get_config()
    out = []
    if cfg.uploads_dir.exists():
        for p in sorted(cfg.uploads_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
    return out


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    cfg = get_config()
    meta = get_upload(file_id)
    (cfg.uploads_dir / f"{meta.data['id']}.bin").unlink(missing_ok=True)
    _sidecar_path(file_id).unlink(missing_ok=True)
    for p in cfg.thumbs_dir.glob(f"{file_id}*"):
        p.unlink(missing_ok=True)
    return {"deleted": file_id}


# -------------------------------------------------------------- previews
@router.get("/file/{file_id}/raw")
async def raw_file(file_id: str):
    meta = get_upload(file_id)
    path = upload_path(meta)
    if meta.data["kind"] == "pdf":
        media = "application/pdf"
    else:
        media = IMAGE_MIME.get(meta.data.get("format", ""), "application/octet-stream")
    return FileResponse(path, media_type=media,
                        filename=meta.data.get("orig_name") or f"{meta.data['name']}",
                        content_disposition_type="inline")


@router.get("/file/{file_id}/thumbnail")
async def file_thumbnail(file_id: str, width: int = 240):
    return await _thumbnail(file_id, 1, width)


def _cached_thumb(key: str, width: int, producer) -> Response:
    cfg = get_config()
    cache = cfg.thumbs_dir / f"{key}_w{width}.jpg"
    if cache.exists():
        return Response(content=cache.read_bytes(), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=3600"})
    data = producer(width)
    try:
        cache.write_bytes(data)
    except OSError:
        pass
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=3600"})


async def _thumbnail(file_id: str, page: int, width: int) -> Response:
    meta = get_upload(file_id)
    width = max(60, min(640, width))
    path = upload_path(meta)
    key = f"{file_id}_p{page}"
    if meta.data["kind"] == "pdf":
        return _cached_thumb(key, width, lambda w: pdf_service.render_page_thumbnail(path, page, w))
    return _cached_thumb(key, width, lambda w: pdf_service.image_thumbnail(path, w))


# -------------------------------------------------------------- downloads
@router.get("/download")
async def download(path: str):
    """Serve a processed output file. Only paths inside the output directory
    are eligible - everything else is rejected (path traversal protection)."""
    cfg = get_config()
    try:
        resolved = ensure_within(Path(path), cfg.output_dir, "download path")
    except ValidationError as exc:
        raise HTTPException(403, str(exc))
    if not resolved.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(resolved, filename=resolved.name, content_disposition_type="attachment")
