import { useState } from "react";
import { FilePlus2 } from "lucide-react";
import FileDrop from "../components/FileDrop";
import TaskPanel from "../components/TaskPanel";
import { deleteFile, opExtractImages, uploadFiles } from "../api";
import { useToast } from "../ctx";
import { UploadedFile, humanSize } from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, SECTION_TITLE } from "../ui";

export default function ExtractImages() {
  const [pdf, setPdf] = useState<UploadedFile | null>(null);
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();

  const load = async (files: File[]) => {
    const f = files.find((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
    if (!f) { toast.push("error", "Drop a single PDF."); return; }
    setBusy(true);
    setTaskId(null);
    try {
      const [meta] = await uploadFiles([f]);
      setPdf(meta);
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  const run = async () => {
    if (!pdf) return;
    setBusy(true);
    try {
      const { task_id } = await opExtractImages(pdf.id);
      setTaskId(task_id);
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className={SECTION_TITLE}>Extract Images</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Exports the embedded raster images (photos, figures) at their stored resolution, in
          their original format when possible. Vector graphics are not raster images and are skipped.
        </p>
      </div>

      {!pdf && <FileDrop onFiles={load} accept=".pdf,application/pdf" multiple={false} label="Drop a PDF" disabled={busy} />}

      {pdf && (
        <>
          <div className={`${CARD} flex flex-wrap items-center gap-3 p-4`}>
            <span className="text-sm text-slate-600 dark:text-slate-300">{pdf.name} - {humanSize(pdf.size)}</span>
            <span className="ml-auto flex gap-2">
              <button onClick={run} disabled={busy} className={BTN_PRIMARY}><FilePlus2 size={16} /> Extract images</button>
              <button onClick={() => { setPdf(null); deleteFile(pdf.id).catch(() => {}); }} className={BTN_SECONDARY}>Close file</button>
            </span>
          </div>
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
