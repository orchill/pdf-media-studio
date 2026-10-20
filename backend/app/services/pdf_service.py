"""PDF processing service built on PyMuPDF (fitz), pypdf and Pillow.

Library split (documented in README):
- pypdf (BSD): merge + split - structural page copying.
- PyMuPDF (AGPL): page edits (reorder/delete/rotate), rendering/thumbnails,
  image extraction, compression, and image->PDF composition.
- Pillow (MIT-CMU): image decoding/validation, transcoding, thumbnails.

Every operation writes to a NEW uniquely-named file in the output directory;
uploaded source files are never modified or overwritten.
"""
from __future__ import annotations

import io
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Callable
from urllib.parse import quote

import fitz  # PyMuPDF
from PIL import Image, ImageOps

from ..security import ValidationError
from ..tasks import TaskCancelled, TaskRecord
from ..utils import sanitize_stem, unique_path

ReportFn = Callable[[str, float | None], None]

PAGE_SIZES_PT: dict[str, tuple[float, float]] = {
    "a4": (595.28, 841.89),
    "a3": (841.89, 1190.55),
    "a5": (419.53, 595.28),
    "letter": (612.0, 792.0),
    "legal": (612.0, 1008.0),
}


def _cancel_check(rec: TaskRecord) -> None:
    if rec.cancel_event.is_set():
        raise TaskCancelled("Cancelled by user")


def _mm_to_pt(mm: float) -> float:
    return mm * 72.0 / 25.4


def open_pdf(path: Path) -> fitz.Document:
    try:
        doc = fitz.open(str(path))
        if doc.needs_pass:
            doc.close()
            raise ValidationError("This PDF is password-protected and cannot be processed")
        return doc
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"File is not a readable PDF document ({exc.__class__.__name__})")


def verify_pdf(path: Path, expected_pages: int | None = None) -> int:
    """Re-open a produced PDF to confirm it is valid; return page count."""
    try:
        doc = fitz.open(str(path))
        count = doc.page_count
        doc.close()
    except Exception as exc:
        raise RuntimeError(f"Produced PDF failed validation: {exc}")
    if count < 1:
        raise RuntimeError("Produced PDF has no pages")
    if expected_pages is not None and count != expected_pages:
        raise RuntimeError(f"Produced PDF has {count} pages, expected {expected_pages}")
    return count


def make_output(cfg_dir: Path, stem: str, suffix: str) -> Path:
    return unique_path((cfg_dir / f"{sanitize_stem(stem)}{suffix}"))


def output_entry(path: Path) -> dict:
    return {"name": path.name, "path": str(path), "size": path.stat().st_size,
            "url": f"/api/download?path={quote(path.as_posix())}"}


# =============================================================== merge
def merge_task(rec: TaskRecord, inputs: list[Path], out_dir: Path) -> dict:
    from pypdf import PdfWriter

    if len(inputs) < 2:
        raise ValidationError("Select at least two PDF files to merge")
    out = make_output(out_dir, "merged", ".pdf")
    writer = PdfWriter()
    total_pages = 0
    try:
        for i, path in enumerate(inputs):
            _cancel_check(rec)
            rec.report(f"Adding {path.name} ({i + 1}/{len(inputs)})", (i) / len(inputs))
            try:
                writer.append(str(path))
            except Exception as exc:
                raise ValidationError(f"'{path.name}' is not a readable PDF: {exc}")
        _cancel_check(rec)
        rec.report("Writing merged document", 0.9)
        with open(out, "wb") as fh:
            writer.write(fh)
    finally:
        try:
            writer.close()
        except Exception:
            pass
    pages = verify_pdf(out)
    rec.message = f"Merged {len(inputs)} files, {pages} pages"
    return {"outputs": [output_entry(out)], "info": {"pages": pages, "inputs": len(inputs)}}


# ======================================================= images -> PDF
def _embed_bytes(data: bytes, img_format: str | None) -> tuple[bytes, str]:
    """Return (bytes_to_embed, format_tag). Transcode formats MuPDF can't read."""
    supported = {"JPEG", "PNG", "GIF", "TIFF", "BMP"}
    if (img_format or "").upper() in supported:
        return data, img_format.upper()
    # WEBP/unknown -> transcode via Pillow (alpha preserved as PNG, else JPEG q95)
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        buf = io.BytesIO()
        if has_alpha:
            im.convert("RGBA").save(buf, format="PNG")
            return buf.getvalue(), "PNG"
        im.convert("RGB").save(buf, format="JPEG", quality=95)
        return buf.getvalue(), "JPEG"


def images_to_pdf_task(rec: TaskRecord, images: list[dict], opts: dict,
                       out_dir: Path) -> dict:
    """images: [{id, path, rotation}] in final order; opts from the UI."""
    if not images:
        raise ValidationError("No images selected")
    page_size = str(opts.get("page_size", "a4")).lower()
    orientation = str(opts.get("orientation", "auto")).lower()
    margin_mm = max(0.0, min(50.0, float(opts.get("margin_mm", 10))))
    dpi = int(opts.get("image_dpi", 96))
    dpi = dpi if dpi in (72, 96, 150, 300) else 96
    quality = opts.get("jpeg_quality", None)  # None = preserve original bytes
    if quality is not None:
        quality = max(10, min(95, int(quality)))

    out = make_output(out_dir, "images", ".pdf")
    doc = fitz.open()
    try:
        margin = _mm_to_pt(margin_mm)
        total = len(images)
        for i, item in enumerate(images):
            _cancel_check(rec)
            src = Path(item["path"])
            rotation = int(item.get("rotation", 0)) % 360
            rec.report(f"Placing image {i + 1}/{total} ({src.name})", i / total)
            data = src.read_bytes()
            try:
                embed, _fmt = _embed_bytes(data, item.get("format"))
            except Exception:
                raise ValidationError(f"Image '{src.name}' could not be decoded")

            with Image.open(io.BytesIO(data)) as im:
                im.load()
                im = ImageOps.exif_transpose(im)
                px_w, px_h = im.size

            if page_size == "image":
                pw = px_w * 72.0 / dpi + 2 * margin
                ph = px_h * 72.0 / dpi + 2 * margin
                if rotation in (90, 270):
                    pw, ph = ph, pw
            else:
                pw, ph = PAGE_SIZES_PT.get(page_size, PAGE_SIZES_PT["a4"])
                eff_w, eff_h = (px_h, px_w) if rotation in (90, 270) else (px_w, px_h)
                if orientation == "landscape" or (orientation == "auto" and eff_w > eff_h):
                    pw, ph = ph, pw
            page = doc.new_page(width=pw, height=ph)
            rect = fitz.Rect(margin, margin, pw - margin, ph - margin)
            if rect.is_empty or rect.width <= 1 or rect.height <= 1:
                rect = fitz.Rect(0, 0, pw, ph)
            embed_data = embed
            if quality is not None and _fmt_tag_is_recompressible(item.get("format")):
                embed_data = _recompress(embed, quality)
            page.insert_image(rect, stream=embed_data, rotate=rotation, keep_proportion=True)
        rec.report("Saving PDF", 0.95)
        doc.save(str(out), garbage=3, deflate=True)
    finally:
        doc.close()
    pages = verify_pdf(out, expected_pages=len(images))
    rec.message = f"Created {pages}-page PDF from {len(images)} images"
    return {"outputs": [output_entry(out)],
            "info": {"pages": pages, "images": len(images), "page_size": page_size,
                     "margin_mm": margin_mm}}


def _fmt_tag_is_recompressible(fmt: str | None) -> bool:
    return (fmt or "").upper() in {"JPEG", "PNG", "BMP", "TIFF", "GIF", "WEBP"}


def _recompress(data: bytes, quality: int) -> bytes:
    """Optionally JPEG-recompress to shrink output (alpha flattened to white)."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                bg = Image.new("RGB", im.size, (255, 255, 255))
                im = im.convert("RGBA")
                bg.paste(im, mask=im.split()[-1])
                buf = io.BytesIO()
                bg.save(buf, format="JPEG", quality=quality, optimize=True)
            else:
                buf = io.BytesIO()
                im.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
    except Exception:
        return data


# ======================================================== edit pages
def edit_pages_task(rec: TaskRecord, src: Path, order: list[int],
                    rotate_map: dict[int, int], out_dir: Path,
                    output_name: str | None = None,
                    base_name: str | None = None) -> dict:
    """Reorder / keep subset / rotate in one pass. `order` = final sequence of
    1-based original page numbers; pages not listed are removed."""
    doc = open_pdf(src)
    n = doc.page_count  # captured before any close
    out_stem = output_name or f"{base_name or src.stem}_edited"
    out = make_output(out_dir, out_stem, ".pdf")
    new = fitz.open()
    try:
        total = len(order)
        for i, page_no in enumerate(order):
            _cancel_check(rec)
            rec.report(f"Building page {i + 1}/{total}", i / max(1, total))
            new.insert_pdf(doc, from_page=page_no - 1, to_page=page_no - 1)
            deg = int(rotate_map.get(page_no, 0)) % 360
            if deg:
                new[-1].set_rotation((new[-1].rotation + deg) % 360)
        rec.report("Saving", 0.95)
        new.save(str(out), garbage=3, deflate=True)
    finally:
        doc.close()
        new.close()
    pages = verify_pdf(out, expected_pages=len(order))
    deleted = n - len(set(order))
    rec.message = (f"{pages} pages saved"
                   + (f" ({deleted} removed)" if deleted else "")
                   + (f", rotation applied" if rotate_map else ""))
    return {"outputs": [output_entry(out)],
            "info": {"pages": pages, "source_pages": n, "removed": deleted,
                     "rotated": {str(k): v for k, v in rotate_map.items() if v}}}


# ============================================================ split
def _write_pages_with_pypdf(src: Path, page_numbers: list[int], out: Path) -> None:
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for p in page_numbers:
        writer.add_page(reader.pages[p - 1])
    with open(out, "wb") as fh:
        writer.write(fh)


def split_task(rec: TaskRecord, src: Path, mode: str, ranges: str | None,
               every_n: int | None, pages: str | None, out_dir: Path,
               base_name: str | None = None) -> dict:
    doc = open_pdf(src)
    try:
        n = doc.page_count
    finally:
        doc.close()

    stem = base_name or src.stem
    parts: list[tuple[str, Path, list[int]]] = []  # (label, path, pages)

    if mode == "extract":
        from ..security import parse_pages
        sel = parse_pages(pages, n)
        out = make_output(out_dir, f"{stem}_extract", ".pdf")
        rec.report(f"Extracting {len(sel)} pages", 0.4)
        _write_pages_with_pypdf(src, sel, out)
        parts.append((f"pages {sel[0]}-{sel[-1]}", out, sel))

    elif mode == "every_n":
        if not every_n or every_n < 1:
            raise ValidationError("'every N pages' must be at least 1")
        groups = [list(range(a, min(a + every_n, n + 1))) for a in range(1, n + 1, every_n)]
        for k, group in enumerate(groups, 1):
            _cancel_check(rec)
            rec.report(f"Writing part {k}/{len(groups)}", (k - 1) / len(groups))
            out = make_output(out_dir, f"{stem}_part{k:02d}", ".pdf")
            _write_pages_with_pypdf(src, group, out)
            parts.append((f"pages {group[0]}-{group[-1]}", out, group))

    elif mode == "ranges":
        from ..security import parse_page_groups
        groups_raw = parse_page_groups(ranges or "", n)
        for k, (a, b) in enumerate(groups_raw, 1):
            _cancel_check(rec)
            rec.report(f"Writing part {k}/{len(groups_raw)}", (k - 1) / len(groups_raw))
            sel = list(range(a, b + 1))
            out = make_output(out_dir, f"{stem}_p{a}-{b}", ".pdf")
            _write_pages_with_pypdf(src, sel, out)
            parts.append((f"pages {a}-{b}", out, sel))
    else:
        raise ValidationError(f"Unknown split mode: {mode}")

    # validate every produced file
    for _, path, sel in parts:
        verify_pdf(path, expected_pages=len(sel))

    outputs: list[dict] = []
    if len(parts) == 1:
        outputs.append(output_entry(parts[0][1]))
    else:
        zip_path = make_output(out_dir, f"{stem}_split", ".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for _, path, _sel in parts:
                zf.write(path, path.name)
        outputs.append(output_entry(zip_path))
        for _, path, _sel in parts:
            try:
                path.unlink()
            except OSError:
                pass
    rec.message = f"Split into {len(parts)} document(s)" if len(parts) > 1 \
        else f"Extracted {len(parts[0][2])} page(s)"
    return {"outputs": outputs,
            "info": {"mode": mode, "source_pages": n,
                     "parts": [{"label": lbl, "pages": len(sel)} for lbl, _, sel in parts]}}


# ========================================================= compress
def compress_task(rec: TaskRecord, src: Path, quality: int, dpi_cap: int,
                  out_dir: Path, base_name: str | None = None) -> dict:
    """Recompress embedded raster images (no alpha) and clean the file.

    Strategy: for every embedded image, compute its displayed size; if the
    stored bitmap is larger than needed for `dpi_cap`, downscale it and/or
    JPEG-re-encode at `quality`, then replace the object in-place. Images
    with transparency (smask) are left untouched to preserve alpha.
    """
    quality = max(10, min(95, int(quality)))
    dpi_cap = max(36, min(300, int(dpi_cap)))
    out = make_output(out_dir, f"{base_name or src.stem}_compressed", ".pdf")
    doc = open_pdf(src)
    replaced = 0
    try:
        # map xref -> largest displayed size (pt)
        displayed: dict[int, tuple[float, float]] = {}
        owner_page: dict[int, int] = {}
        for pno in range(doc.page_count):
            _cancel_check(rec)
            page = doc[pno]
            for img in page.get_images(full=True):
                xref = img[0]
                owner_page.setdefault(xref, pno)
                try:
                    for r in page.get_image_rects(xref):
                        w, h = displayed.get(xref, (0.0, 0.0))
                        displayed[xref] = (max(w, r.width), max(h, r.height))
                except Exception:
                    continue
        xrefs = list(displayed.keys())
        total = len(xrefs)
        for i, xref in enumerate(xrefs):
            _cancel_check(rec)
            rec.report(f"Optimizing image {i + 1}/{total}", 0.1 + 0.8 * i / max(1, total))
            try:
                info = doc.extract_image(xref)
            except Exception:
                continue
            ext = (info.get("ext") or "").lower()
            data = info.get("image") or b""
            if not data:
                continue
            img_rect_w, img_rect_h = displayed.get(xref, (0.0, 0.0))
            if img_rect_w <= 1 and img_rect_h <= 1:
                continue
            target_w = int(img_rect_w / 72.0 * dpi_cap)
            target_h = int(img_rect_h / 72.0 * dpi_cap)
            target_w, target_h = max(1, target_w), max(1, target_h)
            try:
                with Image.open(io.BytesIO(data)) as im:
                    im.load()
                    has_alpha = (info.get("smask", 0) != 0) or im.mode in ("RGBA", "LA")
                    if has_alpha:
                        continue  # preserve transparency; do not touch
                    w, h = im.size
                    needs_downscale = w > target_w * 1.05 or h > target_h * 1.05
                    is_lossy_src = ext in ("jpg", "jpeg")
                    if not needs_downscale and is_lossy_src:
                        continue  # avoid generation loss for well-sized JPEGs
                    if not needs_downscale and ext not in ("png", "bmp", "gif", "tiff", "tiffa", "jpx", "jp2"):
                        continue
                    if needs_downscale:
                        scale = min(target_w / w, target_h / h, 1.0)
                        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                        im = im.convert("RGB").resize(new_size, Image.LANCZOS)
                    else:
                        im = im.convert("RGB")
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=quality, optimize=True)
                    new_bytes = buf.getvalue()
                    if len(new_bytes) < len(data) * 0.95:
                        pno = owner_page.get(xref, 0)
                        doc[pno].replace_image(xref, stream=new_bytes)
                        replaced += 1
            except Exception:
                continue  # leave problematic images untouched
        rec.report("Saving optimized document", 0.95)
        doc.save(str(out), garbage=4, deflate=True, deflate_fonts=True, clean=True)
        n_pages = doc.page_count
    finally:
        doc.close()

    orig_size = src.stat().st_size
    new_size = out.stat().st_size
    verify_pdf(out)
    saved = max(0, orig_size - new_size)
    pct = (saved / orig_size * 100.0) if orig_size else 0.0
    note = None
    if new_size >= orig_size:
        note = ("The document was already well optimized - the result is not smaller "
                "than the source. The original file is kept.")
    rec.message = f"Reduced by {pct:.1f}% ({new_size:,} bytes)"
    return {"outputs": [output_entry(out)],
            "info": {"original_size": orig_size, "new_size": new_size,
                     "saved_bytes": saved, "saved_pct": round(pct, 1),
                     "images_replaced": replaced, "pages": n_pages},
            "note": note}


# ==================================================== extract images
def extract_images_task(rec: TaskRecord, src: Path, out_dir: Path,
                        base_name: str | None = None) -> dict:
    doc = open_pdf(src)
    tmp_dir = rec.temp_dir or (out_dir / ".tmp_extract")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    try:
        seen: set[int] = set()
        smasks: set[int] = set()
        for pno in range(doc.page_count):
            for img in doc[pno].get_images(full=True):
                smasks.add(img[1]) if img[1] else None
        total_images = 0
        for pno in range(doc.page_count):
            _cancel_check(rec)
            page_images = doc[pno].get_images(full=True)
            for k, img in enumerate(page_images):
                xref = img[0]
                if xref in seen or xref in smasks:
                    continue
                seen.add(xref)
                try:
                    info = doc.extract_image(xref)
                except Exception:
                    continue
                data = info.get("image") or b""
                if not data:
                    continue
                ext = (info.get("ext") or "png").lower()
                if ext in ("jpx", "jp2"):
                    ext = "jp2"
                name = f"{base_name or src.stem}_p{pno + 1:03d}_{len(saved) + 1:02d}_{info.get('width', 0)}x{info.get('height', 0)}.{ext}"
                path = tmp_dir / name
                path.write_bytes(data)
                saved.append(path)
                total_images += 1
                rec.report(f"Extracting images (page {pno + 1})", None)
        if total_images == 0:
            raise ValidationError("No embedded raster images were found in this PDF "
                                  "(vector graphics and text are not extractable as images)")
        if total_images == 1:
            out = make_output(out_dir, f"{base_name or src.stem}_image", saved[0].suffix)
            shutil.copyfile(saved[0], out)
            outputs = [output_entry(out)]
        else:
            out = make_output(out_dir, f"{base_name or src.stem}_images", ".zip")
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in saved:
                    zf.write(p, p.name)
            outputs = [output_entry(out)]
    finally:
        doc.close()
        if rec.temp_dir is None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    rec.message = f"Extracted {total_images} image(s)"
    return {"outputs": outputs, "info": {"count": total_images}}


# ====================================================== PDF -> images
def to_images_task(rec: TaskRecord, src: Path, fmt: str, dpi: int,
                   pages: str | None, out_dir: Path,
                   base_name: str | None = None) -> dict:
    fmt = "jpg" if str(fmt).lower() in ("jpg", "jpeg") else "png"
    dpi = max(36, min(600, int(dpi)))
    doc = open_pdf(src)
    try:
        n = doc.page_count
    finally:
        doc.close()
    from ..security import parse_pages
    sel = parse_pages(pages, n)
    tmp_dir = rec.temp_dir or (out_dir / ".tmp_toimg")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    doc = open_pdf(src)
    try:
        for i, pno in enumerate(sel):
            _cancel_check(rec)
            rec.report(f"Rendering page {pno}/{n}", i / len(sel))
            page = doc[pno - 1]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            if fmt == "png":
                path = tmp_dir / f"{base_name or src.stem}_p{pno:03d}.png"
                pix.save(str(path))
            else:
                from PIL import Image as PILImage
                img = PILImage.frombytes("RGB", (pix.width, pix.height), pix.samples)
                path = tmp_dir / f"{base_name or src.stem}_p{pno:03d}.jpg"
                img.save(path, format="JPEG", quality=90)
            saved.append(path)
            pix = None
        if len(saved) == 1:
            out = make_output(out_dir, f"{base_name or src.stem}_p{sel[0]:03d}", f".{fmt}")
            shutil.copyfile(saved[0], out)
            outputs = [output_entry(out)]
        else:
            out = make_output(out_dir, f"{base_name or src.stem}_{fmt}", ".zip")
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in saved:
                    zf.write(p, p.name)
            outputs = [output_entry(out)]
    finally:
        doc.close()
        if rec.temp_dir is None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    rec.message = f"Exported {len(saved)} page(s) as {fmt.upper()} @ {dpi} DPI"
    return {"outputs": outputs, "info": {"count": len(saved), "format": fmt, "dpi": dpi}}


# ------------------------------------------------------------- thumbnails
def render_page_thumbnail(src: Path, page_no: int, width: int) -> bytes:
    """Render one page to a PNG thumbnail (cached by the caller)."""
    doc = open_pdf(src)
    try:
        page_no = max(1, min(page_no, doc.page_count))
        page = doc[page_no - 1]
        zoom = max(0.2, min(3.0, width / max(1.0, page.rect.width)))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def image_thumbnail(path: Path, width: int) -> bytes:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((width, int(width * 4)), Image.LANCZOS)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=85)
        return buf.getvalue()
