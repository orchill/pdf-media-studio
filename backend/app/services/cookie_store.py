"""Cookie sign-in store for yt-dlp (fixes YouTube's "confirm you're not a bot").

This implements the *official* yt-dlp sign-in mechanism: passing cookies
from the user's OWN logged-in browser session (``--cookies`` file or
``--cookies-from-browser``). It is ordinary authentication - the same
requests the user's browser would make - not a bypass of any access
control. DRM, paywall and members-only restrictions still apply.

Accepted input formats for the paste box:
1. A Netscape ``cookies.txt`` file (exported by "Get cookies.txt LOCALLY",
   "Cookie-Editor" and similar browser extensions).
2. A raw HTTP ``Cookie:`` header line copied from browser devtools,
   e.g. ``VISITOR_INFO1_LIVE=abc; SID=g.123; ...`` (converted to the
   Netscape format for the given domain).

Security properties:
- Cookie values are never logged, echoed, or returned by the API.
- Only a masked summary (count + domain names) is exposed.
- The file lives at data_dir/cookies.txt with 0600-style permissions.
- Input size and line count are hard-capped; control characters rejected.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from ..security import ValidationError

MAX_COOKIE_BYTES = 262_144          # 256 KB is far more than any cookie file needs
MAX_COOKIES = 3_000
HEADER_COOKIE_DEFAULT_DOMAIN = ".youtube.com"

_NETSCAPE_DATA_RE = re.compile(r"^\s*#\S+")          # "#HttpOnly_ ..." lines
_DOMAIN_RE = re.compile(r"^\.?[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+)+$")
_DOMAIN_ONLY_RE = re.compile(r"^\.?[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+)*$")
_PATH_RE = re.compile(r"^/[\x20-\x7e]*$")
_COOKIE_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]{1,128}$")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _err(msg: str) -> ValidationError:
    return ValidationError(msg)


def _looks_like_netscape(text: str) -> bool:
    for line in text.splitlines():
        s = line.rstrip("\r")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if len(s.split("\t")) >= 6:
            return True
    return False


def _parse_netscape(text: str) -> list[str]:
    """Validate an already-Netscape document; return the cleaned data lines."""
    out: list[str] = []
    seen: dict[tuple[str, str, str], int] = {}
    for line in text.splitlines():
        s = line.rstrip("\r")
        if not s.strip():
            continue
        if s.lstrip().startswith("#"):
            # Keep the standard header comment, drop "#HttpOnly_" prefixed
            # real cookies only if they parse below; plain comments pass.
            if not s.lstrip().startswith("#HttpOnly_"):
                if "# Netscape" in s or "HTTP Cookie File" in s:
                    out.append(s.strip())
                continue
            s = s.lstrip()[len("#HttpOnly_"):]
        parts = s.split("\t")
        if len(parts) == 6:          # exporter omitted the empty value column
            parts.append("")
        if len(parts) != 7:
            raise _err(
                "This does not look like a valid cookies.txt file (expected "
                "7 tab-separated columns). Export cookies with a browser "
                "extension such as 'Get cookies.txt LOCALLY' and paste the "
                "whole file, or paste a Cookie header from devtools.")
        domain, _flag, path, _secure, expiry, name, value = (p.strip() for p in parts)
        if not _DOMAIN_ONLY_RE.match(domain):
            raise _err(f"Invalid cookie domain: '{domain[:60]}'")
        if not _PATH_RE.match(path or "/"):
            raise _err(f"Invalid cookie path: '{path[:60]}'")
        try:
            int(expiry or "0")
        except ValueError:
            raise _err(f"Invalid cookie expiry for '{name[:40]}' (must be an integer)")
        if not name or not _COOKIE_NAME_RE.match(name):
            raise _err(f"Invalid cookie name: '{name[:40]}'")
        if _CTRL_RE.search(value or "") or "\t" in value:
            raise _err(f"Cookie value for '{name[:40]}' contains forbidden characters")
        key = (domain, path or "/", name)
        seen[key] = len(out)
        secure = "TRUE" if _secure.upper() in ("TRUE", "1") else "FALSE"
        # The stdlib loader asserts flag == domain.startswith('.'); enforce it.
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        out.append("\t".join((domain, flag, path or "/", secure,
                              expiry or "0", name, value or "")))
        if len(out) > MAX_COOKIES:
            raise _err(f"Cookie file exceeds the {MAX_COOKIES}-cookie limit")
    if not out:
        raise _err("No cookies were found in the pasted text")
    # Re-apply dedupe (last occurrence wins, like yt-dlp's loader)
    final: list[str] = []
    for i, line in enumerate(out):
        if not line.startswith("#") and seen.get((line.split("\t")[0], line.split("\t")[2], line.split("\t")[5])) == i:
            final.append(line)
    return final


def _parse_header_line(text: str, domain: str) -> list[str]:
    """Convert a raw ``Cookie:`` header line into Netscape-format entries."""
    if "\n" in text.strip() and _looks_like_netscape(text):
        return _parse_netscape(text)
    pairs = [p.strip() for p in text.strip().split(";") if p.strip()]
    if not pairs:
        raise _err("Cookie text is empty")
    expiry = str(int(time.time()) + 2 * 365 * 24 * 3600)
    out: list[str] = []
    index_by_name: dict[str, int] = {}
    for pair in pairs:
        if "=" not in pair:
            raise _err(
                f"'{pair[:40]}' is not a NAME=VALUE pair. Paste the full "
                "'Cookie:' header line (NAME=value; NAME2=value2; ...) or a "
                "cookies.txt export.")
        name, _, value = pair.partition("=")
        name, value = name.strip(), value.strip().strip('"')
        if not name or not _COOKIE_NAME_RE.match(name):
            raise _err(f"Invalid cookie name: '{name[:40]}'")
        if _CTRL_RE.search(value):
            raise _err(f"Cookie value for '{name[:40]}' contains forbidden characters")
        line = f"{domain}\tTRUE\t/\tTRUE\t{expiry}\t{name}\t{value}"
        if name in index_by_name:               # duplicate name -> last wins
            out[index_by_name[name]] = line
        else:
            index_by_name[name] = len(out)
            out.append(line)
        if len(out) > MAX_COOKIES:
            raise _err(f"Cookie header exceeds the {MAX_COOKIES}-cookie limit")
    return out


def parse_cookie_input(text: str, domain: str = HEADER_COOKIE_DEFAULT_DOMAIN) -> str:
    """Validate pasted cookies and return a normalized Netscape cookies.txt.

    Raises ValidationError with an actionable message on any problem.
    """
    text = (text or "").strip()
    if not text:
        raise _err("Cookie text is empty - paste a cookies.txt export or a "
                   "'Cookie:' header line")
    if len(text.encode("utf-8", "replace")) > MAX_COOKIE_BYTES:
        raise _err("Cookie text is too large (limit 256 KB) - paste only the "
                   "cookies file, not a web page")
    domain = (domain or HEADER_COOKIE_DEFAULT_DOMAIN).strip().rstrip(".")
    if not _DOMAIN_ONLY_RE.match(domain):
        raise _err(f"Invalid cookie domain: '{domain[:60]}' (use e.g. .youtube.com)")
    if not domain.startswith("."):
        domain = "." + domain
    if _looks_like_netscape(text):
        lines = _parse_netscape(text)
    else:
        lines = _parse_header_line(text, domain)
    if not lines:
        raise _err("No usable cookies were found in the pasted text")
    # NOTE: the first line must be EXACTLY this string - the stdlib cookie
    # loader rejects the file otherwise.
    header = ("# Netscape HTTP Cookie File\n"
              "# Generated by PDF & Media Studio - stored locally for yt-dlp sign-in.\n")
    return header + "\n".join(lines) + "\n"


def summarize_file(path: Path) -> dict:
    """Masked summary of a stored cookies.txt (count + domains, NO values)."""
    result = {"cookie_count": 0, "domains": []}
    if not path.is_file():
        return result
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
    domains: list[str] = []
    count = 0
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            count += 1
            if parts[0] not in domains:
                domains.append(parts[0])
    result["cookie_count"] = count
    result["domains"] = domains[:20]
    return result
