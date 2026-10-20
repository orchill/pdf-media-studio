"""Media downloading service: yt-dlp (subprocess) + FFmpeg.

Security model:
- yt-dlp is executed via an argument array (no shell) with fixed flags;
  the only user-influenced arguments are the pre-validated URL and
  format-selection strings built from whitelisted patterns.
- Output is constrained to the configured output directory via -P.
- Cancellation terminates the process; partial `.part` files are removed.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from ..config import Config
from ..security import ValidationError
from ..tasks import TaskCancelled, TaskRecord

# Stable public video ("Me at the zoo") used to verify cookie sign-in works.
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

_BOT_TIP = (" Tip: open the Cookies / Sign-in tab in the Media Downloader and "
            "add your YouTube cookies - signing in with your own account usually "
            "resolves this check.")

_DL_RE = re.compile(r"^__P__(\S+)\|(\S*)\|(\S*)\|(\S*)\|(\S*)$")
_POST_RE = re.compile(r"^__POST__(\S*)\|(\S*)$")

FRIENDLY_ERRORS: list[tuple[str, str]] = [
    ("sign in to confirm", "YouTube asked for sign-in / bot verification for this video "
                           "(common when signed out, for age-restricted videos, or on "
                           "datacenter/cloud IPs)."),
    ("confirm your age", "This video is age-restricted; it requires signing in with a "
                         "YouTube account that has access (add your cookies in the "
                         "Cookies / Sign-in tab)."),
    ("members-only", "This video is members-only content and cannot be downloaded."),
    ("private video", "This video is private and cannot be downloaded."),
    ("video unavailable", "The video is unavailable (removed, region-locked, or the link is wrong)."),
    ("unsupported url", "This URL is not supported by yt-dlp."),
    ("is not a valid url", "This is not a valid URL."),
    ("http error 403", "The server refused access (HTTP 403) - the site may be blocking automated downloads."),
    ("http error 404", "The resource was not found (HTTP 404)."),
    ("http error 429", "Too many requests (HTTP 429) - the site is rate-limiting you. Try again later."),
    ("max-filesize", "The file exceeds the configured maximum download size."),
    ("ffmpeg not found", "FFmpeg was not found. Install it or set its path in Settings."),
    ("requested format is not available", "The selected format is not available for this video."),
    ("no video formats", "No downloadable formats were found for this URL."),
    ("unable to download webpage", "Could not reach the site - check your internet connection."),
    ("getaddrinfo failed", "Could not resolve the site - check the URL and your connection."),
    ("timed out", "The connection timed out."),
    # cookie-specific failures
    ("could not copy", "Could not read your browser's cookie database. Fully close the "
                       "browser (all windows) and try again, or switch to 'Paste cookies "
                       "file' in the Cookies / Sign-in tab."),
    ("cookies database", "Could not find that browser's cookie database. Make sure the "
                         "browser is installed and that you have visited/sign-ed-in to "
                         "YouTube with it at least once, or use 'Paste cookies file' instead."),
    ("cookie database is locked", "The browser's cookie database is locked - fully close the "
                                  "browser first, or use 'Paste cookies file' instead."),
    ("failed to decrypt", "Could not decrypt the browser's cookies on this system. Use "
                          "'Paste cookies file' in the Cookies / Sign-in tab instead."),
    ("no cookies exist", "No cookies were found for that browser profile - sign in to "
                         "YouTube in that browser first, or use 'Paste cookies file'."),
]


def _friendly(cfg: Config, stderr_tail: str) -> str:
    low = stderr_tail.lower()
    for needle, msg in FRIENDLY_ERRORS:
        if needle in low:
            if needle == "sign in to confirm" and cookie_args(cfg):
                msg += (" Your cookies did not satisfy this check - re-export fresh "
                        "cookies while logged in to YouTube, or try a different account.")
            return msg
    lines = [ln.strip() for ln in stderr_tail.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.upper().startswith("ERROR:"):
            return ln[6:].strip()[:300]
    return (lines[-1][:300] if lines else "yt-dlp failed without an error message")


# ------------------------------------------------------------- cookies
def cookie_args(cfg: Config) -> list[str]:
    """yt-dlp sign-in arguments based on the configured cookie source.

    Values are never logged: only flags and a file path / browser name.
    """
    src = str(cfg.get("cookie_source") or "none")
    if src == "file":
        p = cfg.cookies_path
        try:
            if p.is_file() and p.stat().st_size > 0:
                return ["--cookies", str(p)]
        except OSError:
            pass
        return []
    if src == "browser":
        b = str(cfg.get("cookie_browser") or "").strip().lower()
        if b:
            return ["--cookies-from-browser", b]
    return []


# ------------------------------------------------------------- detection
def find_ffmpeg(cfg: Config) -> tuple[Path | None, str]:
    """Locate ffmpeg: configured path first, then PATH. Returns (path, version)."""
    candidates: list[str] = []
    if cfg.get("ffmpeg_path"):
        candidates.append(cfg.get("ffmpeg_path"))
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)
    for cand in candidates:
        p = Path(cand)
        if p.is_file() or shutil.which(cand):
            try:
                out = subprocess.run(
                    [str(p), "-version"], capture_output=True, text=True, timeout=10,
                    shell=False)
                first = (out.stdout or out.stderr).splitlines()[0].strip()
                return p, first
            except Exception:
                continue
    return None, ""


def resolve_ytdlp_cmd(cfg: Config) -> list[str]:
    """Command array that runs yt-dlp. Custom binary overrides `python -m yt_dlp`."""
    custom = (cfg.get("ytdlp_path") or "").strip()
    if custom:
        p = Path(custom)
        if p.is_file():
            return [str(p)]
        found = shutil.which(custom)
        if found:
            return [found]
    return [sys.executable, "-m", "yt_dlp"]


def ytdlp_version(cfg: Config) -> str:
    try:
        out = subprocess.run(resolve_ytdlp_cmd(cfg) + ["--version"],
                             capture_output=True, text=True, timeout=20)
        return (out.stdout or "").strip() or "unknown"
    except Exception:
        return "not found"


def require_ffmpeg(cfg: Config, purpose: str) -> Path:
    path, _ver = find_ffmpeg(cfg)
    if path is None:
        raise ValidationError(
            f"{purpose} requires FFmpeg, which was not found. Install FFmpeg "
            "(winget install Gyan.FFmpeg on Windows, or apt install ffmpeg on Linux) "
            "and restart, or set its full path in Settings.")
    return path


# ----------------------------------------------------------------- info
AUDIO_EXTS = {"mp3", "m4a", "m4b", "wav", "ogg", "oga", "opus", "aac",
              "flac", "weba", "wma", "aiff", "alac", "mka"}


def _fmt_type(vcodec: str, acodec: str, ext: str) -> str:
    if vcodec != "none" and acodec != "none":
        return "video+audio"
    if vcodec != "none":
        return "video-only"
    if acodec != "none" or ext.lower() in AUDIO_EXTS:
        return "audio-only"
    return "other"


def _fmt_entry(f: dict) -> dict | None:
    fid = str(f.get("format_id") or "")
    ext = str(f.get("ext") or "")
    if not fid or ext in ("mhtml",) or "storyboard" in str(f.get("format_note", "")).lower():
        return None
    vcodec = f.get("vcodec") or "none"
    acodec = f.get("acodec") or "none"
    kind = _fmt_type(vcodec, acodec, ext)
    if kind == "other":
        return None
    return {
        "id": fid,
        "ext": ext,
        "type": kind,
        "vcodec": vcodec,
        "acodec": acodec,
        "height": f.get("height"),
        "width": f.get("width"),
        "fps": f.get("fps"),
        "abr": f.get("abr"),
        "vbr": f.get("vbr"),
        "tbr": f.get("tbr"),
        "filesize": f.get("filesize"),
        "filesize_approx": f.get("filesize_approx"),
        "note": f.get("format_note") or "",
    }


async def fetch_info(cfg: Config, url: str) -> dict:
    """Run `yt-dlp -J` and return trimmed metadata for the UI."""
    args = resolve_ytdlp_cmd(cfg) + [
        "--dump-single-json", "--no-playlist", "--no-warnings",
        "--socket-timeout", "20", "--retries", "2",
    ] + cookie_args(cfg) + [url]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except OSError as exc:
        raise RuntimeError(f"Could not start yt-dlp: {exc}")
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("yt-dlp timed out while fetching video info (60s)")
    if proc.returncode != 0:
        tail = (stderr or b"").decode("utf-8", "replace")
        msg = _friendly(cfg, tail)
        if "sign-in" in msg and not cookie_args(cfg):
            msg += _BOT_TIP
        raise RuntimeError(msg)
    import json
    try:
        data = json.loads(stdout.decode("utf-8", "replace"))
    except Exception:
        raise RuntimeError("yt-dlp returned unreadable metadata")

    if data.get("_type") == "playlist" and data.get("entries"):
        data = data["entries"][0]
    formats = []
    for f in data.get("formats") or []:
        e = _fmt_entry(f)
        if e:
            formats.append(e)
    videos = [f for f in formats if f["type"] in ("video+audio", "video-only")]
    audios = [f for f in formats if f["type"] == "audio-only"]
    videos.sort(key=lambda f: (f.get("height") or 0, f.get("tbr") or 0), reverse=True)
    audios.sort(key=lambda f: (f.get("abr") or f.get("tbr") or 0), reverse=True)
    return {
        "id": str(data.get("id") or ""),
        "title": data.get("title") or "Untitled",
        "uploader": data.get("uploader") or data.get("channel") or "",
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail") or "",
        "is_live": bool(data.get("is_live")),
        "extractor": data.get("extractor_key") or data.get("extractor") or "",
        "webpage_url": data.get("webpage_url") or url,
        "formats": formats[:80],
        "video_formats": videos[:40],
        "audio_formats": audios[:20],
    }


# ------------------------------------------------------------- download
def _build_format_args(params: dict, info: dict | None) -> list[str]:
    """Build yt-dlp format/codec arguments from validated UI parameters."""
    mode = params.get("mode")  # video | audio
    args: list[str] = []
    if mode == "audio":
        fmt = params.get("audio_format", "mp3")
        if fmt not in ("mp3", "m4a", "best"):
            raise ValidationError(f"Unsupported audio format: {fmt}")
        args += ["-x", "--audio-format", fmt]
        q = params.get("audio_quality")  # kbps int or None
        if fmt in ("mp3", "m4a") and q:
            q = int(q)
            if q not in (320, 256, 192, 128, 96, 64):
                raise ValidationError("Audio quality must be one of 320/256/192/128/96/64 kbps")
            args += ["--audio-quality", f"{q}K"]
        return args

    # video mode
    merge = params.get("video_format", "mp4")
    if merge not in ("mp4", "best"):
        raise ValidationError(f"Unsupported video container: {merge}")
    args += ["--merge-output-format", "mp4" if merge == "mp4" else "mkv"]

    height = params.get("height")  # None or int
    if height is not None:
        height = int(height)
        if height not in (2160, 1440, 1080, 720, 480, 360):
            raise ValidationError("Unsupported resolution preset")
    compat = bool(params.get("prefer_h264", True))

    fmt_ids = params.get("format_ids") or None
    if fmt_ids:
        vid = str(fmt_ids.get("video") or "").strip()
        aud = str(fmt_ids.get("audio") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.+\-]{1,40}", vid or ""):
            raise ValidationError("Invalid video format id")
        if aud and not re.fullmatch(r"[A-Za-z0-9_.+\-]{1,40}", aud):
            raise ValidationError("Invalid audio format id")
        spec = f"{vid}+{aud}" if aud else vid
        args += ["-f", f"{spec}/{vid}+ba/b"]
        return args

    sort_parts = []
    if compat:
        sort_parts += ["vcodec:h264", "acodec:aac"]
    if height:
        sort_parts.append(f"res:{height}")
    args += ["-f", f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b" if height else "bv*+ba/b"]
    if sort_parts:
        args += ["-S", ",".join(sort_parts)]
    return args


def download_task_wrapper(cfg: Config, params: dict):
    """Return an async runner closure for TaskManager.submit()."""
    async def runner(rec: TaskRecord) -> dict:
        return await download_task(rec, cfg, params)
    return runner


async def download_task(rec: TaskRecord, cfg: Config, params: dict) -> dict:
    """Async runner executed by TaskManager for media downloads."""
    from . import pdf_service  # noqa: F401  (import guard)

    url = params["url"]                      # pre-validated by the router
    out_dir = cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = str(params.get("video_id") or "")
    title = str(params.get("title") or "media")[:80]

    mode = params.get("mode")
    needs_ffmpeg = mode == "audio" or bool(params.get("merge", True))
    if needs_ffmpeg:
        require_ffmpeg(cfg, "Audio conversion" if mode == "audio" else "Video merging")

    args = resolve_ytdlp_cmd(cfg) + [
        "--newline", "--no-playlist", "--no-warnings", "--no-overwrites",
        "--trim-filenames", "150",
        "--retries", "3", "--fragment-retries", "3", "--socket-timeout", "30",
        "--concurrent-fragments", "4",
        "--progress-template", "download:__P__%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s",
        "--progress-template", "postprocess:__POST__%(progress.postprocessor)s|%(progress.status)s",
        "-P", str(out_dir),
        "-o", "%(title).140B [%(id)s].%(ext)s",
    ]
    ffmpeg_path, _ = find_ffmpeg(cfg)
    if ffmpeg_path is not None:
        args += ["--ffmpeg-location", str(ffmpeg_path)]
    args += cookie_args(cfg)
    max_gb = int(cfg.get("max_download_gb") or 0)
    if max_gb > 0:
        args += ["--max-filesize", f"{max_gb}g"]
    max_hours = int(cfg.get("max_duration_hours") or 0)
    if max_hours > 0 and not params.get("is_live"):
        # '?' right after the operator = pass when the field is missing
        args += ["--match-filters", f"duration<=?{max_hours * 3600}"]
    args += _build_format_args(params, None)
    args.append(url)

    started = time.time()
    rec.add_log("Command: " + " ".join(args[:6]) + " ... (URL omitted from log)")
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(out_dir))
    except OSError as exc:
        raise RuntimeError(f"Could not start yt-dlp: {exc}")
    rec.process = proc

    stderr_tail = ""

    async def pump_stderr():
        nonlocal stderr_tail
        assert proc.stderr is not None
        while True:
            raw = await proc.stderr.readline()
            if not raw:
                break
            line = raw.decode("utf-8", "replace").rstrip()
            stderr_tail = (stderr_tail + "\n" + line)[-4000:]
            rec.add_log(line)

    async def pump_stdout():
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            m = _DL_RE.match(line)
            if m:
                try:
                    done = float(m.group(1)) if m.group(1) not in ("NA", "None", "") else None
                    total_s, est_s, speed, eta = m.group(2), m.group(3), m.group(4), m.group(5)
                except ValueError:
                    continue
                total = None
                for cand in (total_s, est_s):
                    try:
                        if cand not in ("NA", "None", ""):
                            total = float(cand)
                            break
                    except ValueError:
                        continue
                speed = speed if speed not in ("NA", "None") else None
                eta = eta if eta not in ("NA", "None") else None
                if done is not None and total:
                    frac = max(0.0, min(1.0, done / total)) * 0.92
                    rec.progress = frac
                    pct = frac / 0.92 * 100
                    rec.stage = f"Downloading {pct:.0f}% at {speed or '?'}" + (f", ETA {eta}s" if eta else "")
                elif done is not None:
                    rec.progress = None
                    mb = done / 1e6
                    rec.stage = f"Downloading {mb:.1f} MB at {speed or '?'} (size unknown)"
                continue
            m = _POST_RE.match(line)
            if m:
                name, status = m.group(1) or "Post-processing", m.group(2) or ""
                rec.progress = max(rec.progress or 0, 0.93)
                rec.stage = f"Processing ({name}) {status}".strip()
                continue
            if line and not line.startswith("[download]"):
                rec.add_log(line)

    out_task = asyncio.create_task(pump_stdout())
    err_task = asyncio.create_task(pump_stderr())
    try:
        await proc.wait()
    except asyncio.CancelledError:
        # user cancellation -> hard kill, then re-raise
        try:
            proc.kill()
        except Exception:
            pass
        raise
    finally:
        if out_task:
            out_task.cancel()
        if err_task:
            err_task.cancel()
        for t in (out_task, err_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        rec.process = None
        # cleanup partial files for cancelled/failed downloads
        if rec.status in ("cancelled", "failed", "running") or proc.returncode != 0:
            if rec.cancel_event.is_set() or proc.returncode != 0:
                for pf in out_dir.glob("*.part"):
                    try:
                        if pf.stat().st_mtime >= started:
                            pf.unlink()
                    except OSError:
                        pass

    if rec.cancel_event.is_set():
        raise TaskCancelled("Cancelled by user")
    if proc.returncode != 0:
        msg = _friendly(cfg, stderr_tail)
        if "sign-in" in msg and not cookie_args(cfg):
            msg += _BOT_TIP
        raise RuntimeError(msg)

    # locate produced file(s): newest matching file written since start
    produced: list[Path] = []
    for p in out_dir.iterdir():
        if p.is_file() and p.stat().st_mtime >= started - 1 and not p.name.endswith(".part"):
            produced.append(p)
    produced.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if not produced:
        raise RuntimeError("Download finished but no output file was found")
    outputs = [{
        "name": p.name, "path": str(p), "size": p.stat().st_size,
        "url": f"/api/download?path={quote(p.as_posix())}",
    } for p in produced[:1]]
    total_size = outputs[0]["size"]
    rec.message = f"Saved {title} ({total_size / 1e6:.1f} MB)"
    return {"outputs": outputs,
            "info": {"title": title, "video_id": vid, "mode": mode,
                     "duration_s": round(time.time() - started, 1)}}
