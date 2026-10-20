#!/usr/bin/env python3
"""End-to-end smoke test against the running server (real HTTP, not TestClient)."""
import io
import json
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import fitz
from PIL import Image

BASE = "http://127.0.0.1:3000"
TMP = Path("/tmp/pms_e2e")
TMP.mkdir(exist_ok=True)
ok, fail = 0, 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {name}")
    else:
        fail += 1
        print(f"  FAIL  {name} {extra}")


def req(path, data=None, headers=None, raw=None, timeout=60):
    url = BASE + path
    if raw is not None:
        r = urllib.request.Request(url, data=raw, headers=headers or {})
    elif data is not None:
        r = urllib.request.Request(url, data=json.dumps(data).encode(),
                                   headers={"Content-Type": "application/json"})
    else:
        r = urllib.request.Request(url)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        body = resp.read()
        ctype = resp.headers.get("content-type", "")
        return resp.status, body, ctype


def upload(name, path):
    boundary = "----pmse2e"
    payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
               f"filename=\"{name}\"\r\nContent-Type: application/pdf\r\n\r\n").encode()
    payload += Path(path).read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    st, body, _ = req("/api/upload", raw=payload,
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.loads(body)[0]


def wait_task(task_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st, body, _ = req(f"/api/tasks/{task_id}")
        t = json.loads(body)
        if t["status"] in ("completed", "failed", "cancelled"):
            return t
        time.sleep(0.3)
    raise TimeoutError(task_id)


print("== E2E smoke test ==")

# 1. make fixture PDFs
def make_pdf(path, marker, pages=3):
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page(width=595, height=842)
        p.insert_text((72, 100), f"{marker}{i+1}", fontsize=48)
    doc.save(path)
    doc.close()

make_pdf(TMP / "e2e_a.pdf", "A")
make_pdf(TMP / "e2e_b.pdf", "B")
m1, m2 = upload("e2e_a.pdf", TMP / "e2e_a.pdf"), upload("e2e_b.pdf", TMP / "e2e_b.pdf")
check("upload 2 PDFs", m1["kind"] == "pdf" and m2["kind"] == "pdf")

# 2. merge
st, body, _ = req("/api/pdf/merge", {"file_ids": [m1["id"], m2["id"]]})
task = wait_task(json.loads(body)["task_id"])
check("merge completed", task["status"] == "completed", task.get("error", ""))
st, pdf_bytes, ctype = req(task["result"]["outputs"][0]["url"])
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
check("merged download + valid 6 pages", doc.page_count == 6
      and [doc[i].get_text().strip() for i in range(6)] == ["A1","A2","A3","B1","B2","B3"])
doc.close()

# 3. images -> pdf
img = Image.new("RGB", (600, 400), (250, 120, 30))
img.save(TMP / "e2e.jpg", "JPEG", quality=90)
boundary = "----pmse2e"
payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
           f"filename=\"e2e.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode()
payload += (TMP / "e2e.jpg").read_bytes() + f"\r\n--{boundary}--\r\n".encode()
st, body, _ = req("/api/upload", raw=payload, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
mimg = json.loads(body)[0]
st, body, _ = req("/api/pdf/images-to-pdf", {"items": [{"id": mimg["id"], "rotation": 0}],
                                             "page_size": "a4", "margin_mm": 5})
task = wait_task(json.loads(body)["task_id"])
check("images->pdf completed", task["status"] == "completed", task.get("error", ""))

# 4. split extract
st, body, _ = req("/api/pdf/split", {"file_id": m1["id"], "mode": "extract", "pages": "1,3"})
task = wait_task(json.loads(body)["task_id"])
check("split extract completed", task["status"] == "completed", task.get("error", ""))

# 5. compress big image pdf
import random
random.seed(7)
noise = bytes(random.getrandbits(8) for _ in range(2000 * 1500))
Image.frombytes("L", (2000, 1500), noise).convert("RGB").save(TMP / "noisy.jpg", "JPEG", quality=95)
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.insert_image(fitz.Rect(50, 50, 545, 420), stream=(TMP / "noisy.jpg").read_bytes())
doc.save(TMP / "e2e_big.pdf")
doc.close()
mbig = upload("e2e_big.pdf", TMP / "e2e_big.pdf")
orig = (TMP / "e2e_big.pdf").stat().st_size
st, body, _ = req("/api/pdf/compress", {"file_id": mbig["id"], "quality": 55, "dpi_cap": 80})
task = wait_task(json.loads(body)["task_id"], timeout=90)
new_size = task["result"]["info"]["new_size"] if task["status"] == "completed" else None
check("compress reduced size", task["status"] == "completed" and new_size and new_size < orig,
      f"{orig} -> {new_size}")

# 6. media info on a URL that must be rejected (SSRF) and one that fails cleanly
try:
    req("/api/media/info?url=http://127.0.0.1:3000/api/health")
    check("SSRF local URL rejected", False)
except urllib.error.HTTPError as e:
    check("SSRF local URL rejected", e.code == 400)

# 7. youtube metadata attempt (network dependent - report only)
print("  NOTE  attempting YouTube metadata (network dependent)...")
try:
    st, body, _ = req("/api/media/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ", timeout=90)
    info = json.loads(body)
    print(f"  NOTE  YouTube metadata OK: '{info['title'][:60]}' formats={len(info['formats'])}")
except urllib.error.HTTPError as e:
    print(f"  NOTE  YouTube metadata unavailable from this network (HTTP {e.code}: {e.read()[:160]!r})")
except Exception as e:
    print(f"  NOTE  YouTube metadata unavailable: {e}")

# 8. security: traversal
try:
    req("/api/download?path=/etc/passwd")
    check("path traversal blocked", False)
except urllib.error.HTTPError as e:
    check("path traversal blocked", e.code == 403)

# 9. UI served
st, body, ctype = req("/")
check("UI served", b"PDF" in body and b"root" in body)

print(f"\n== RESULT: {ok} passed, {fail} failed ==")
sys.exit(1 if fail else 0)
