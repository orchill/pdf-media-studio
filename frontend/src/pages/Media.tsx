import { useEffect, useState } from "react";
import {
  AlertTriangle, Cookie, Download, KeyRound, Link2, Loader2, Music,
  RefreshCw, Video,
} from "lucide-react";
import TaskPanel from "../components/TaskPanel";
import CookiesPanel from "../components/CookiesPanel";
import { getCookieStatus, mediaDownload, mediaInfo } from "../api";
import { useToast } from "../ctx";
import {
  CookieStatus, MediaFormat, MediaInfo, humanSize, fmtDuration,
} from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, INPUT, LABEL, SECTION_TITLE } from "../ui";

const HEIGHTS: [number, string][] = [
  [0, "Best available"],
  [2160, "2160p (4K)"], [1440, "1440p"], [1080, "1080p"],
  [720, "720p"], [480, "480p"], [360, "360p"],
];

function formatSize(f: MediaFormat | null | undefined): number | null {
  return f?.filesize ?? f?.filesize_approx ?? null;
}

export default function Media() {
  const [tab, setTab] = useState<"downloader" | "cookies">("downloader");
  const [cookieStatus, setCookieStatus] = useState<CookieStatus | null>(null);
  const [needCookies, setNeedCookies] = useState(false);
  const [url, setUrl] = useState("");
  const [info, setInfo] = useState<MediaInfo | null>(null);
  const [fetching, setFetching] = useState(false);
  const [mode, setMode] = useState<"video" | "audio">("video");
  const [height, setHeight] = useState(0);
  const [preferH264, setPreferH264] = useState(true);
  const [videoFmt, setVideoFmt] = useState("");   // advanced: explicit format id
  const [audioFmt, setAudioFmt] = useState("mp3");
  const [audioKbps, setAudioKbps] = useState<number | null>(192);
  const [starting, setStarting] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();

  const refreshCookies = (): Promise<CookieStatus> =>
    getCookieStatus().then((s) => {
      setCookieStatus(s);
      return s;
    });
  useEffect(() => { refreshCookies().catch(() => {}); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchInfo = async () => {
    if (!url.trim()) { toast.push("error", "Paste a video URL first."); return; }
    setFetching(true);
    setInfo(null);
    setTaskId(null);
    setNeedCookies(false);
    try {
      const data = await mediaInfo(url.trim());
      setInfo(data);
      toast.push("success", `Found: ${data.title}`);
    } catch (e: any) {
      toast.push("error", e.message);
      if (/sign-in|bot|age|cookies/i.test(String(e.message || ""))) setNeedCookies(true);
    } finally {
      setFetching(false);
    }
  };

  const start = async () => {
    if (!info) return;
    setStarting(true);
    try {
      const { task_id } = await mediaDownload({
        url: info.webpage_url || url,
        mode,
        video_format: "mp4",
        audio_format: audioFmt,
        audio_quality: mode === "audio" && audioFmt !== "best" ? audioKbps : null,
        height: height || null,
        prefer_h264: preferH264,
        format_ids: videoFmt ? { video: videoFmt, audio: "" } : null,
        video_id: info.id,
        title: info.title,
        is_live: info.is_live,
      });
      setTaskId(task_id);
      toast.push("info", "Download started.");
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setStarting(false);
    }
  };

  const bestAudio = info?.audio_formats?.[0];
  const selectedVideo = videoFmt
    ? info?.video_formats.find((f) => f.id === videoFmt)
    : null;
  const estSize =
    mode === "audio"
      ? audioFmt === "best" ? formatSize(bestAudio) : null
      : formatSize(selectedVideo);

  return (
    <div className="space-y-4">
      <div>
        <h2 className={SECTION_TITLE}>Media Downloader</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Powered by yt-dlp + FFmpeg running locally. Paste a supported URL (YouTube and hundreds
          of other sites). Only download content you have the right to save - DRM and access
          controls are never bypassed. Hitting a bot check? Use the
          <button onClick={() => setTab("cookies")} className="mx-1 font-medium text-violet-600 underline decoration-dotted hover:text-violet-500 dark:text-violet-400">
            Cookies / Sign-in
          </button>
          tab.
        </p>
      </div>

      {needCookies && tab === "downloader" && (
        <div className={`${CARD} flex flex-col gap-2 border-amber-300 p-4 sm:flex-row sm:items-center dark:border-amber-800`}>
          <div className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>
              YouTube is asking for verification. Signing in with your own cookies usually
              fixes this - it takes about a minute.
            </span>
          </div>
          <button onClick={() => setTab("cookies")} className={`${BTN_SECONDARY} shrink-0 sm:ml-auto`}>
            <KeyRound size={15} /> Open Cookies / Sign-in
          </button>
        </div>
      )}

      {/* top-level tabs: Downloader | Cookies / Sign-in */}
      <div className="flex gap-2" role="tablist" aria-label="Downloader sections">
        <button
          role="tab"
          aria-selected={tab === "downloader"}
          onClick={() => setTab("downloader")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium sm:flex-none sm:px-6 ${
            tab === "downloader"
              ? "border-violet-500 bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300"
              : "border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300"
          }`}
        >
          <Download size={16} /> Downloader
        </button>
        <button
          role="tab"
          aria-selected={tab === "cookies"}
          onClick={() => setTab("cookies")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium sm:flex-none sm:px-6 ${
            tab === "cookies"
              ? "border-violet-500 bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300"
              : "border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300"
          }`}
        >
          <Cookie size={16} /> Cookies / Sign-in
          {cookieStatus && cookieStatus.source !== "none" && (
            <span className="h-2 w-2 rounded-full bg-emerald-500" title="Sign-in configured" />
          )}
        </button>
      </div>

      {tab === "cookies" && (
        <CookiesPanel status={cookieStatus} refresh={refreshCookies} />
      )}

      {tab === "downloader" && (
        <>
      <div className={`${CARD} p-4`}>
        <label className={LABEL} htmlFor="mediaurl">Video or audio URL</label>
        <div className="mt-1 flex gap-2">
          <div className="relative flex-1">
            <Link2 size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              id="mediaurl"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !fetching && fetchInfo()}
              placeholder="https://www.youtube.com/watch?v=..."
              className={`${INPUT} pl-9`}
              spellCheck={false}
              autoComplete="off"
            />
          </div>
          <button onClick={fetchInfo} disabled={fetching} className={BTN_SECONDARY}>
            {fetching ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Fetch info
          </button>
        </div>
      </div>

      {fetching && (
        <div className={`${CARD} flex items-center gap-3 p-6 text-sm text-slate-500 dark:text-slate-400`}>
          <Loader2 size={16} className="animate-spin" /> Contacting the site and reading available formats...
        </div>
      )}

      {info && (
        <>
          <div className={`${CARD} overflow-hidden`}>
            <div className="flex flex-col gap-4 p-4 sm:flex-row">
              <img
                src={info.thumbnail}
                alt=""
                className="h-36 w-full max-w-xs rounded-lg bg-slate-200 object-cover dark:bg-slate-800"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }}
              />
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold leading-snug text-slate-900 dark:text-slate-100">{info.title}</h3>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {info.uploader && <>{info.uploader} - </>}
                  {info.is_live ? "LIVE" : fmtDuration(info.duration)}
                  {info.extractor && <> - {info.extractor}</>}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {info.video_formats.length} video / {info.audio_formats.length} audio formats available
                </p>
              </div>
            </div>
          </div>

          <div className={`${CARD} space-y-4 p-4`}>
            <div className="flex gap-2" role="tablist" aria-label="Output type">
              <button role="tab" aria-selected={mode === "video"} onClick={() => setMode("video")}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium ${mode === "video" ? "border-violet-500 bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300" : "border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300"}`}>
                <Video size={16} /> Video (MP4)
              </button>
              <button role="tab" aria-selected={mode === "audio"} onClick={() => setMode("audio")}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium ${mode === "audio" ? "border-violet-500 bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300" : "border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300"}`}>
                <Music size={16} /> Audio (MP3 / M4A)
              </button>
            </div>

            {mode === "video" ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className={LABEL} htmlFor="res">Maximum resolution</label>
                  <select id="res" value={height} onChange={(e) => { setHeight(+e.target.value); setVideoFmt(""); }} className={`${INPUT} mt-1`} disabled={!!videoFmt}>
                    {HEIGHTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div>
                  <label className={LABEL} htmlFor="vfmt">Exact format (advanced)</label>
                  <select id="vfmt" value={videoFmt} onChange={(e) => setVideoFmt(e.target.value)} className={`${INPUT} mt-1`}>
                    <option value="">Auto-select (recommended)</option>
                    {info.video_formats.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.id} - {f.height ? `${f.height}p` : "video"} {f.fps ? `${Math.round(f.fps)}fps` : ""} {f.ext} {formatSize(f) ? `(${humanSize(formatSize(f))})` : ""} {f.type === "video-only" ? "(no audio)" : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300 sm:col-span-2">
                  <input type="checkbox" checked={preferH264} onChange={(e) => setPreferH264(e.target.checked)} disabled={!!videoFmt} className="accent-violet-600" />
                  Prefer H.264/AAC for maximum player compatibility (falls back to any codec if unavailable)
                </label>
                {videoFmt && info.video_formats.find((f) => f.id === videoFmt)?.type === "video-only" && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 sm:col-span-2">
                    Selected format has no audio - the best audio stream will be merged in (requires FFmpeg).
                  </p>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className={LABEL} htmlFor="afmt">Audio format</label>
                  <select id="afmt" value={audioFmt} onChange={(e) => setAudioFmt(e.target.value)} className={`${INPUT} mt-1`}>
                    <option value="mp3">MP3 (converted via FFmpeg)</option>
                    <option value="m4a">M4A / AAC (where available)</option>
                    <option value="best">Best available (no conversion)</option>
                  </select>
                </div>
                <div>
                  <label className={LABEL} htmlFor="akbps">Bitrate</label>
                  <select id="akbps" value={audioKbps ?? ""} onChange={(e) => setAudioKbps(+e.target.value)} className={`${INPUT} mt-1`} disabled={audioFmt === "best"}>
                    {[320, 256, 192, 128, 96, 64].map((k) => <option key={k} value={k}>{k} kbps</option>)}
                  </select>
                </div>
                {bestAudio && (
                  <p className="text-xs text-slate-500 dark:text-slate-400 sm:col-span-2">
                    Best source audio: {bestAudio.ext} {bestAudio.abr ? `${Math.round(bestAudio.abr)} kbps` : ""} {formatSize(bestAudio) ? `- about ${humanSize(formatSize(bestAudio))}` : ""}
                  </p>
                )}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4 dark:border-slate-800">
              <button onClick={start} disabled={starting} className={BTN_PRIMARY}>
                {starting ? <Loader2 size={15} className="animate-spin" /> : <Download size={16} />}
                Download {mode === "video" ? (videoFmt ? `format ${videoFmt}` : (height ? `${height}p` : "best")) : audioFmt.toUpperCase()}
              </button>
              {estSize ? (
                <span className="text-xs text-slate-500 dark:text-slate-400">Estimated size: {humanSize(estSize)}</span>
              ) : (
                <span className="text-xs text-slate-400">Size estimate unavailable for this selection</span>
              )}
              <span className="ml-auto flex items-center gap-1 text-[11px] text-slate-400">
                <AlertTriangle size={11} /> Respect copyright - download only permitted content
              </span>
            </div>
          </div>
        </>
      )}
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
