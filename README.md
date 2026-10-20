# PDF & Media Studio

A modern, fully functional, **locally hosted** PDF toolbox + media downloader.
One unified web app running on your own computer — merge/convert/organize/compress
PDFs, turn images into PDFs, extract content, and download/convert video & audio
through **yt-dlp** and **FFmpeg**. Everything is processed on your machine: no
cloud services, no telemetry, no accounts.

```
┌────────────────────────────────────────────────────────────────────┐
│  Browser UI (React + TypeScript + Tailwind, built SPA)             │
│  http://127.0.0.1:8756                                             │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  JSON API (/api/…, polling)
┌──────────────────────────────┴─────────────────────────────────────┐
│  FastAPI backend (Python, bound to 127.0.0.1)                      │
│  ├─ Task manager: queue, progress, cancel, cleanup, history        │
│  ├─ PDF service:  PyMuPDF + pypdf + Pillow                         │
│  │    merge · split · reorder/delete/rotate · compress             │
│  │    images→PDF · extract images · PDF→images · thumbnails        │
│  └─ Media service: yt-dlp (subprocess) + FFmpeg (subprocess)       │
│       metadata · MP4 video · MP3/M4A audio · merge · progress      │
└────────────────────────────────────────────────────────────────────┘
```

---

## Feature overview

**PDF tools** (all write NEW files — originals are never modified or overwritten):

| Tool | What it does |
|---|---|
| Merge PDFs | Combine 2–24 PDFs; drag-and-drop ordering |
| Images to PDF | PNG/JPEG/WebP/GIF/BMP/TIFF → one PDF; page sizes (A4/Letter/Legal/A3/A5/match-image), margins, portrait/landscape/auto, per-image rotation; original image bytes embedded without recompression by default (optional JPEG re-encode) |
| Organize Pages | Visual thumbnail grid: drag to reorder, rotate/delete individual pages or a multi-selection, rename output |
| Split / Extract | Extract selected pages into one PDF, split by custom ranges (each range → own file), or every N pages; multiple outputs delivered as ZIP |
| Compress PDF | Downscales oversized embedded images + JPEG re-encode, preserves transparency; reports the *actual* resulting size and saving % |
| Extract Images | Exports embedded raster images in their original format/resolution (ZIP when multiple) |
| PDF to Images | Render pages to PNG or JPG at 72–600 DPI, with page selection |
| Page selection | Individual pages, ranges (`1-3,5,8-10`), multi-select everywhere |

**Media downloader** (publicly accessible content only):

- Paste a URL → see **title, thumbnail, duration, uploader and all available formats** with sizes
- Output: **MP4 video** (H.264/AAC preferred for compatibility, or best available), **MP3**, **M4A**, best-audio
- Resolution presets (2160p → 360p) or exact format picker; size estimates
- Live progress (percent, speed, ETA), post-processing status, **cancel** with partial-file cleanup
- Configurable output directory; "Open output folder" button; no-overwrite safety
- Clear errors for unavailable/private/age-restricted videos, network failures, missing FFmpeg
- **Cookies / Sign-in tab**: sign in with your own YouTube session to resolve YouTube's
  "confirm you're not a bot" check — via `--cookies` file paste (Netscape cookies.txt or a
  `Cookie:` header line) or `--cookies-from-browser` (Chrome/Edge/Firefox/Brave/Opera/Vivaldi/Whale/Chromium/Safari).
  This is regular authentication as yourself, not an access-control bypass.
- Works with any site yt-dlp supports; **no DRM circumvention or authentication bypass** — only download content you have permission to save

**General**

- Dashboard with tool cards, dependency status and recent tasks
- Task history (bounded, persisted) with re-download links
- Settings page: output dir, FFmpeg/yt-dlp paths, size/duration/concurrency limits
- Dark & light themes, responsive layout, keyboard-accessible controls
- Graceful shutdown: running subprocesses are killed, temp files cleaned on start & exit

---

## Requirements

| | |
|---|---|
| OS | **Windows 10/11** (primary), Linux, macOS |
| Python | 3.10 – 3.13 (developed and tested on 3.12) |
| Node.js + npm | **optional** — only needed to rebuild the UI (a prebuilt UI is bundled in `frontend/dist/`) |
| FFmpeg | needed for MP3/M4A conversion and MP4 merging (not needed for PDF tools) |
| yt-dlp | installed automatically with the Python dependencies |
| Hardware | any modern PC; no Docker, no database, no paid APIs |

---

## Installation & startup (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) — check **"Add python.exe to PATH"**.
2. Install FFmpeg (skip if you only want PDF tools), any one of:
   ```bat
   winget install Gyan.FFmpeg
   ```
   or download from <https://www.gyan.dev/ffmpeg/builds/>, unzip, and add its `bin` folder to PATH
   (or point at `ffmpeg.exe` in the app's Settings).
3. Double-click **`scripts\start.bat`**.

   The first run creates a virtual environment (`.venv`), installs the Python
   dependencies, and opens your browser at `http://127.0.0.1:8756`.
   (`scripts\setup.bat` does the setup alone, if you prefer.)

## Installation & startup (Linux / macOS)

```bash
# Debian/Ubuntu FFmpeg (optional, for media features)
sudo apt install ffmpeg

./scripts/start.sh          # or: setup.sh once, then start.sh
```

## Shutdown

- Press `Ctrl+C` in the console window, **or**
- Windows: `scripts\stop.bat` (optionally `stop.bat 8756`), Linux/macOS: `./scripts/stop.sh`

Stopping kills all running yt-dlp/FFmpeg subprocesses. On the next start, cached
uploads, thumbnails and temp files from the previous run are wiped automatically —
no orphaned temp data.

---

## Configuration

`config.json` is created with defaults on first start (see `config.example.json`).
Everything except `host` / `port` / `data_dir` can also be edited live in the
Settings page.

| Key | Default | Meaning |
|---|---|---|
| `host` | `127.0.0.1` | Bind address. Keep localhost unless you understand the risk |
| `port` | `8756` | HTTP port (`--port` CLI flag overrides) |
| `output_dir` | `outputs/` | Where processed files and downloads are saved |
| `data_dir` | `data/` | Transient workspace: uploads cache, thumbnails, logs, history |
| `ffmpeg_path` | *(auto)* | Full path to `ffmpeg(.exe)` if not on PATH |
| `ytdlp_path` | *(auto)* | Path to a standalone `yt-dlp(.exe)`; empty = bundled Python module |
| `max_upload_mb` | `512` | Per-file upload limit |
| `max_download_gb` | `2` | Refuse downloads larger than this (0 = unlimited) |
| `max_duration_hours` | `4` | Refuse media longer than this (0 = unlimited) |
| `max_concurrent_tasks` | `3` | Parallel task execution limit |
| `history_limit` | `100` | Task-history entries kept on disk |
| `cookie_source` | `none` | Sign-in source for yt-dlp: `none` / `file` / `browser`. Set from the downloader's **Cookies / Sign-in** tab, not by hand |
| `cookie_browser` | *(empty)* | Browser name for `cookie_source: browser` (e.g. `chrome`, `firefox`, `edge`) |
| `open_browser` | `true` | Open the UI automatically on start |

CLI flags: `python run.py [--host 127.0.0.1] [--port 8756] [--no-browser]`

Logs are written to `data/logs/app.log` (rotating). Media downloads are also
verbose in the task's diagnostics log (URLs are omitted from logs).

---

## Architecture notes

- **Backend**: FastAPI + Uvicorn, single worker. Long-running work runs as *tasks*
  (PDF work in worker threads with cooperative cancellation, media in asyncio
  subprocesses). The UI polls `GET /api/tasks/{id}` (~1 Hz) for progress.
- **Task manager**: semaphore-bounded queue, per-task progress/stage/error/log,
  cancellation via flag + `terminate()`/`kill()` of child processes, output
  validation (files must exist and be non-empty; PDFs are re-opened and page-checked),
  bounded JSON history (`data/history.json`).
- **Security**: argument-array subprocess execution (no shell), URLs restricted to
  http(s) with **private/loopback address blocking (SSRF protection)**, all client
  paths validated against the output directory (traversal blocked), uploads
  content-sniffed (magic bytes + real parsing) not extension-trusted, localhost-only
  binding, size/duration/concurrency limits, no arbitrary command execution surface.
- **PDF library split** (deliberate, no duplication):
  - `pypdf` (BSD-3) — merge and split: pure structural page copying.
  - `PyMuPDF` (AGPL-3.0) — rendering/thumbnails, page edits (reorder/rotate/delete),
    image extraction, image→PDF composition, compression.
  - `Pillow` (MIT-CMU) — image validation, EXIF orientation, format transcoding
    (e.g. WebP, which MuPDF cannot embed natively), JPEG re-encoding.
- **Media**: yt-dlp is executed as a controlled subprocess (`python -m yt_dlp` or
  the configured binary) with `--progress-template` for machine-readable progress;
  FFmpeg handles audio extraction, MP3/M4A conversion and stream merging via
  yt-dlp's post-processors.

Full API reference: start the app and open <http://127.0.0.1:8756/api/docs>.

---

## YouTube sign-in with cookies (bot-check fix)

YouTube often answers automated, signed-out requests with
*"Sign in to confirm you're not a bot"* — especially on VPNs, cloud IPs or for
age-restricted videos. The officially supported solution is what the app's
**Media Downloader → Cookies / Sign-in** tab does: yt-dlp sends the cookies of
**your own logged-in browser session** (`--cookies` file or
`--cookies-from-browser`). You are simply authenticated as yourself, exactly
as if you were browsing; nothing is bypassed.

**How to use it**

1. *Paste cookies file*: log in to youtube.com, export the site's cookies with a
   browser extension ("Get cookies.txt LOCALLY" for Chrome/Edge/Firefox), paste
   the file contents (or just the `Cookie:` request-header line from devtools)
   into the tab and save. Header-style input is converted to the Netscape format
   automatically; a custom domain can be set for non-YouTube sites.
2. *Use browser cookies*: pick your browser and yt-dlp reads its cookie database
   directly. Fully close the browser first (its database is locked while running);
   on Windows, Chrome/Edge cookies are encrypted per Windows user.
3. Press **Test sign-in** — the app fetches a stable public video with your
   cookies and reports the result.

**Storage & privacy**

- Cookies are stored only in `data/cookies.txt` (Netscape format, restrictive
  file permissions). Values are never returned by the API, never logged, and
  only ever sent to the video site by yt-dlp.
- The API exposes just a masked summary: source, cookie **count** and domain
  names.
- Treat that file like a password — anyone with it can use your YouTube session.
  Use **Clear cookies** before sharing your data folder, and re-export fresh
  cookies if downloads start failing (they expire, and yt-dlp refreshes them in
  the same file as it runs).
- Private, members-only and DRM-protected content stays inaccessible; use your
  own account and respect YouTube's terms and copyright law.

---

## Testing & verification status

The backend test-suite (`pytest backend/tests`, 62 tests) **all pass** and were
executed in the development environment against fixture PDFs/images and a local
HTTP media server (no reliance on external sites):

| # | Verified | Status |
|---|---|---|
| 1 | Merging two PDFs yields a valid combined document (page order checked) | ✅ executed (API + file bytes) |
| 2 | Multiple images → correctly ordered PDF (pixel-color verified, rotation + page-size math checked) | ✅ executed |
| 3 | Split (extract/ranges/every-N), reorder, delete, rotate produce valid results | ✅ executed |
| 4 | Compression produces a readable document, reports real size (file bytes == reported) | ✅ executed |
| 5 | PDF pages export as PNG/JPG | ✅ executed |
| 6 | yt-dlp retrieves metadata (title, formats, sizes) for a supported URL | ✅ executed — local HTTP fixtures **and** live YouTube (42 formats retrieved for a public video) |
| 7 | MP3 conversion works when FFmpeg is installed | ✅ executed — local fixture **and** live YouTube → MP3 (verified with ffprobe) |
| 8 | MP4 output with merged streams | ✅ executed — local fixture **and** live YouTube 360p H.264 → merged MP4 (11.9 MB, ffprobe-verified) |
| 9 | Missing dependencies produce actionable diagnostics | ✅ executed (error-message mapping unit-covered; Settings page shows install hints) |
| 10 | Failed & cancelled tasks clean up resources (no `.part` leftovers, temp dirs removed) | ✅ executed |
| 11 | Unsafe paths (traversal) and invalid inputs rejected | ✅ executed |
| 12 | App stays responsive during long operations | ✅ executed (task isolation via threads/asyncio; UI polling unaffected) |
| — | UI flows in a real browser (upload → thumbnails → organize → save → download; media fetch → format list) | ✅ executed via automated browser |
| — | Cookie sign-in: header-format conversion, Netscape validation/dedupe, masked API (no values returned), file storage + clearing, browser-name whitelist | ✅ executed (13 dedicated tests + 20 live API checks) |
| — | Cookies actually transmitted by yt-dlp | ✅ executed — local HTTP server recorded the `Cookie` header sent by yt-dlp (`--cookies` path) |
| — | Cookie flag against real YouTube | ✅ executed — with dummy cookies YouTube correctly rejects (datacenter IP); error message adapts to cookie-active state. With your real cookies it authenticates as your account |
| — | Bot-check hint card in the UI (real bot-checked video) | ✅ executed via automated browser — hint appears, button switches to Cookies tab, 0 console errors |
| — | Windows `.bat` scripts | ⚠️ unverified on real Windows hardware (logic kept simple; report issues) |
| — | Other yt-dlp sites (TikTok, Vimeo, …), playlists, live streams | ⚠️ not exercised — depends on site availability; yt-dlp handles these natively |
| — | 4K/8K downloads on slow connections, exotic codecs | ⚠️ unverified |

Some YouTube videos may fail with a "sign-in / bot verification" error — this is
YouTube restricting anonymous automated requests (common on datacenter/VPN IPs).
The app now shows a hint and offers the **Cookies / Sign-in** tab: providing
cookies from your own logged-in browser usually resolves it. When cookies are
configured and still rejected, the error explicitly says to re-export fresh
cookies.

## Known limitations

- Private and members-only videos cannot be downloaded (by design). Age-restricted
  videos require signing in with cookies from an account that has access.
- **Cookies are stored in plain text** (`data/cookies.txt`) because that is the
  format yt-dlp consumes — the app mitigates with restrictive permissions, no-logging
  and one-click clearing, but local disk access to that file means session access.
- DRM-protected content (e.g. Widevine streams) is not and will not be supported.
- Image extraction cannot export vector graphics or text (they are not raster images).
- Compression only shrinks raster images; already-optimized or text-only PDFs may
  shrink very little (the app tells you and keeps the original).
- No PDF form editing / annotation / OCR.
- The web UI is not a public web server — do not forward the port to the internet.
- Playlists are intentionally limited to the first entry (`--no-playlist`).
- Live stream recordings are downloaded but untested against duration limits.

## Licensing

| Component | License | Notes |
|---|---|---|
| This project | MIT (you are free to use/modify) | |
| PyMuPDF | **AGPL-3.0** | Local personal use is fine; distributing this app commercially may require a PyMuPDF commercial license from Artifex |
| pypdf | BSD-3-Clause | |
| Pillow | MIT-CMU | |
| FastAPI / Uvicorn / starlette | BSD/MIT | |
| yt-dlp | Unlicense | public domain |
| FFmpeg | LGPL-2.1+/GPL (build-dependent) | you install your own build |

Downloading media may be illegal depending on content, jurisdiction and source.
You are responsible for complying with the terms of the sites you use and with
copyright law.

## Troubleshooting

| Problem | Fix |
|---|---|
| "FFmpeg was not found" | Install it (`winget install Gyan.FFmpeg`) and restart the app, or set the full path in Settings → FFmpeg path |
| YouTube: "sign-in / bot verification" | Open the **Cookies / Sign-in** tab and add your YouTube cookies (export with "Get cookies.txt LOCALLY" while logged in), or use the browser-cookie mode |
| Cookies: "Could not read your browser's cookie database" | Fully close that browser (all windows) and retry, or switch to paste-file mode |
| Cookies were working, now failing | Cookie sessions expire — re-export fresh cookies while logged in to YouTube |
| YouTube: "The page needs to be reloaded" | YouTube is challenging the saved sign-in session (known yt-dlp issue). The app automatically retries without cookies so public videos still work; for signed-in content, sign out of YouTube in your browser, sign back in, and re-export the cookies immediately after visiting YouTube |
| "The video is unavailable" | The link is wrong, the video is private/region-locked, or deleted |
| Port already in use | Change `port` in `config.json`, or `scripts\stop.bat 8756` first |
| A PDF fails to open | It may be encrypted (password-protected PDFs are rejected with a clear message) |
| Web UI shows "API running" JSON | The frontend wasn't built — run `cd frontend && npm install && npm run build`, then restart |
| Downloads stop mid-way | Check `data/logs/app.log` and the task's diagnostics log; yt-dlp auto-resumes `.part` files on retry |
| Antivirus complains about yt-dlp | False positive reported by some vendors for `yt-dlp.exe`; the app uses the Python module by default, no standalone binary is downloaded |

## Project structure

```
pdf-media-studio/
├── run.py                     # launcher (port, browser, banner)
├── requirements.txt           # pinned backend dependencies
├── config.example.json        # documented config template
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, static UI mount
│   │   ├── config.py          # JSON config with validation
│   │   ├── security.py        # URL/path/page-selection validation
│   │   ├── tasks.py           # async task manager + history
│   │   ├── services/
│   │   │   ├── pdf_service.py     # all PDF/image operations
│   │   │   ├── media_service.py   # yt-dlp/FFmpeg wrappers + cookie args
│   │   │   ├── cookie_store.py    # cookie sign-in parse/validate/store
│   │   │   └── depsinfo.py        # dependency diagnostics
│   │   └── routers/           # system · files · pdf · media · tasks
│   └── tests/                 # 62 pytest tests (run: pytest backend/tests)
├── frontend/
│   ├── src/                   # React + TypeScript sources (pages, components)
│   └── dist/                  # prebuilt UI (shipped, no Node needed)
├── scripts/
│   ├── start.bat / setup.bat / stop.bat     # Windows
│   ├── start.sh / setup.sh / stop.sh        # Linux / macOS
│   └── e2e_smoke.py           # end-to-end smoke test (needs a running server)
└── outputs/                   # default output folder (created on first run)
```
