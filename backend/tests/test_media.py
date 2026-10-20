"""Media pipeline tests using a LOCAL HTTP server (no external websites).

Covers: yt-dlp generic-extractor metadata, download with progress, MP3
conversion through FFmpeg, MP4 output, and cancellation cleanup.
Real-YouTube verification is intentionally NOT automated here (see README).
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import json
import pathlib
import shutil
import socket
import subprocess
import tempfile
import threading
import time

import pytest

from backend.app.config import Config
from backend.app.services import media_service
from backend.app.tasks import TaskCancelled, TaskManager

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pms_media_"))

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                   check=True, capture_output=True)


def _make_wav(path: pathlib.Path, seconds: float = 1.0, rate: int = 8000) -> None:
    """Synthesize a valid WAV without ffmpeg (stdlib only)."""
    import math
    import struct
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * seconds)):
            frames += struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * i / rate)))
        w.writeframes(bytes(frames))


@pytest.fixture(scope="module")
def media_server():
    """Serve generated media files over local HTTP."""
    root = TMP / "www"
    root.mkdir(exist_ok=True)
    wav = root / "tone.wav"
    mp4 = root / "clip.mp4"
    big = root / "bigfile.mp4"
    if HAS_FFMPEG:
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-q:a", "9",
                str(wav))
        _ffmpeg("-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
                "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                "-shortest", str(mp4))
    else:
        _make_wav(wav)  # metadata/cancel tests stay meaningful without ffmpeg
    if not big.exists():
        big.write_bytes(b"\x5a" * (48 * 1024 * 1024))  # 48 MB for cancel test

    port = _free_port()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield {"port": port, "root": root, "wav": wav, "mp4": mp4, "big": big}
    httpd.shutdown()


def _test_cfg(tmp_name: str) -> Config:
    cfg_dir = TMP / tmp_name
    cfg_dir.mkdir(exist_ok=True)
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({"output_dir": str(cfg_dir / "out"),
                                    "data_dir": str(cfg_dir / "data")}),
                        encoding="utf-8")
    return Config(cfg_file)


def _run_manager(coro_factory) -> dict:
    return asyncio.run(coro_factory())


# ------------------------------------------------------------------ info
def test_ytdlp_generic_metadata(media_server):
    """yt-dlp retrieves metadata for a supported (local) URL."""
    url = f"http://127.0.0.1:{media_server['port']}/tone.wav"
    cfg = _test_cfg("info")

    async def go():
        return await media_service.fetch_info(cfg, url)

    info = asyncio.run(go())
    assert info["title"]
    assert info["id"]
    assert info["formats"], "expected at least one format from generic extractor"


def test_ytdlp_metadata_error_message(media_server):
    async def go():
        return await media_service.fetch_info(
            _test_cfg("info_err"), f"http://127.0.0.1:{media_server['port']}/missing.mp4")
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(go())
    assert "404" in str(exc.value) or "not found" in str(exc.value).lower() or \
        "unavailable" in str(exc.value).lower()


# -------------------------------------------------------------- downloads
@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_mp3_conversion_via_ffmpeg(media_server):
    """WAV source -> MP3 output through yt-dlp + FFmpeg."""
    cfg = _test_cfg("mp3")
    params = {"url": f"http://127.0.0.1:{media_server['port']}/tone.wav",
              "mode": "audio", "audio_format": "mp3", "audio_quality": 192,
              "video_id": "tone", "title": "tone"}

    async def go():
        tm = TaskManager(cfg.history_path, 10, 2)

        async def runner(rec):
            return await media_service.download_task(rec, cfg, params)

        task_id = tm.submit("media_audio", "tone test", runner)
        rec = tm.get(task_id)
        while rec.status not in ("completed", "failed", "cancelled"):
            await asyncio.sleep(0.2)
        return rec

    rec = asyncio.run(go())
    assert rec.status == "completed", (rec.status, rec.error, rec.log[-5:])
    out = rec.result["outputs"][0]
    assert out["name"].endswith(".mp3")
    assert out["size"] > 1000
    produced = pathlib.Path(out["path"])
    assert produced.exists()


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_m4a_conversion_via_ffmpeg(media_server):
    """WAV source -> M4A output through yt-dlp + FFmpeg (same post-processor path)."""
    cfg = _test_cfg("m4a")
    params = {"url": f"http://127.0.0.1:{media_server['port']}/tone.wav",
              "mode": "audio", "audio_format": "m4a", "audio_quality": 192,
              "video_id": "tone", "title": "tone"}

    async def go():
        tm = TaskManager(cfg.history_path, 10, 2)

        async def runner(rec):
            return await media_service.download_task(rec, cfg, params)

        task_id = tm.submit("media_audio", "tone m4a test", runner)
        rec = tm.get(task_id)
        while rec.status not in ("completed", "failed", "cancelled"):
            await asyncio.sleep(0.2)
        return rec

    rec = asyncio.run(go())
    assert rec.status == "completed", (rec.status, rec.error, rec.log[-5:])
    assert rec.result["outputs"][0]["name"].endswith(".m4a")


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_mp4_output(media_server):
    cfg = _test_cfg("mp4")
    params = {"url": f"http://127.0.0.1:{media_server['port']}/clip.mp4",
              "mode": "video", "video_format": "mp4", "video_id": "clip",
              "title": "clip", "merge": True}

    async def go():
        tm = TaskManager(cfg.history_path, 10, 2)

        async def runner(rec):
            return await media_service.download_task(rec, cfg, params)

        task_id = tm.submit("media_video", "clip test", runner)
        rec = tm.get(task_id)
        while rec.status not in ("completed", "failed", "cancelled"):
            await asyncio.sleep(0.2)
        return rec

    rec = asyncio.run(go())
    assert rec.status == "completed", (rec.status, rec.error, rec.log[-5:])
    assert rec.result["outputs"][0]["name"].endswith(".mp4")


def test_download_cancel_cleans_part_files(media_server):
    """Cancelled downloads are killed, marked cancelled, and .part files removed."""
    cfg = _test_cfg("cancel")
    out_dir = cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    params = {"url": f"http://127.0.0.1:{media_server['port']}/bigfile.mp4",
              "mode": "video", "video_format": "best", "video_id": "big",
              "title": "big", "merge": False}

    async def go():
        tm = TaskManager(cfg.history_path, 10, 2)

        async def runner(rec):
            return await media_service.download_task(rec, cfg, params)

        task_id = tm.submit("media_video", "cancel test", runner)
        rec = tm.get(task_id)
        # wait until download has actually started producing progress
        deadline = time.time() + 30
        while time.time() < deadline:
            if rec.status == "running" and (rec.progress or 0) > 0:
                break
            if rec.status in ("completed", "failed"):  # too fast to cancel
                return rec
            await asyncio.sleep(0.05)
        tm.cancel(task_id)
        while rec.status not in ("completed", "failed", "cancelled"):
            await asyncio.sleep(0.1)
        return rec

    rec = asyncio.run(go())
    assert rec.status == "cancelled", rec.status
    leftovers = [p.name for p in out_dir.glob("*.part")]
    assert not leftovers, f"part files left behind: {leftovers}"
    assert not any(p.name.endswith(".part") for p in out_dir.iterdir())


# ------------------------------------------------------ TaskManager unit
def test_session_challenged_detection():
    assert media_service._session_challenged(
        "ERROR: [youtube] abc: The page needs to be reloaded.")
    assert media_service._session_challenged("ERROR: No video formats found!")
    assert media_service._session_challenged(
        "ERROR: Sign in to confirm you're not a bot.")
    assert not media_service._session_challenged("ERROR: HTTP Error 404: Not Found")
    assert not media_service._session_challenged("")


def test_task_manager_cancel_and_temp_cleanup():
    async def go():
        cfg = _test_cfg("tm_cancel")
        cfg.ensure_dirs()
        tm = TaskManager(cfg.history_path, 10, 2)
        temp_dir = cfg.tmp_dir / "task-temp-check"
        temp_dir.mkdir(parents=True, exist_ok=True)
        started = asyncio.Event()
        release = asyncio.Event()

        async def runner(rec):
            started.set()
            await release.wait()
            return {"outputs": []}

        task_id = tm.submit("unit", "cancel me", runner, temp_dir=temp_dir)
        rec = tm.get(task_id)
        await started.wait()
        assert rec.status == "running"
        tm.cancel(task_id)
        await asyncio.sleep(0.2)
        assert rec.status == "cancelled"
        assert not temp_dir.exists(), "temp dir must be cleaned after cancel"

        # queued task cancelled before start
        block = asyncio.Event()

        async def slow_runner(rec):
            await block.wait()
            return {}

        id1 = tm.submit("unit", "a", slow_runner)
        id2 = tm.submit("unit", "b", slow_runner)
        tm.cancel(id2)
        rec2 = tm.get(id2)
        assert rec2.status == "cancelled"
        block.set()
        await asyncio.sleep(0.2)

    asyncio.run(go())


def test_history_limit_enforced():
    async def go():
        cfg = _test_cfg("hist")
        cfg.ensure_dirs()
        tm = TaskManager(cfg.history_path, 5, 2)

        for i in range(7):
            async def runner(rec, i=i):
                return {}
            tm.submit("unit", f"t{i}", runner)
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.3)
        assert len(tm.history) <= 5
        import json
        data = json.loads(cfg.history_path.read_text())
        assert len(data) <= 5

    asyncio.run(go())
