"""Dependency and environment diagnostics (versions, paths, disk space)."""
from __future__ import annotations

import importlib.metadata as ilmd
import platform
import shutil
import subprocess
import sys

from .. import APP_NAME, __version__
from ..config import Config


def _pkg_version(name: str) -> str:
    try:
        return ilmd.version(name)
    except Exception:
        return "not found"


def system_info(cfg: Config) -> dict:
    from .media_service import find_ffmpeg, ytdlp_version

    ffmpeg_path, ffmpeg_ver = find_ffmpeg(cfg)
    ffprobe = shutil.which("ffprobe") or ""
    ytdlp_custom = bool((cfg.get("ytdlp_path") or "").strip())
    try:
        out = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, text=True, timeout=20)
        ytdlp_ok = out.returncode == 0
        ytdlp_ver = (out.stdout or "").strip() or "unknown"
    except Exception:
        ytdlp_ok, ytdlp_ver = False, "not found"

    free_gb = None
    try:
        import shutil as _sh
        free_gb = round(_sh.disk_usage(cfg.output_dir).free / 1024**3, 1)
    except Exception:
        pass

    return {
        "app": APP_NAME,
        "app_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(terse=True),
        "output_dir": str(cfg.output_dir),
        "data_dir": str(cfg.data_dir),
        "free_disk_gb": free_gb,
        "deps": {
            "ffmpeg": {"found": ffmpeg_path is not None,
                       "path": str(ffmpeg_path) if ffmpeg_path else "",
                       "version": ffmpeg_ver},
            "ffprobe": {"found": bool(ffprobe), "path": ffprobe},
            "ytdlp": {"found": ytdlp_ok or ytdlp_custom,
                      "version": ytdlp_ver,
                      "source": "custom path" if ytdlp_custom else "python module"},
            "pymupdf": _pkg_version("PyMuPDF"),
            "pypdf": _pkg_version("pypdf"),
            "pillow": _pkg_version("pillow"),
            "fastapi": _pkg_version("fastapi"),
        },
        "config": cfg.public_dict(),
    }
