import { CheckCircle2, ChevronDown, ChevronRight, FolderOutput, Loader2, X, XCircle } from "lucide-react";
import { useState } from "react";
import { cancelTask, downloadUrl, getTaskLog, openOutputFolder } from "../api";
import { useToast } from "../ctx";
import { useTask } from "../hooks";
import { TaskRecord, humanSize } from "../types";
import { BADGE, BTN_DANGER, BTN_GHOST, BTN_SECONDARY, CARD } from "../ui";

const KIND_LABELS: Record<string, string> = {
  pdf_merge: "Merge PDFs",
  pdf_images: "Images to PDF",
  pdf_pages: "Edit pages",
  pdf_split: "Split PDF",
  pdf_compress: "Compress PDF",
  pdf_extract_images: "Extract images",
  pdf_to_images: "PDF to images",
  media_video: "Video download",
  media_audio: "Audio download",
};

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
    cancelled: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300",
    running: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300",
    queued: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  };
  return <span className={`${BADGE} ${map[status] || map.queued}`}>{status}</span>;
}

function ProgressBar({ value, indeterminate }: { value: number | null; indeterminate: boolean }) {
  if (indeterminate) {
    return (
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div className="h-full w-1/3 animate-progress rounded-full bg-violet-500" />
      </div>
    );
  }
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
      <div
        className="h-full rounded-full bg-violet-600 transition-[width] duration-300"
        style={{ width: `${Math.round((value ?? 0) * 100)}%` }}
        role="progressbar"
        aria-valuenow={Math.round((value ?? 0) * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      />
    </div>
  );
}

function LogViewer({ taskId }: { taskId: string }) {
  const [lines, setLines] = useState<string[] | null>(null);
  const [open, setOpen] = useState(false);
  const toggle = async () => {
    if (open) { setOpen(false); return; }
    try {
      const r = await getTaskLog(taskId);
      setLines(r.log.slice(-120));
    } catch {
      setLines(["Log is only available while the app is running (not archived)."]);
    }
    setOpen(true);
  };
  return (
    <div>
      <button onClick={toggle} className="flex items-center gap-1 text-xs text-slate-500 hover:text-violet-600 dark:text-slate-400">
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />} Diagnostics log
      </button>
      {open && (
        <pre className="mt-1.5 max-h-48 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-relaxed text-slate-300">
          {lines?.length ? lines.join("\n") : "No log output."}
        </pre>
      )}
    </div>
  );
}

export default function TaskPanel({ taskId, onDismiss }: { taskId: string | null; onDismiss?: () => void }) {
  const task = useTask(taskId);
  const toast = useToast();
  const [cancelling, setCancelling] = useState(false);
  if (!taskId || !task) return null;

  const running = task.status === "running" || task.status === "queued";
  const indeterminate = task.status === "running" && task.progress == null;
  const kindLabel = KIND_LABELS[task.kind] || task.kind;

  const doCancel = async () => {
    setCancelling(true);
    try {
      await cancelTask(task.id);
      toast.push("info", "Cancellation requested...");
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className={`${CARD} p-4`}>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{task.title}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {kindLabel}
            {task.finished_at && task.started_at && (
              <> - finished in {Math.max(0, (new Date(task.finished_at).getTime() - new Date(task.started_at).getTime()) / 1000).toFixed(1)}s</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {running ? (
            <Loader2 size={16} className="animate-spin text-violet-500" />
          ) : task.status === "completed" ? (
            <CheckCircle2 size={16} className="text-emerald-500" />
          ) : task.status === "failed" ? (
            <XCircle size={16} className="text-red-500" />
          ) : null}
          <StatusBadge status={task.status} />
          {running && (
            <button onClick={doCancel} disabled={cancelling} className={BTN_DANGER} aria-label="Cancel task">
              <X size={14} /> Cancel
            </button>
          )}
          {onDismiss && !running && (
            <button onClick={onDismiss} className={BTN_GHOST} aria-label="Dismiss panel"><X size={14} /></button>
          )}
        </div>
      </div>

      {running && (
        <div className="mt-3">
          <ProgressBar value={task.progress} indeterminate={indeterminate} />
          <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">{task.stage}</p>
        </div>
      )}

      {task.status === "completed" && (
        <div className="mt-3">
          {task.message && <p className="text-sm text-slate-600 dark:text-slate-300">{task.message}</p>}
          {task.result?.note && (
            <p className="mt-1 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
              {task.result.note}
            </p>
          )}
          <ul className="mt-2 space-y-1.5">
            {(task.result?.outputs || []).map((o) => (
              <li key={o.path} className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                <span className="min-w-0 flex-1 truncate text-sm text-slate-800 dark:text-slate-200" title={o.name}>{o.name}</span>
                <span className="text-xs text-slate-500">{humanSize(o.size)}</span>
                <a href={downloadUrl(o.path)} className={BTN_SECONDARY} download>
                  Download
                </a>
              </li>
            ))}
          </ul>
          <button
            onClick={async () => {
              try { await openOutputFolder(); } catch (e: any) { toast.push("error", e.message); }
            }}
            className={`${BTN_GHOST} mt-2 text-xs`}
          >
            <FolderOutput size={14} /> Open output folder
          </button>
        </div>
      )}

      {task.status === "failed" && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/40">
          <p className="text-sm font-medium text-red-800 dark:text-red-300">Something went wrong</p>
          <p className="mt-1 whitespace-pre-wrap break-words text-xs text-red-700 dark:text-red-300/90">{task.error}</p>
        </div>
      )}

      {(task.status === "failed" || (task.status === "completed" && task.kind.startsWith("media"))) && (
        <div className="mt-3"><LogViewer taskId={task.id} /></div>
      )}
    </div>
  );
}
