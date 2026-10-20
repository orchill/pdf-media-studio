import { useEffect, useState } from "react";
import { Scissors } from "lucide-react";
import FileDrop from "../components/FileDrop";
import PageGrid, { PageState } from "../components/PageGrid";
import TaskPanel from "../components/TaskPanel";
import { deleteFile, opSplit, uploadFiles } from "../api";
import { useToast } from "../ctx";
import { UploadedFile } from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, INPUT, LABEL, SECTION_TITLE } from "../ui";

type Mode = "extract" | "ranges" | "every_n";

export default function Split() {
  const [pdf, setPdf] = useState<UploadedFile | null>(null);
  const [pages, setPages] = useState<PageState[]>([]);
  const [selection, setSelection] = useState<Set<number>>(new Set());
  const [mode, setMode] = useState<Mode>("extract");
  const [rangeText, setRangeText] = useState("1-3, 5");
  const [everyN, setEveryN] = useState(1);
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (pdf) setPages(Array.from({ length: pdf.pages }, (_, i) => ({ page: i + 1, rotation: 0 })));
    setSelection(new Set());
  }, [pdf]);

  const load = async (files: File[]) => {
    const pdfFile = files.find((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
    if (!pdfFile) { toast.push("error", "Drop a single PDF."); return; }
    setBusy(true);
    try {
      const [meta] = await uploadFiles([pdfFile]);
      setPdf(meta);
      toast.push("success", `${meta.name}: ${meta.pages} pages.`);
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  const applySelectionToRangeText = () => {
    const sel = [...selection].sort((a, b) => a - b);
    if (!sel.length) { setRangeText(""); return; }
    const groups: string[] = [];
    let start = sel[0], prev = sel[0];
    for (const p of sel.slice(1)) {
      if (p === prev + 1) { prev = p; continue; }
      groups.push(start === prev ? `${start}` : `${start}-${prev}`);
      start = prev = p;
    }
    groups.push(start === prev ? `${start}` : `${start}-${prev}`);
    setRangeText(groups.join(", "));
  };

  const run = async () => {
    if (!pdf) return;
    setBusy(true);
    try {
      const payload: Record<string, any> = { file_id: pdf.id, mode };
      if (mode === "extract") payload.pages = [...selection].sort((a, b) => a - b).join(",") || undefined;
      if (mode === "ranges") payload.ranges = rangeText;
      if (mode === "every_n") payload.every_n = everyN;
      const { task_id } = await opSplit(payload);
      setTaskId(task_id);
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  const modes: { id: Mode; label: string; desc: string }[] = [
    { id: "extract", label: "Extract pages", desc: "Selected pages become one new PDF" },
    { id: "ranges", label: "Split by ranges", desc: "Each range becomes its own PDF (e.g. 1-3, 5, 8-10)" },
    { id: "every_n", label: "Every N pages", desc: "Fixed-size chunks" },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h2 className={SECTION_TITLE}>Split / Extract</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Extract selected pages into a single document, or split a PDF into several files.
          Multiple outputs are delivered as a ZIP archive.
        </p>
      </div>

      {!pdf && <FileDrop onFiles={load} accept=".pdf,application/pdf" multiple={false} label="Drop a PDF to split" hint="Click pages to select them" disabled={busy} />}

      {pdf && (
        <>
          <div className="grid grid-cols-1 gap-2 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-3">
            {modes.map((m) => (
              <label key={m.id} className={`flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-sm transition-colors ${mode === m.id ? "border-violet-500 bg-violet-50 dark:bg-violet-500/10" : "border-slate-200 dark:border-slate-700"}`}>
                <span className="flex items-center gap-2 font-medium text-slate-800 dark:text-slate-200">
                  <input type="radio" name="splitmode" checked={mode === m.id} onChange={() => setMode(m.id)} className="accent-violet-600" />
                  {m.label}
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">{m.desc}</span>
              </label>
            ))}
          </div>

          {mode === "extract" && (
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => setSelection(new Set(pages.map((p) => p.page)))} className={BTN_SECONDARY}>Select all</button>
              <button onClick={() => setSelection(new Set())} className={BTN_SECONDARY}>Clear</button>
              <button onClick={applySelectionToRangeText} className={BTN_SECONDARY}>Selection to text</button>
              <span className="text-sm text-slate-500 dark:text-slate-400">{selection.size} page(s) selected</span>
            </div>
          )}

          {mode === "ranges" && (
            <div>
              <label className={LABEL} htmlFor="ranges">Page ranges (each group = one output file)</label>
              <input id="ranges" value={rangeText} onChange={(e) => setRangeText(e.target.value)} placeholder="1-3, 5, 8-10" className={`${INPUT} mt-1`} />
            </div>
          )}

          {mode === "every_n" && (
            <div>
              <label className={LABEL} htmlFor="everyn">Pages per output file</label>
              <input id="everyn" type="number" min={1} max={pdf.pages} value={everyN} onChange={(e) => setEveryN(Math.max(1, +e.target.value))} className={`${INPUT} mt-1 w-32`} />
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Will produce {Math.ceil(pdf.pages / Math.max(1, everyN))} file(s).
              </p>
            </div>
          )}

          <PageGrid
            fileId={pdf.id}
            pages={pages}
            setPages={setPages}
            selection={selection}
            setSelection={setSelection}
            allowSelect
            width={180}
          />

          <div className="flex items-center gap-3">
            <button onClick={run} disabled={busy || (mode === "extract" && !selection.size)} className={BTN_PRIMARY}>
              <Scissors size={16} />
              {mode === "extract" ? `Extract ${selection.size} page(s)` : "Split document"}
            </button>
            <button onClick={() => { setPdf(null); deleteFile(pdf.id).catch(() => {}); }} className={BTN_SECONDARY}>Close file</button>
          </div>
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
