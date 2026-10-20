import { useEffect, useState } from "react";
import { Zap } from "lucide-react";
import FileDrop from "../components/FileDrop";
import TaskPanel from "../components/TaskPanel";
import { deleteFile, opCompress, uploadFiles } from "../api";
import { useToast } from "../ctx";
import { UploadedFile, humanSize } from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, SECTION_TITLE } from "../ui";

const PRESETS = [
  { id: "high", label: "High quality", quality: 80, dpi: 150, desc: "Crisp images, moderate saving" },
  { id: "balanced", label: "Balanced", quality: 62, dpi: 120, desc: "Good default for sharing" },
  { id: "aggressive", label: "Aggressive", quality: 42, dpi: 90, desc: "Smallest files, visible softening" },
  { id: "custom", label: "Custom", quality: 60, dpi: 120, desc: "Tune quality and DPI manually" },
];

export default function Compress() {
  const [pdf, setPdf] = useState<UploadedFile | null>(null);
  const [preset, setPreset] = useState("balanced");
  const [quality, setQuality] = useState(62);
  const [dpi, setDpi] = useState(120);
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    const p = PRESETS.find((p) => p.id === preset);
    if (p && preset !== "custom") { setQuality(p.quality); setDpi(p.dpi); }
  }, [preset]);

  const load = async (files: File[]) => {
    const f = files.find((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
    if (!f) { toast.push("error", "Drop a single PDF."); return; }
    setBusy(true);
    try {
      const [meta] = await uploadFiles([f]);
      setPdf(meta);
      setTaskId(null);
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
      const { task_id } = await opCompress({ file_id: pdf.id, quality, dpi_cap: dpi });
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
        <h2 className={SECTION_TITLE}>Compress PDF</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Downscales oversized embedded images and re-encodes them as JPEG. The tool reports the
          real output size after processing; if the file is already optimized, the original is kept.
        </p>
      </div>

      {!pdf && <FileDrop onFiles={load} accept=".pdf,application/pdf" multiple={false} label="Drop a PDF to compress" hint={pdf ? undefined : "Image-heavy documents shrink the most"} disabled={busy} />}

      {pdf && (
        <>
          <div className={`${CARD} p-4`}>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Source: <span className="font-medium">{pdf.name}</span> ({humanSize(pdf.size)}, {pdf.pages} pages)
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {PRESETS.map((p) => (
                <label key={p.id} className={`cursor-pointer rounded-lg border p-3 text-sm ${preset === p.id ? "border-violet-500 bg-violet-50 dark:bg-violet-500/10" : "border-slate-200 dark:border-slate-700"}`}>
                  <span className="flex items-center gap-2 font-medium text-slate-800 dark:text-slate-200">
                    <input type="radio" name="preset" checked={preset === p.id} onChange={() => setPreset(p.id)} className="accent-violet-600" />
                    {p.label}
                  </span>
                  <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{p.desc}</span>
                </label>
              ))}
            </div>
            {preset === "custom" && (
              <div className="mt-4 space-y-3">
                <label className="block text-xs text-slate-500 dark:text-slate-400" htmlFor="cq">
                  JPEG quality: {quality}
                  <input id="cq" type="range" min={20} max={95} value={quality} onChange={(e) => setQuality(+e.target.value)} className="ml-3 w-56 accent-violet-600" />
                </label>
                <label className="block text-xs text-slate-500 dark:text-slate-400" htmlFor="cdpi">
                  Max image DPI: {dpi}
                  <input id="cdpi" type="range" min={60} max={250} step={10} value={dpi} onChange={(e) => setDpi(+e.target.value)} className="ml-3 w-56 accent-violet-600" />
                </label>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button onClick={run} disabled={busy} className={BTN_PRIMARY}><Zap size={16} /> Compress</button>
            <button onClick={() => { setPdf(null); deleteFile(pdf.id).catch(() => {}); }} className={BTN_SECONDARY}>Close file</button>
          </div>
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
