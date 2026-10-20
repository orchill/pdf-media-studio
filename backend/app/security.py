"""Input validation and path containment helpers (security layer).

Everything the client can influence passes through here:
page selections, rotation values, output paths and media URLs.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

_RANGE_RE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


class ValidationError(ValueError):
    """Raised for any rejected user input -> HTTP 400."""


# ------------------------------------------------------------------ paths
def ensure_within(path: Path, base: Path, what: str = "path") -> Path:
    """Resolve `path` and guarantee it lives inside `base` (no traversal)."""
    base = base.resolve()
    resolved = path.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValidationError(
            f"{what} is outside the permitted directory (path traversal blocked)")
    return resolved


# ---------------------------------------------------------- page selections
def _clamp(v: int, max_page: int, what: str) -> int:
    if v < 1 or v > max_page:
        raise ValidationError(f"Page {what} {v} is out of range (document has {max_page} pages)")
    return v


def parse_pages(spec: str | list | None, max_page: int) -> list[int]:
    """Parse '1-3,5' / [1,2,3] into a sorted, de-duplicated 1-based page list."""
    if spec is None or (isinstance(spec, str) and not spec.strip()):
        return list(range(1, max_page + 1))
    tokens: list[str]
    if isinstance(spec, str):
        tokens = [t for t in re.split(r"[,\s]+", spec.strip()) if t]
    elif isinstance(spec, list):
        tokens = [str(t) for t in spec if str(t).strip()]
    else:
        raise ValidationError("Invalid page selection")
    pages: set[int] = set()
    for tok in tokens:
        m = _RANGE_RE.match(tok)
        if not m:
            raise ValidationError(f"Invalid page token: '{tok}' (expected e.g. 1-3 or 5)")
        a = _clamp(int(m.group(1)), max_page, "number")
        b = _clamp(int(m.group(2)) if m.group(2) else a, max_page, "number")
        if b < a:
            a, b = b, a
        pages.update(range(a, b + 1))
    if not pages:
        raise ValidationError("Page selection is empty")
    return sorted(pages)


def parse_page_groups(spec: str, max_page: int) -> list[tuple[int, int]]:
    """Parse '1-3,5,8-10' into ordered (start, end) groups. Empty -> error."""
    if not spec or not str(spec).strip():
        raise ValidationError("Page ranges are empty")
    groups: list[tuple[int, int]] = []
    for tok in [t for t in re.split(r"[,\s]+", str(spec).strip()) if t]:
        m = _RANGE_RE.match(tok)
        if not m:
            raise ValidationError(f"Invalid range token: '{tok}' (expected e.g. 1-3 or 5)")
        a = _clamp(int(m.group(1)), max_page, "number")
        b = _clamp(int(m.group(2)) if m.group(2) else a, max_page, "number")
        if b < a:
            a, b = b, a
        groups.append((a, b))
    if not groups:
        raise ValidationError("Page ranges are empty")
    return groups


def validate_order(order: list, max_page: int) -> list[int]:
    """Validate a full page ordering (used by the Organize tool)."""
    if not isinstance(order, list) or not order:
        raise ValidationError("Page order is empty")
    seen: set[int] = set()
    result: list[int] = []
    for item in order:
        try:
            page = int(item)
        except (TypeError, ValueError):
            raise ValidationError(f"Invalid page in order: {item!r}")
        _clamp(page, max_page, "number")
        if page in seen:
            raise ValidationError(f"Page {page} appears more than once")
        seen.add(page)
        result.append(page)
    return result


def validate_rotation(deg: int) -> int:
    if int(deg) not in (0, 90, 180, 270):
        raise ValidationError("Rotation must be one of 0, 90, 180, 270 degrees")
    return int(deg)


# ------------------------------------------------------------------ URLs
def validate_media_url(url: str) -> str:
    """Validate a media URL before handing it to yt-dlp.

    Blocks non-http(s) schemes, embedded credentials, and any host that
    resolves to loopback/private/reserved address space (SSRF protection).
    """
    url = (url or "").strip()
    if not url or len(url) > 2048:
        raise ValidationError("URL is empty or too long")
    if any(ch in url for ch in "\r\n\t"):
        raise ValidationError("URL contains invalid characters")
    try:
        parts = urlparse(url)
    except ValueError:
        raise ValidationError("URL could not be parsed")
    if parts.scheme not in ("http", "https"):
        raise ValidationError("Only http:// and https:// URLs are supported")
    if not parts.hostname:
        raise ValidationError("URL has no hostname")
    if parts.username or parts.password:
        raise ValidationError("URLs with embedded credentials are not allowed")

    host = parts.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".local", ".internal", ".lan", ".home")):
        raise ValidationError("Access to local hostnames is blocked for security reasons")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValidationError(f"Cannot resolve host '{host}' - check the URL and your connection")
    except OSError:
        raise ValidationError(f"Could not look up host '{host}'")
    if not infos:
        raise ValidationError(f"Host '{host}' has no usable addresses")
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if not ip.is_global:
            raise ValidationError(
                "Access to private/loopback network addresses is blocked for security reasons")
    return url
