import { useEffect, useState } from "react";
import { CheckCircle2, FolderOutput, RefreshCw, Save, ShieldAlert, Trash2, XCircle } from "lucide-react";
import { clearWorkspace, getSettings, openOutputFolder, saveSettings, systemInfo } from "../api";
import { useToast } from "../ctx";
import { Settings, SystemInfo } from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, INPUT, LABEL, SECTION_TITLE } from "../ui";

function DepRow({ name, found, detail, hint }: { name: string; found: boolean; detail: string; hint?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2 py-1.5">
      {found ? <CheckCircle2 size={15} className="text-emerald-500" /> : <XCircle size={15} className="text-red-500" />}
      <span className="text-sm font-medium text-slate-800 dark:text-slate-200">{name}</span>
      <span className={`truncate text-xs ${found ? "text-slate-500 dark:text-slate-400" : "text-red-500"}`}>{detail}</span>
      {!found && hint && <span className="w-full text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </div>
  );
}

export default function SettingsPage() {
  const [cfg, setCfg] = useState<Settings | null>(null);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const loadAll = async () => {
    try {
      setCfg(await getSettings());
      setInfo(await systemInfo());
    } catch (e: any) {
      toast.push("error", e.message);
    }
  };
  useEffect(() => { loadAll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k: keyof Settings, v: any) => setCfg((c) => (c ? { ...c, [k]: v } : c));

  const save = async () => {
    if (!cfg) return;
    setSaving(true);
    try {
      const { restart_required } = await saveSettings({
        output_dir: cfg.output_dir,
        ffmpeg_path: cfg.ffmpeg_path,
        ytdlp_path: cfg.ytdlp_path,
        max_upload_mb: cfg.max_upload_mb,
        max_download_gb: cfg.max_download_gb,
        max_duration_hours: cfg.max_duration_hours,
        max_concurrent_tasks: cfg.max_concurrent_tasks,
        history_limit: cfg.history_limit,
        open_browser: cfg.open_browser,
      });
      toast.push("success", "Settings saved." + (restart_required.length ? ` Restart required for: ${restart_required.join(", ")}` : ""));
      setInfo(await systemInfo());
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!cfg) return <p className="text-sm text-slate-500">Loading settings...</p>;

  return (
    <div className="space-y-4">
      <h2 className={SECTION_TITLE}>Settings</h2>

      <div className={`${CARD} space-y-4 p-4`}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="outdir">Output directory (processed files are saved here)</label>
            <input id="outdir" value={cfg.output_dir} onChange={(e) => set("output_dir", e.target.value)} className={`${INPUT} mt-1 font-mono text-xs`} />
          </div>
          <div>
            <label className={LABEL} htmlFor="ffmpeg">FFmpeg path (empty = auto-detect)</label>
            <input id="ffmpeg" value={cfg.ffmpeg_path} onChange={(e) => set("ffmpeg_path", e.target.value)} placeholder="C:\ffmpeg\bin\ffmpeg.exe or /usr/bin/ffmpeg" className={`${INPUT} mt-1 font-mono text-xs`} />
          </div>
          <div>
            <label className={LABEL} htmlFor="ytdlp">yt-dlp path (empty = built-in module)</label>
            <input id="ytdlp" value={cfg.ytdlp_path} onChange={(e) => set("ytdlp_path", e.target.value)} placeholder="C:\tools\yt-dlp.exe" className={`${INPUT} mt-1 font-mono text-xs`} />
          </div>
          <div className="grid grid-cols-2 gap-4 sm:col-span-2 sm:grid-cols-4">
            <div>
              <label className={LABEL} htmlFor="upl">Max upload (MB)</label>
              <input id="upl" type="number" value={cfg.max_upload_mb} onChange={(e) => set("max_upload_mb", +e.target.value)} className={`${INPUT} mt-1`} />
            </div>
            <div>
              <label className={LABEL} htmlFor="dlgb">Max download (GB, 0 = no cap)</label>
              <input id="dlgb" type="number" value={cfg.max_download_gb} onChange={(e) => set("max_download_gb", +e.target.value)} className={`${INPUT} mt-1`} />
            </div>
            <div>
              <label className={LABEL} htmlFor="dur">Max duration (h, 0 = no cap)</label>
              <input id="dur" type="number" value={cfg.max_duration_hours} onChange={(e) => set("max_duration_hours", +e.target.value)} className={`${INPUT} mt-1`} />
            </div>
            <div>
              <label className={LABEL} htmlFor="conc">Parallel tasks</label>
              <input id="conc" type="number" value={cfg.max_concurrent_tasks} onChange={(e) => set("max_concurrent_tasks", +e.target.value)} className={`${INPUT} mt-1`} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300 sm:col-span-2">
            <input type="checkbox" checked={cfg.open_browser} onChange={(e) => set("open_browser", e.target.checked)} className="accent-violet-600" />
            Open the web interface automatically on startup
          </label>
        </div>
        <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
          <button onClick={save} disabled={saving} className={BTN_PRIMARY}><Save size={15} /> Save settings</button>
          <button onClick={async () => { try { await openOutputFolder(); } catch (e: any) { toast.push("error", e.message); } }} className={BTN_SECONDARY}>
            <FolderOutput size={15} /> Open output folder
          </button>
          <button
            onClick={async () => {
              if (!confirm("Clear all cached uploads and thumbnails? Files in the output folder are NOT touched.")) return;
              try { const r = await clearWorkspace(); toast.push("success", `Cleared ${r.removed} items.`); }
              catch (e: any) { toast.push("error", e.message); }
            }}
            className={BTN_SECONDARY}
          >
            <Trash2 size={15} /> Clear workspace cache
          </button>
        </div>
      </div>

      <div className={`${CARD} p-4`}>
        <div className="mb-2 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Dependencies &amp; diagnostics</h3>
          <button onClick={loadAll} className={`${BTN_SECONDARY} ml-auto py-1 text-xs`}><RefreshCw size={12} /> Re-check</button>
        </div>
        {info && (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            <DepRow name="FFmpeg" found={info.deps.ffmpeg.found}
              detail={info.deps.ffmpeg.found ? `${info.deps.ffmpeg.version} (${info.deps.ffmpeg.path})` : "not found"}
              hint="Install: winget install Gyan.FFmpeg (Windows) or apt install ffmpeg (Linux), then restart the app - or set the path above." />
            <DepRow name="yt-dlp" found={info.deps.ytdlp.found} detail={`${info.deps.ytdlp.version} (${info.deps.ytdlp.source})`} />
            <DepRow name="PyMuPDF" found detail={info.deps.pymupdf} />
            <DepRow name="pypdf" found detail={info.deps.pypdf} />
            <DepRow name="Pillow" found detail={info.deps.pillow} />
            <p className="pt-2 text-xs text-slate-400">
              App {info.app_version} - Python {info.python} - {info.platform}
              {info.free_disk_gb != null && <> - {info.free_disk_gb} GB free</>}
            </p>
          </div>
        )}
      </div>

      <div className={`${CARD} border-amber-300 p-4 dark:border-amber-800`}>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-400">
          <ShieldAlert size={15} /> Privacy &amp; security notes
        </h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
          <li>The server binds to 127.0.0.1 only - other devices on your network cannot reach it.</li>
          <li>URLs pointing at private/loopback addresses are rejected to prevent SSRF.</li>
          <li>Downloads are limited in size and duration (see fields above).</li>
          <li>Cached uploads are wiped on every restart; outputs stay in the output folder.</li>
          <li>YouTube cookies (if configured in the downloader's Cookies / Sign-in tab) are
            stored only in <code>data/cookies.txt</code>, never logged and never shown.</li>
          <li>No telemetry, no cloud services - files never leave this machine.</li>
        </ul>
      </div>
    </div>
  );
}
