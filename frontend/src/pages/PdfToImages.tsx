import { useEffect, useState } from "react";
import { FileOutput } from "lucide-react";
import FileDrop from "../components/FileDrop";
import PageGrid, { PageState } from "../components/PageGrid";
import TaskPanel from "../components/TaskPanel";
import { deleteFile, opToImages, uploadFiles } from "../api";
import { useToast } from "../ctx";
import { UploadedFile } from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, INPUT, LABEL, SECTION_TITLE } from "../ui";

export default function PdfToImages() {
  const [pdf, setPdf] = useState<UploadedFile | null>(null);
  const [pages, setPages] = useState<PageState[]>([]);
  const [selection, setSelection] = useState<Set<number>>(new Set());
  const [fmt, setFmt] = useState("png");
  const [dpi, setDpi] = useState(150);
  const [useAll, setUseAll] = useState(true);
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (pdf) {
      setPages(Array.from({ length: pdf.pages }, (_, i) => ({ page: i + 1, rotation: 0 })));
      setSelection(new Set(Array.from({ length: pdf.pages }, (_, i) => i + 1)));
    }
  }, [pdf]);

  const load = async (files: File[]) => {
    const f = files.find((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
    if (!f) { toast.push("error", "Drop a single PDF."); return; }
    setBusy(true);
    setTaskId(null);
    try {
      const [meta] = await uploadFiles([f]);
      setPdf(meta);
      setUseAll(true);
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
      const pagesSpec = useAll
        ? null
        : [...selection].sort((a, b) => a - b).join(",") || null;
      const { task_id } = await opToImages({ file_id: pdf.id, format: fmt, dpi, pages: pagesSpec });
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
        <h2 className={SECTION_TITLE}>PDF to Images</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Render pages to PNG (lossless) or JPG at the chosen DPI. Select specific pages if you do
          not need the whole document; multiple outputs arrive as a ZIP.
        </p>
      </div>

      {!pdf && <FileDrop onFiles={load} accept=".pdf,application/pdf" multiple={false} label="Drop a PDF" disabled={busy} />}

      {pdf && (
        <>
          <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <div>
              <label className={LABEL} htmlFor="fmt">Format</label>
              <select id="fmt" value={fmt} onChange={(e) => setFmt(e.target.value)} className={`${INPUT} mt-1 w-28`}>
                <option value="png">PNG</option>
                <option value="jpg">JPG</option>
              </select>
            </div>
            <div>
              <label className={LABEL} htmlFor="tdpi">DPI</label>
              <select id="tdpi" value={dpi} onChange={(e) => setDpi(+e.target.value)} className={`${INPUT} mt-1 w-32`}>
                <option value={72}>72 - screen</option>
                <option value={150}>150 - good</option>
                <option value={300}>300 - print</option>
                <option value={600}>600 - archive</option>
              </select>
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={useAll} onChange={(e) => setUseAll(e.target.checked)} className="accent-violet-600" />
              All pages
            </label>
            <span className="ml-auto flex gap-2">
              <button onClick={run} disabled={busy || (!useAll && !selection.size)} className={BTN_PRIMARY}>
                <FileOutput size={16} /> Export {useAll ? pdf.pages : selection.size} page(s)
              </button>
              <button onClick={() => { setPdf(null); deleteFile(pdf.id).catch(() => {}); }} className={BTN_SECONDARY}>Close file</button>
            </span>
          </div>

          {!useAll && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Click thumbnails below to pick pages ({selection.size} selected).
            </p>
          )}
          <PageGrid
            fileId={pdf.id}
            pages={pages}
            setPages={setPages}
            selection={selection}
            setSelection={setSelection}
            allowSelect={!useAll}
            width={180}
          />
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
