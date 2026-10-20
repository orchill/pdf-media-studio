"""Media endpoints: metadata lookup, download tasks, cookie sign-in."""
from __future__ import annotations

import os
import re
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import COOKIE_BROWSERS, ConfigError, get_config
from ..security import ValidationError, validate_media_url
from ..services import cookie_store, media_service
from ..tasks import TaskManager

router = APIRouter()


def _tm(request: Request) -> TaskManager:
    return request.app.state.tm


# ------------------------------------------------------------ cookies API
# Sign-in via the user's OWN browser cookies - the officially supported
# yt-dlp mechanism (--cookies / --cookies-from-browser). This is ordinary
# authentication, not a bypass of any access control.


def _cookie_status() -> dict:
    cfg = get_config()
    src = str(cfg.get("cookie_source") or "none")
    summary = cookie_store.summarize_file(cfg.cookies_path)
    return {
        "source": src,
        "browser": str(cfg.get("cookie_browser") or ""),
        "file_present": cfg.cookies_path.is_file() and summary["cookie_count"] > 0,
        "cookie_count": summary["cookie_count"],
        "domains": summary["domains"],
        "supported_browsers": list(COOKIE_BROWSERS),
    }


@router.get("/media/cookies")
async def get_cookies():
    return _cookie_status()


class CookiePrefsIn(BaseModel):
    source: str                            # none | file | browser
    browser: str = ""                      # used when source == browser
    cookies_text: str | None = None        # used when source == file
    domain: str = cookie_store.HEADER_COOKIE_DEFAULT_DOMAIN


@router.put("/media/cookies")
async def put_cookies(body: CookiePrefsIn):
    """Save cookie sign-in preferences. Cookie values are never logged."""
    cfg = get_config()
    if body.source == "none":
        cfg.set_cookie_prefs("none")
        return _cookie_status()
    if body.source == "browser":
        try:
            cfg.set_cookie_prefs("browser", body.browser)
        except ConfigError as exc:
            raise HTTPException(400, str(exc))
        return _cookie_status()
    if body.source != "file":
        raise HTTPException(400, "source must be one of: none, file, browser")

    text = body.cookies_text or ""
    if not text.strip():
        if cfg.cookies_path.is_file() and cookie_store.summarize_file(cfg.cookies_path)["cookie_count"] > 0:
            # keep the previously stored file, just activate file mode
            cfg.set_cookie_prefs("file")
            return _cookie_status()
        raise HTTPException(400,
                            "No cookies provided. Paste a cookies.txt export (from a "
                            "browser extension such as 'Get cookies.txt LOCALLY') or a "
                            "'Cookie:' header line copied from devtools while logged in.")
    try:
        content = cookie_store.parse_cookie_input(text, body.domain)
    except ValidationError as exc:
        raise HTTPException(400, str(exc))

    path = cfg.cookies_path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("cookies.txt.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass  # Windows: ACLs apply instead
    except OSError as exc:
        raise HTTPException(500, f"Could not store the cookies file: {exc}")
    cfg.set_cookie_prefs("file")
    return _cookie_status()


@router.delete("/media/cookies")
async def delete_cookies():
    """Forget stored cookies entirely (file deleted, sign-in disabled)."""
    cfg = get_config()
    try:
        if cfg.cookies_path.is_file():
            cfg.cookies_path.unlink()
        tmp = cfg.cookies_path.with_name("cookies.txt.tmp")
        if tmp.is_file():
            tmp.unlink()
    except OSError as exc:
        raise HTTPException(500, f"Could not delete the cookies file: {exc}")
    cfg.set_cookie_prefs("none")
    return _cookie_status()


@router.post("/media/cookies/test")
async def test_cookies():
    """Verify the configured sign-in by fetching a stable public video."""
    cfg = get_config()
    if not media_service.cookie_args(cfg):
        return {"ok": False, "message":
                "No cookie sign-in is configured. Choose 'Paste cookies file' or "
                "'Use browser cookies' in the Cookies / Sign-in tab first."}
    started = time.time()
    try:
        info = await media_service.fetch_info(cfg, media_service.TEST_VIDEO_URL)
    except RuntimeError as exc:
        return {"ok": False,
                "message": str(exc),
                "elapsed_s": round(time.time() - started, 1)}
    return {"ok": True,
            "message": f"Sign-in works - fetched '{info['title']}' successfully.",
            "elapsed_s": round(time.time() - started, 1)}


# ------------------------------------------------------------- info
@router.get("/media/info")
async def media_info(url: str):
    cfg = get_config()
    try:
        url = validate_media_url(url)
    except ValidationError as exc:
        raise HTTPException(400, str(exc))
    try:
        info = await media_service.fetch_info(cfg, url)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    max_hours = int(cfg.get("max_duration_hours") or 0)
    duration = info.get("duration")
    if max_hours > 0 and duration and duration > max_hours * 3600:
        raise HTTPException(400,
                            f"This video is longer than the configured maximum duration "
                            f"({max_hours} h). Adjust the limit in Settings if appropriate.")
    return info


class FormatIds(BaseModel):
    video: str = ""
    audio: str = ""


class MediaDownloadIn(BaseModel):
    url: str
    mode: str = "video"                    # video | audio
    video_format: str = "mp4"              # mp4 | best  (video mode)
    audio_format: str = "mp3"              # mp3 | m4a | best (audio mode)
    audio_quality: int | None = None       # kbps: 320/256/192/128/96/64
    height: int | None = None              # resolution cap for video mode
    prefer_h264: bool = True
    format_ids: FormatIds | None = None    # advanced: explicit ids from /media/info
    video_id: str = ""
    title: str = ""
    is_live: bool = False


@router.post("/media/download")
async def media_download(request: Request, body: MediaDownloadIn):
    cfg = get_config()
    try:
        url = validate_media_url(body.url)
    except ValidationError as exc:
        raise HTTPException(400, str(exc))
    if body.mode not in ("video", "audio"):
        raise HTTPException(400, "mode must be 'video' or 'audio'")

    vid = body.video_id if re.fullmatch(r"[A-Za-z0-9_\-\.]{1,64}", body.video_id or "") else ""
    title = re.sub(r"[\r\n\t]+", " ", (body.title or ""))[:120]

    params = {
        "url": url,
        "mode": body.mode,
        "video_format": body.video_format,
        "audio_format": body.audio_format,
        "audio_quality": body.audio_quality,
        "height": body.height,
        "prefer_h264": body.prefer_h264,
        "format_ids": body.format_ids.model_dump() if body.format_ids else None,
        "video_id": vid,
        "title": title or "media",
        "is_live": body.is_live,
        "merge": True,
    }
    tm = _tm(request)
    kind = "media_audio" if body.mode == "audio" else "media_video"
    task_id = tm.submit(kind, f"Download: {title or url[:60]}",
                        media_service.download_task_wrapper(cfg, params),
                        meta={"mode": body.mode, "video_id": vid})
    return {"task_id": task_id}
