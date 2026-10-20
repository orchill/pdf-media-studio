import {
  Combine, FileOutput, FilePlus2, FileStack, Images, Loader2, Scissors,
  Video, Zap,
} from "lucide-react";
import { useEffect, useState } from "react";
import { listTasks, systemInfo } from "../api";
import { useNav } from "../ctx";
import { SystemInfo, TaskRecord, humanSize } from "../types";
import { StatusBadge } from "../components/TaskPanel";
import { CARD, SECTION_TITLE } from "../ui";

const TOOLS = [
  { id: "merge", icon: Combine, title: "Merge PDFs", desc: "Combine multiple PDFs in any order." },
  { id: "images", icon: Images, title: "Images to PDF", desc: "Turn photos into one PDF with page sizes, margins and rotation." },
  { id: "organize", icon: FileStack, title: "Organize Pages", desc: "Visually reorder, rotate and delete pages." },
  { id: "split", icon: Scissors, title: "Split / Extract", desc: "Extract page ranges or split every N pages." },
  { id: "compress", icon: Zap, title: "Compress PDF", desc: "Shrink file size while balancing quality." },
  { id: "extract", icon: FilePlus2, title: "Extract Images", desc: "Export the embedded images from a PDF." },
  { id: "toimages", icon: FileOutput, title: "PDF to Images", desc: "Render pages to PNG or JPG at any DPI." },
  { id: "media", icon: Video, title: "Media Downloader", desc: "Download video/audio via yt-dlp + FFmpeg." },
] as const;

function DepsCard({ info }: { info: SystemInfo | null }) {
  if (!info) return null;
  const d = info.deps;
  const items = [
    { name: "FFmpeg", ok: d.ffmpeg.found, detail: d.ffmpeg.found ? d.ffmpeg.version.split(" ")[0] : "install required" },
    { name: "yt-dlp", ok: d.ytdlp.found, detail: d.ytdlp.version },
    { name: "PyMuPDF", ok: true, detail: d.pymupdf },
    { name: "pypdf", ok: true, detail: d.pypdf },
    { name: "Pillow", ok: true, detail: d.pillow },
  ];
  return (
    <div className={`${CARD} p-4`}>
      <h2 className={`${SECTION_TITLE} mb-3 text-base`}>System status</h2>
      <ul className="space-y-1.5 text-sm">
        {items.map((it) => (
          <li key={it.name} className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${it.ok ? "bg-emerald-500" : "bg-red-500"}`} aria-hidden />
            <span className="font-medium text-slate-700 dark:text-slate-300">{it.name}</span>
            <span className="ml-auto truncate text-xs text-slate-500 dark:text-slate-400">{it.detail}</span>
          </li>
        ))}
        <li className="flex items-center gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          Output folder: <span className="truncate font-mono">{info.output_dir}</span>
        </li>
        {info.free_disk_gb != null && (
          <li className="text-xs text-slate-500 dark:text-slate-400">Free disk space: {info.free_disk_gb} GB</li>
        )}
      </ul>
    </div>
  );
}

export default function Dashboard() {
  const { navigate } = useNav();
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [recent, setRecent] = useState<TaskRecord[]>([]);

  useEffect(() => {
    systemInfo().then(setInfo).catch(() => {});
    listTasks(6).then(setRecent).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <section className={`${CARD} bg-gradient-to-br from-violet-600 to-violet-800 p-6 text-white`}>
        <h2 className="text-xl font-bold">Welcome to PDF &amp; Media Studio</h2>
        <p className="mt-1 max-w-2xl text-sm text-violet-100">
          A private, local-first toolbox: everything runs on this machine as a localhost service.
          Merge, convert, organize and compress PDFs; convert images; download and convert media
          with yt-dlp and FFmpeg. Original files are always preserved.
        </p>
      </section>

      <section>
        <h2 className={`${SECTION_TITLE} mb-3`}>Tools</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => navigate(t.id as any)}
                className={`${CARD} group flex items-start gap-3 p-4 text-left transition-all hover:border-violet-400 hover:shadow-md dark:hover:border-violet-500`}
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700 group-hover:bg-violet-600 group-hover:text-white dark:bg-violet-500/15 dark:text-violet-300">
                  <Icon size={18} />
                </span>
                <span>
                  <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">{t.title}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-slate-500 dark:text-slate-400">{t.desc}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DepsCard info={info} />
        <div className={`${CARD} p-4`}>
          <h2 className={`${SECTION_TITLE} mb-3 text-base`}>Recent tasks</h2>
          {recent.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">No tasks yet - results and downloads will appear here.</p>
          ) : (
            <ul className="space-y-2">
              {recent.map((t) => (
                <li key={t.id} className="flex items-center gap-2 text-sm">
                  <StatusBadge status={t.status} />
                  <span className="min-w-0 flex-1 truncate text-slate-700 dark:text-slate-300">{t.title}</span>
                  <span className="text-xs text-slate-400">
                    {t.result?.outputs?.[0]?.size ? humanSize(t.result.outputs[0].size) : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <p className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
        <Loader2 size={12} className="animate-spin" style={{ display: "none" }} />
        Only download media you have permission to save. This app does not bypass DRM or access controls.
      </p>
    </div>
  );
}
