export type TaskStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface OutputFile {
  name: string;
  path: string;
  size: number;
  url: string;
}

export interface TaskRecord {
  id: string;
  kind: string;
  title: string;
  status: TaskStatus;
  progress: number | null;
  stage: string;
  message: string;
  error: string;
  result: { outputs?: OutputFile[]; info?: Record<string, any>; note?: string };
  log_tail: string[];
  meta: Record<string, any>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface UploadedFile {
  id: string;
  name: string;
  orig_name?: string;
  size: number;
  kind: "pdf" | "image";
  pages: number;
  format: string;
  width?: number;
  height?: number;
  ext?: string;
  uploaded_at?: string;
}

export interface MediaFormat {
  id: string;
  ext: string;
  type: "video+audio" | "video-only" | "audio-only";
  vcodec: string;
  acodec: string;
  height: number | null;
  width: number | null;
  fps: number | null;
  abr: number | null;
  vbr: number | null;
  tbr: number | null;
  filesize: number | null;
  filesize_approx: number | null;
  note: string;
}

export interface MediaInfo {
  id: string;
  title: string;
  uploader: string;
  duration: number | null;
  thumbnail: string;
  is_live: boolean;
  extractor: string;
  webpage_url: string;
  formats: MediaFormat[];
  video_formats: MediaFormat[];
  audio_formats: MediaFormat[];
}

export interface CookieStatus {
  source: "none" | "file" | "browser";
  browser: string;
  file_present: boolean;
  cookie_count: number;
  domains: string[];
  supported_browsers: string[];
}

export interface CookieTestResult {
  ok: boolean;
  message: string;
  elapsed_s?: number;
}

export interface SystemInfo {
  app: string;
  app_version: string;
  python: string;
  platform: string;
  output_dir: string;
  data_dir: string;
  free_disk_gb: number | null;
  deps: {
    ffmpeg: { found: boolean; path: string; version: string };
    ffprobe: { found: boolean; path: string };
    ytdlp: { found: boolean; version: string; source: string };
    pymupdf: string;
    pypdf: string;
    pillow: string;
    fastapi: string;
  };
  config: Record<string, any>;
}

export type Settings = {
  host: string;
  port: number;
  output_dir: string;
  ffmpeg_path: string;
  ytdlp_path: string;
  max_upload_mb: number;
  max_download_gb: number;
  max_duration_hours: number;
  max_concurrent_tasks: number;
  history_limit: number;
  open_browser: boolean;
};

export interface ImageItem {
  id: string;
  rotation: number;
}

export const TERMINAL: TaskStatus[] = ["completed", "failed", "cancelled"];
export const isTerminal = (s: TaskStatus) => TERMINAL.includes(s);

export function humanSize(n: number | null | undefined): string {
  if (n == null) return "-";
  if (n < 1024) return `${Math.round(n)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n;
  let u = -1;
  do {
    v /= 1024;
    u++;
  } while (v >= 1024 && u < units.length - 1);
  return `${v.toFixed(1)} ${units[u]}`;
}

export function fmtDuration(s: number | null | undefined): string {
  if (s == null || isNaN(s)) return "-";
  const total = Math.round(s);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const sec = total % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    : `${m}:${String(sec).padStart(2, "0")}`;
}
