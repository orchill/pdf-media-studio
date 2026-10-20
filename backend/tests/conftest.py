"""Pytest fixtures for PDF & Media Studio backend tests."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------- config env
# Must run before backend.app.* is imported anywhere.
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="pms_test_"))
_CFG = {
    "output_dir": str(_TMP_ROOT / "outputs"),
    "data_dir": str(_TMP_ROOT / "data"),
    "max_upload_mb": 8,
    "max_download_gb": 1,
    "max_duration_hours": 4,
    "max_concurrent_tasks": 2,
    "history_limit": 50,
    "open_browser": False,
    "port": 8991,
}
_CFG_PATH = _TMP_ROOT / "config.json"
_CFG_PATH.write_text(json.dumps(_CFG), encoding="utf-8")
os.environ["PDFMEDIA_CONFIG"] = str(_CFG_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

import fitz  # noqa: E402
from PIL import Image  # noqa: E402

import io  # noqa: E402

TERMINAL = {"completed", "failed", "cancelled"}


@pytest.fixture(scope="session")
def client():
    from backend.app.main import app
    with TestClient(app) as c:
        yield c


def wait_task(client, task_id: str, timeout: float = 60.0) -> dict:
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/tasks/{task_id}")
        assert r.status_code == 200, r.text
        data = r.json()
        if data["status"] in TERMINAL:
            return data
        time.sleep(0.2)
    raise TimeoutError(f"Task {task_id} did not finish in {timeout}s: {data}")


def run_pdf_task(client, endpoint: str, payload: dict, timeout: float = 60.0) -> dict:
    r = client.post(endpoint, json=payload)
    assert r.status_code == 200, f"{endpoint} -> {r.status_code}: {r.text}"
    return wait_task(client, r.json()["task_id"], timeout)


# ------------------------------------------------------------------ makers
def make_pdf(path: Path, pages: int = 3, marker: str = "P") -> Path:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"{marker}{i + 1}", fontsize=48)
    doc.save(str(path))
    doc.close()
    return path


def make_pdf_with_image(path: Path, size=(1600, 1200)) -> Path:
    import random
    random.seed(42)
    # incompressible noise JPEG -> compressible via downscale
    noise = bytes(random.getrandbits(8) for _ in range(size[0] * size[1]))
    img = Image.frombytes("L", size, noise).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(50, 50, 445, 330), stream=buf.getvalue())
    doc.save(str(path))
    doc.close()
    return path


def make_image(path: Path, size=(300, 200), color=(255, 0, 0), fmt="PNG") -> Path:
    img = Image.new("RGB", size, color)
    if fmt in ("JPEG", "WEBP"):
        img.save(path, format=fmt, quality=90)
    else:
        img.save(path, format=fmt)
    return path


def image_bytes(size=(300, 200), color=(255, 0, 0), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt,
                                       quality=90 if fmt in ("JPEG", "WEBP") else None)
    return buf.getvalue()


def upload_file(client, name: str, data: bytes) -> dict:
    r = client.post("/api/upload", files=[("files", (name, data))])
    assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
    return r.json()[0]
