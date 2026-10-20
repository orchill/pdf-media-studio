"""Cookie sign-in tests: parsing, storage API, and real transmission to a
local HTTP server (proves cookies are actually sent by yt-dlp)."""
from __future__ import annotations

import functools
import http.server
import math
import pathlib
import socket
import struct
import tempfile
import threading
import wave

import pytest

from backend.app.config import Config, COOKIE_BROWSERS
from backend.app.security import ValidationError
from backend.app.services import cookie_store, media_service

TMP = pathlib.Path(tempfile.mkdtemp(prefix="pms_cookies_"))

HEADER_COOKIES = ("VISITOR_INFO1_LIVE=abc123; SID=g.000test; "
                  "HSID=secret1; SSID=secret2; SAPISID=tok1; SIDCC=tok2")


def _test_cfg(name: str) -> Config:
    d = TMP / name
    d.mkdir(exist_ok=True)
    f = d / "config.json"
    f.write_text('{"output_dir": "%s", "data_dir": "%s"}'
                 % (d / "out", d / "data"), encoding="utf-8")
    return Config(f)


# ----------------------------------------------------------- parsing units
def test_header_format_converted_to_netscape():
    out = cookie_store.parse_cookie_input(HEADER_COOKIES)
    lines = [ln for ln in out.splitlines() if ln and not ln.startswith("#")]
    assert len(lines) == 6
    for ln in lines:
        parts = ln.split("\t")
        assert len(parts) == 7
        assert parts[0] == ".youtube.com"          # default domain
        assert parts[2] == "/"
        assert parts[3] == "TRUE"
    names = [ln.split("\t")[5] for ln in lines]
    assert "SID" in names and "SAPISID" in names
    # values survive intact
    sid = [ln for ln in lines if ln.split("\t")[5] == "SID"][0]
    assert sid.split("\t")[6] == "g.000test"


def test_netscape_passthrough_and_dedupe():
    raw = ("# Netscape HTTP Cookie File\n"
           ".youtube.com\tTRUE\t/\tTRUE\t1900000000\tONE\tfirst\n"
           ".youtube.com\tTRUE\t/\tTRUE\t1900000000\tONE\tsecond\n"
           ".youtube.com\tTRUE\t/\tTRUE\t1900000000\tTWO\tv2\n")
    out = cookie_store.parse_cookie_input(raw)
    data = [ln for ln in out.splitlines() if ln and not ln.startswith("#")]
    assert len(data) == 2                          # ONE deduped (last wins)
    one = [ln for ln in data if "\tONE\t" in ln][0]
    assert one.endswith("\tsecond")


def test_httponly_prefixed_lines_accepted():
    raw = ("#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1900000000\tHSID\tval1\n"
           ".youtube.com\tTRUE\t/\tTRUE\t1900000000\tSSID\tval2\n")
    out = cookie_store.parse_cookie_input(raw)
    data = [ln for ln in out.splitlines() if ln and not ln.startswith("#")]
    assert len(data) == 2
    assert data[0].split("\t")[5] == "HSID"


def test_empty_and_garbage_inputs_rejected():
    with pytest.raises(ValidationError):
        cookie_store.parse_cookie_input("")
    with pytest.raises(ValidationError):
        cookie_store.parse_cookie_input("   \n  ")
    with pytest.raises(ValidationError) as e:
        cookie_store.parse_cookie_input("just some random words")
    assert "NAME=VALUE" in str(e.value)
    with pytest.raises(ValidationError):
        cookie_store.parse_cookie_input("A=1; bad pair without equals")
    with pytest.raises(ValidationError) as e:
        cookie_store.parse_cookie_input(HEADER_COOKIES, domain="not a domain!")
    assert "domain" in str(e.value).lower()


def test_control_characters_rejected_and_size_cap():
    with pytest.raises(ValidationError):
        cookie_store.parse_cookie_input("A=x\x01y")
    with pytest.raises(ValidationError) as e:
        cookie_store.parse_cookie_input("A=" + "x" * (cookie_store.MAX_COOKIE_BYTES + 10))
    assert "too large" in str(e.value)


def test_custom_domain_for_header_cookies():
    out = cookie_store.parse_cookie_input("K=v", domain="example.org")
    line = [ln for ln in out.splitlines() if ln and not ln.startswith("#")][0]
    assert line.startswith(".example.org\t")


def test_summarize_file_masks_values(tmp_path: pathlib.Path):
    p = tmp_path / "cookies.txt"
    p.write_text(cookie_store.parse_cookie_input(HEADER_COOKIES), encoding="utf-8")
    s = cookie_store.summarize_file(p)
    assert s["cookie_count"] == 6
    assert s["domains"] == [".youtube.com"]
    raw = repr(s)
    assert "secret" not in raw and "abc123" not in raw      # values never leak


# --------------------------------------------------------- cookie_args unit
def test_cookie_args_none_and_browser():
    cfg = _test_cfg("args_none")
    assert media_service.cookie_args(cfg) == []
    cfg.set_cookie_prefs("browser", "firefox")
    assert media_service.cookie_args(cfg) == ["--cookies-from-browser", "firefox"]
    with pytest.raises(Exception):
        cfg.set_cookie_prefs("browser", "netscape-navigator")   # unsupported


def test_cookie_args_file_requires_existing_file():
    cfg = _test_cfg("args_file")
    cfg.cookies_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.set_cookie_prefs("file")
    assert media_service.cookie_args(cfg) == []            # no file yet
    cfg.cookies_path.write_text("x\tTRUE\t/\tTRUE\t0\tn\tv\n", encoding="utf-8")
    args = media_service.cookie_args(cfg)
    assert args == ["--cookies", str(cfg.cookies_path)]


def test_friendly_bot_message_varies_with_cookie_state():
    cfg = _test_cfg("friendly")
    cfg.cookies_path.parent.mkdir(parents=True, exist_ok=True)
    tail = "ERROR: Sign in to confirm you're not a bot. This helps protect our community."
    msg = media_service._friendly(cfg, tail)
    assert "bot verification" in msg.lower()
    # with cookies configured, the message says cookies did not satisfy the check
    cfg.cookies_path.write_text("x\tTRUE\t/\tTRUE\t0\tn\tv\n", encoding="utf-8")
    cfg.set_cookie_prefs("file")
    msg2 = media_service._friendly(cfg, tail)
    assert "re-export fresh cookies" in msg2


# ------------------------------------------------------------------ API
def _reset(client):
    client.delete("/api/media/cookies")


def test_cookies_api_roundtrip(client):
    _reset(client)
    # default state
    r = client.get("/api/media/cookies")
    assert r.status_code == 200
    assert r.json()["source"] == "none"
    assert set(r.json()["supported_browsers"]) == set(COOKIE_BROWSERS)

    # save header-style cookies
    r = client.put("/api/media/cookies", json={"source": "file",
                                               "cookies_text": HEADER_COOKIES})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "file" and body["file_present"] is True
    assert body["cookie_count"] == 6
    assert body["domains"] == [".youtube.com"]

    # no cookie values anywhere in the response
    assert "g.000test" not in r.text and "secret1" not in r.text

    # stored on disk in the app data dir
    from backend.app.config import get_config
    assert get_config().cookies_path.is_file()
    stored = get_config().cookies_path.read_text(encoding="utf-8")
    assert "g.000test" in stored and "secret1" in stored

    # config exposes only the source, not any values
    assert client.get("/api/settings").json()["cookie_source"] == "file"

    # generic settings PATCH must NOT be able to change cookie prefs
    r = client.put("/api/settings", json={"patch": {"cookie_source": "browser"}})
    assert r.status_code == 400

    # re-saving with empty text keeps the existing file (source re-activation)
    r = client.put("/api/media/cookies", json={"source": "file", "cookies_text": ""})
    assert r.status_code == 200 and r.json()["file_present"] is True

    # switch to browser mode then back to none
    r = client.put("/api/media/cookies", json={"source": "browser", "browser": "edge"})
    assert r.status_code == 200 and r.json()["source"] == "browser"
    r = client.put("/api/media/cookies", json={"source": "none"})
    assert r.status_code == 200 and r.json()["source"] == "none"

    # clear wipes the file
    client.put("/api/media/cookies", json={"source": "file",
                                           "cookies_text": HEADER_COOKIES})
    r = client.delete("/api/media/cookies")
    assert r.status_code == 200
    assert r.json()["source"] == "none" and r.json()["file_present"] is False
    from backend.app.config import get_config as g
    assert not g().cookies_path.exists()
    _reset(client)


def test_cookies_api_validation_errors(client):
    _reset(client)
    r = client.put("/api/media/cookies", json={"source": "file", "cookies_text": ""})
    assert r.status_code == 400                       # nothing stored yet
    assert "cookies.txt" in r.json()["detail"]

    r = client.put("/api/media/cookies", json={"source": "browser", "browser": "netscape"})
    assert r.status_code == 400

    r = client.put("/api/media/cookies", json={"source": "telegram"})
    assert r.status_code == 400

    r = client.put("/api/media/cookies", json={"source": "file",
                                               "cookies_text": "garbage line without structure"})
    assert r.status_code == 400

    r = client.put("/api/media/cookies",
                   json={"source": "file", "cookies_text": "A=" + "x" * 300_000})
    assert r.status_code == 400

    # test endpoint reports unconfigured state
    r = client.post("/api/media/cookies/test")
    assert r.status_code == 200 and r.json()["ok"] is False
    _reset(client)


# ------------------------------------------- end-to-end cookie transmission
def _make_wav(path: pathlib.Path) -> None:
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(
            struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / 8000)))
            for i in range(16000)))


class _RecordingHandler(http.server.SimpleHTTPRequestHandler):
    cookie_headers: list[str] = []

    def do_GET(self):
        c = self.headers.get("Cookie")
        if c:
            _RecordingHandler.cookie_headers.append(c)
        super().do_GET()

    def log_message(self, *a):   # silence
        pass


def test_cookies_actually_sent_to_site():
    """Full pipeline proof: yt-dlp transmits the stored cookies (local server)."""
    cfg = _test_cfg("e2e")
    www = TMP / "e2e_www"
    www.mkdir(exist_ok=True)
    wav = www / "tone.wav"
    if not wav.exists():
        _make_wav(wav)

    # cookies.txt with an exact-host cookie for the local test server
    port = _free_port()
    cfg.cookies_path.parent.mkdir(parents=True, exist_ok=True)
    netscape = ("# Netscape HTTP Cookie File\n"
                "127.0.0.1\tFALSE\t/\tFALSE\t1900000000\tPMS_TEST_COOKIE\thello123\n")
    cfg.cookies_path.write_text(netscape, encoding="utf-8")
    cfg.set_cookie_prefs("file")
    assert media_service.cookie_args(cfg) == ["--cookies", str(cfg.cookies_path)]

    handler = functools.partial(_RecordingHandler, directory=str(www))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        import asyncio
        info = asyncio.run(media_service.fetch_info(
            cfg, f"http://127.0.0.1:{port}/tone.wav"))
        assert info["title"]
    finally:
        httpd.shutdown()
    assert _RecordingHandler.cookie_headers, "yt-dlp sent no Cookie header"
    assert any("PMS_TEST_COOKIE=hello123" in c for c in _RecordingHandler.cookie_headers)
    cfg.set_cookie_prefs("none")
    _RecordingHandler.cookie_headers.clear()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
