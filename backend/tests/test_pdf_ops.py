"""End-to-end PDF operation tests through the API + task system."""
from __future__ import annotations

import io
import pathlib
import tempfile
import zipfile

import fitz
from PIL import Image

from .conftest import (image_bytes, make_image, make_pdf, make_pdf_with_image,
                       run_pdf_task, upload_file)

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pms_ops_"))


def _download(client, task: dict) -> bytes:
    out = task["result"]["outputs"][0]
    r = client.get(out["url"])
    assert r.status_code == 200, out
    return r.content


def _page_texts(data: bytes) -> list[str]:
    doc = fitz.open(stream=data, filetype="pdf")
    texts = [doc[i].get_text().strip() for i in range(doc.page_count)]
    doc.close()
    return texts


# ----------------------------------------------------------------- merge
def test_merge_two_pdfs_produces_valid_combined_document(client):
    a = make_pdf(TMP / "a.pdf", 3, "A")
    b = make_pdf(TMP / "b.pdf", 2, "B")
    ma = upload_file(client, "a.pdf", a.read_bytes())
    mb = upload_file(client, "b.pdf", b.read_bytes())

    task = run_pdf_task(client, "/api/pdf/merge",
                        {"file_ids": [ma["id"], mb["id"]]})
    assert task["status"] == "completed", task
    data = _download(client, task)
    texts = _page_texts(data)
    assert texts == ["A1", "A2", "A3", "B1", "B2"]

    # merging again must not overwrite the first output
    task2 = run_pdf_task(client, "/api/pdf/merge", {"file_ids": [ma["id"], mb["id"]]})
    names = [o["name"] for o in task2["result"]["outputs"]]
    assert names[0] != "merged.pdf" and names[0].startswith("merged")


# ---------------------------------------------------------- images to pdf
def test_images_to_pdf_order_rotation_and_page_size(client):
    red = image_bytes((300, 200), (255, 0, 0), "PNG")
    green = image_bytes((400, 400), (0, 255, 0), "JPEG")
    blue = image_bytes((200, 100), (0, 0, 255), "PNG")
    m_red = upload_file(client, "red.png", red)
    m_green = upload_file(client, "green.jpg", green)
    m_blue = upload_file(client, "blue.png", blue)

    task = run_pdf_task(client, "/api/pdf/images-to-pdf", {
        "items": [
            {"id": m_red["id"], "rotation": 0},
            {"id": m_green["id"], "rotation": 0},
            {"id": m_blue["id"], "rotation": 90},
        ],
        "page_size": "image", "margin_mm": 0, "image_dpi": 96,
    })
    assert task["status"] == "completed", task
    data = _download(client, task)
    doc = fitz.open(stream=data, filetype="pdf")
    assert doc.page_count == 3
    # page sizes follow image size (px * 72/96), rotated page swapped
    r0, r1, r2 = doc[0].rect, doc[1].rect, doc[2].rect
    assert abs(r0.width - 225) < 1 and abs(r0.height - 150) < 1   # 300x200 @96dpi
    assert abs(r1.width - 300) < 1 and abs(r1.height - 300) < 1   # 400x400
    assert abs(r2.width - 75) < 1 and abs(r2.height - 150) < 1    # 200x100 rotated
    # colors verify ORDER: red, green, blue (allow +-2 per channel)
    for page, expected in ((0, (255, 0, 0)), (1, (0, 255, 0)), (2, (0, 0, 255))):
        pix = doc[page].get_pixmap(dpi=36)
        px = pix.pixel(pix.width // 2, pix.height // 2)
        assert all(abs(a - b) <= 2 for a, b in zip(px[:3], expected)), \
            f"page {page}: {px} != {expected}"
    doc.close()


def test_images_to_pdf_a4_with_margins(client):
    img = upload_file(client, "x.jpg", image_bytes((2000, 1000), (10, 20, 30), "JPEG"))
    task = run_pdf_task(client, "/api/pdf/images-to-pdf", {
        "items": [{"id": img["id"], "rotation": 0}],
        "page_size": "a4", "orientation": "auto", "margin_mm": 10,
    })
    assert task["status"] == "completed"
    doc = fitz.open(stream=_download(client, task), filetype="pdf")
    rect = doc[0].rect
    # 2000x1000 image + orientation 'auto' -> landscape A4
    assert abs(rect.width - 841.89) < 0.5 and abs(rect.height - 595.28) < 0.5
    doc.close()


# ------------------------------------------------------------- edit pages
def test_reorder_delete_rotate_pages(client):
    pdf = make_pdf(TMP / "org.pdf", 5, "P")
    meta = upload_file(client, "org.pdf", pdf.read_bytes())
    task = run_pdf_task(client, "/api/pdf/pages", {
        "file_id": meta["id"],
        "order": [5, 1, 3],
        "rotate": {"5": 90},
    })
    assert task["status"] == "completed", task
    doc = fitz.open(stream=_download(client, task), filetype="pdf")
    assert doc.page_count == 3
    assert doc[0].get_text().strip() == "P5"
    assert doc[0].rotation == 90
    assert doc[1].get_text().strip() == "P1"
    assert doc[2].get_text().strip() == "P3"
    doc.close()


# ----------------------------------------------------------------- split
def test_split_extract_pages(client):
    pdf = make_pdf(TMP / "s.pdf", 5, "S")
    meta = upload_file(client, "s.pdf", pdf.read_bytes())
    task = run_pdf_task(client, "/api/pdf/split",
                        {"file_id": meta["id"], "mode": "extract", "pages": "2-4"})
    assert task["status"] == "completed"
    texts = _page_texts(_download(client, task))
    assert texts == ["S2", "S3", "S4"]


def test_split_ranges_multiple_outputs_zipped(client):
    pdf = make_pdf(TMP / "r.pdf", 5, "R")
    meta = upload_file(client, "r.pdf", pdf.read_bytes())
    task = run_pdf_task(client, "/api/pdf/split",
                        {"file_id": meta["id"], "mode": "ranges", "ranges": "1-2, 4"})
    assert task["status"] == "completed"
    out = task["result"]["outputs"][0]
    assert out["name"].endswith(".zip")
    data = _download(client, task)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = sorted(zf.namelist())
        assert len(names) == 2
        with zf.open(names[0]) as f:
            assert _page_texts(f.read()) == ["R1", "R2"]
        with zf.open(names[1]) as f:
            assert _page_texts(f.read()) == ["R4"]


def test_split_every_n(client):
    pdf = make_pdf(TMP / "n.pdf", 5, "N")
    meta = upload_file(client, "n.pdf", pdf.read_bytes())
    task = run_pdf_task(client, "/api/pdf/split",
                        {"file_id": meta["id"], "mode": "every_n", "every_n": 2})
    assert task["status"] == "completed"
    info = task["result"]["info"]
    assert [p["pages"] for p in info["parts"]] == [2, 2, 1]


# -------------------------------------------------------------- compress
def test_compress_reduces_size_and_reports_actual_bytes(client):
    pdf = make_pdf_with_image(TMP / "big.pdf")
    meta = upload_file(client, "big.pdf", pdf.read_bytes())
    original_size = pdf.stat().st_size
    task = run_pdf_task(client, "/api/pdf/compress",
                        {"file_id": meta["id"], "quality": 55, "dpi_cap": 72},
                        timeout=90)
    assert task["status"] == "completed", task
    info = task["result"]["info"]
    out_path = task["result"]["outputs"][0]["path"]
    import os
    actual = os.path.getsize(out_path)
    assert actual == info["new_size"] == _download(client, task).__len__()
    assert info["new_size"] < original_size
    assert info["saved_pct"] > 10
    doc = fitz.open(stream=_download(client, task), filetype="pdf")
    assert doc.page_count == 1
    doc.close()


# ------------------------------------------------------------ to images
def test_pdf_to_images_png_and_jpg(client):
    pdf = make_pdf(TMP / "t.pdf", 3, "T")
    meta = upload_file(client, "t.pdf", pdf.read_bytes())
    task = run_pdf_task(client, "/api/pdf/to-images",
                        {"file_id": meta["id"], "format": "png", "dpi": 72})
    assert task["status"] == "completed"
    with zipfile.ZipFile(io.BytesIO(_download(client, task))) as zf:
        assert len(zf.namelist()) == 3
        img = Image.open(io.BytesIO(zf.read(zf.namelist()[0])))
        assert img.format == "PNG" and img.width > 100

    task = run_pdf_task(client, "/api/pdf/to-images",
                        {"file_id": meta["id"], "format": "jpg", "dpi": 60, "pages": "1,3"})
    assert task["status"] == "completed"
    with zipfile.ZipFile(io.BytesIO(_download(client, task))) as zf:
        assert len(zf.namelist()) == 2
        assert all(n.endswith(".jpg") for n in zf.namelist())


# -------------------------------------------------------- extract images
def test_extract_embedded_images(client):
    pdf = make_pdf_with_image(TMP / "emb.pdf", size=(800, 600))
    meta = upload_file(client, "emb.pdf", pdf.read_bytes())
    task = run_pdf_task(client, "/api/pdf/extract-images", {"file_id": meta["id"]})
    assert task["status"] == "completed", task
    out = task["result"]["outputs"][0]
    data = _download(client, task)
    if out["name"].endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert len(zf.namelist()) >= 1
            img = Image.open(io.BytesIO(zf.read(zf.namelist()[0])))
    else:
        img = Image.open(io.BytesIO(data))
    assert img.format in ("JPEG", "PNG", "JP2")


def test_extract_images_none_found_fails_clearly(client):
    pdf = make_pdf(TMP / "textonly.pdf", 2, "X")
    meta = upload_file(client, "textonly.pdf", pdf.read_bytes())
    task = run_pdf_task(client, "/api/pdf/extract-images", {"file_id": meta["id"]})
    assert task["status"] == "failed"
    assert "No embedded raster images" in task["error"]
