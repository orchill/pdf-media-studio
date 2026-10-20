import { useEffect, useState } from "react";
import { FileStack, RotateCcw, RotateCw, Save, Trash2 } from "lucide-react";
import FileDrop from "../components/FileDrop";
import PageGrid, { PageState } from "../components/PageGrid";
import TaskPanel from "../components/TaskPanel";
import { deleteFile, opEditPages, uploadFiles } from "../api";
import { useToast } from "../ctx";
import { UploadedFile } from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, INPUT, LABEL, SECTION_TITLE } from "../ui";

export default function Organize() {
  const [pdf, setPdf] = useState<UploadedFile | null>(null);
  const [pages, setPages] = useState<PageState[]>([]);
  const [selection, setSelection] = useState<Set<number>>(new Set());
  const [outName, setOutName] = useState("");
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (pdf) {
      setPages(Array.from({ length: pdf.pages }, (_, i) => ({ page: i + 1, rotation: 0 })));
      setSelection(new Set());
      setOutName(`${pdf.name}_edited`);
    }
  }, [pdf]);

  const load = async (files: File[]) => {
    const pdfFile = files.find((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
    if (!pdfFile) {
      toast.push("error", "Drop a single PDF to organize its pages.");
      return;
    }
    setBusy(true);
    try {
      const [meta] = await uploadFiles([pdfFile]);
      setPdf(meta);
      toast.push("success", `${meta.name}: ${meta.pages} pages loaded.`);
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  const rotateSelected = (delta: number) => {
    const next = [...pages];
    next.forEach((p, i) => {
      if (selection.has(p.page)) next[i] = { ...p, rotation: (p.rotation + delta + 360) % 360 };
    });
    setPages(next);
  };

  const deleteSelected = () => {
    setPages((ps) => ps.filter((p) => !selection.has(p.page)));
    setSelection(new Set());
  };

  const rotateAll = (delta: number) => {
    setPages((ps) => ps.map((p) => ({ ...p, rotation: (p.rotation + delta + 360) % 360 })));
  };

  const save = async () => {
    if (!pdf || pages.length === 0) return;
    setBusy(true);
    try {
      const rotateMap: Record<string, number> = {};
      pages.forEach((p) => { if (p.rotation) rotateMap[String(p.page)] = p.rotation; });
      const { task_id } = await opEditPages({
        file_id: pdf.id,
        order: pages.map((p) => p.page),
        rotate: rotateMap,
        output_name: outName || null,
      });
      setTaskId(task_id);
      toast.push("info", "Processing pages...");
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className={SECTION_TITLE}>Organize Pages</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Drag pages to reorder, rotate or remove individual pages, or select several at once.
          Saving produces a new PDF; the source file stays untouched.
        </p>
      </div>

      {!pdf && <FileDrop onFiles={load} accept=".pdf,application/pdf" multiple={false} label="Drop a PDF to organize" hint="Pages appear as thumbnails" disabled={busy} />}

      {pdf && (
        <>
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{pdf.name} - {pages.length} page(s)</span>
            <span className="ml-auto flex flex-wrap items-center gap-2">
              <button onClick={() => setSelection(new Set(pages.map((p) => p.page)))} className={BTN_SECONDARY}>Select all</button>
              <button onClick={() => setSelection(new Set())} className={BTN_SECONDARY}>Select none</button>
              <button onClick={() => rotateSelected(-90)} disabled={!selection.size} className={BTN_SECONDARY}><RotateCcw size={14} /> Rotate selected</button>
              <button onClick={() => rotateSelected(90)} disabled={!selection.size} className={BTN_SECONDARY}><RotateCw size={14} /> Rotate selected</button>
              <button onClick={deleteSelected} disabled={!selection.size} className="inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:text-red-400 dark:hover:bg-red-500/10">
                <Trash2 size={14} /> Delete selected
              </button>
              <button onClick={() => rotateAll(90)} className={BTN_SECONDARY}>Rotate all +90</button>
              <button onClick={() => { setPdf(null); deleteFile(pdf.id).catch(() => {}); }} className={BTN_SECONDARY}>Close file</button>
            </span>
          </div>

          {pages.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">
              All pages removed - add pages back by reloading the file.
            </p>
          ) : (
            <PageGrid
              fileId={pdf.id}
              pages={pages}
              setPages={setPages}
              selection={selection}
              setSelection={setSelection}
              allowReorder
              allowRotate
              allowDelete
              allowSelect
            />
          )}

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-48">
              <label className={LABEL} htmlFor="outname">Output filename</label>
              <input id="outname" value={outName} onChange={(e) => setOutName(e.target.value)} className={`${INPUT} mt-1`} />
            </div>
            <button onClick={save} disabled={busy || !pages.length} className={BTN_PRIMARY}>
              <Save size={16} /> Save as new PDF
            </button>
          </div>
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
