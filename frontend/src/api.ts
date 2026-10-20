import type { CookieStatus, CookieTestResult, MediaInfo, Settings, SystemInfo, TaskRecord, UploadedFile } from "./types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail)) detail = j.detail.map((d: any) => d.msg || JSON.stringify(d)).join("; ");
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const JSON_HDR = { "Content-Type": "application/json" };

// ---------------------------------------------------------------- files
export const uploadFiles = (files: File[]) => {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return api<UploadedFile[]>("/api/upload", { method: "POST", body: fd });
};
export const listFiles = () => api<UploadedFile[]>("/api/files");
export const deleteFile = (id: string) => api<{ deleted: string }>(`/api/files/${id}`, { method: "DELETE" });
export const clearWorkspace = () => api<{ removed: number }>("/api/system/clear-workspace", { method: "POST" });
export const rawUrl = (id: string) => `/api/file/${id}/raw`;
export const thumbUrl = (id: string, w = 240) => `/api/file/${id}/thumbnail?width=${w}`;
export const pageThumbUrl = (id: string, page: number, w = 200) =>
  `/api/pdf/${id}/page/${page}/thumbnail?width=${w}`;
export const downloadUrl = (path: string) => `/api/download?path=${encodeURIComponent(path)}`;

// ---------------------------------------------------------------- tasks
export const getTask = (id: string) => api<TaskRecord>(`/api/tasks/${id}`);
export const listTasks = (limit = 50, status?: string, kind?: string) => {
  const q = new URLSearchParams({ limit: String(limit) });
  if (status) q.set("status", status);
  if (kind) q.set("kind", kind);
  return api<TaskRecord[]>(`/api/tasks?${q}`);
};
export const cancelTask = (id: string) => api<{ cancelled: string }>(`/api/tasks/${id}/cancel`, { method: "POST" });
export const deleteTask = (id: string) => api<{ removed: string }>(`/api/tasks/${id}`, { method: "DELETE" });
export const getTaskLog = (id: string) =>
  api<{ id: string; log: string[] }>(`/api/tasks/${id}/log`);

// ---------------------------------------------------------------- pdf ops
type OpPayload = Record<string, any>;
const startOp = (endpoint: string, payload: OpPayload) =>
  api<{ task_id: string }>(`/api/pdf/${endpoint}`, {
    method: "POST",
    headers: JSON_HDR,
    body: JSON.stringify(payload),
  });

export const opMerge = (file_ids: string[]) => startOp("merge", { file_ids });
export const opImagesToPdf = (payload: OpPayload) => startOp("images-to-pdf", payload);
export const opEditPages = (payload: OpPayload) => startOp("pages", payload);
export const opSplit = (payload: OpPayload) => startOp("split", payload);
export const opCompress = (payload: OpPayload) => startOp("compress", payload);
export const opExtractImages = (file_id: string) => startOp("extract-images", { file_id });
export const opToImages = (payload: OpPayload) => startOp("to-images", payload);

// ---------------------------------------------------------------- media
export const mediaInfo = (url: string) =>
  api<MediaInfo>(`/api/media/info?url=${encodeURIComponent(url)}`);
export const mediaDownload = (payload: OpPayload) =>
  api<{ task_id: string }>("/api/media/download", {
    method: "POST",
    headers: JSON_HDR,
    body: JSON.stringify(payload),
  });
export const getCookieStatus = () => api<CookieStatus>("/api/media/cookies");
export const saveCookiePrefs = (payload: {
  source: "none" | "file" | "browser";
  browser?: string;
  cookies_text?: string;
  domain?: string;
}) =>
  api<CookieStatus>("/api/media/cookies", {
    method: "PUT",
    headers: JSON_HDR,
    body: JSON.stringify(payload),
  });
export const clearCookiePrefs = () =>
  api<CookieStatus>("/api/media/cookies", { method: "DELETE" });
export const testCookiePrefs = () =>
  api<CookieTestResult>("/api/media/cookies/test", { method: "POST" });

// ---------------------------------------------------------------- system
export const systemInfo = () => api<SystemInfo>("/api/system/info");
export const getSettings = () => api<Settings>("/api/settings");
export const saveSettings = (patch: Partial<Settings>) =>
  api<{ config: Settings; restart_required: string[] }>("/api/settings", {
    method: "PUT",
    headers: JSON_HDR,
    body: JSON.stringify({ patch }),
  });
export const openOutputFolder = () => api<{ opened: string }>("/api/system/open-output-folder", { method: "POST" });
