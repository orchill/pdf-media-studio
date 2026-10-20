import { useState } from "react";
import { Combine } from "lucide-react";
import FileDrop from "../components/FileDrop";
import FileCard from "../components/FileCard";
import TaskPanel from "../components/TaskPanel";
import { deleteFile, opMerge, uploadFiles } from "../api";
import { useToast } from "../ctx";
import { useReorder } from "../hooks";
import { UploadedFile } from "../types";
import { BTN_PRIMARY, SECTION_TITLE } from "../ui";

export default function Merge() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();
  const reorder = useReorder(files, setFiles);

  const addFiles = async (list: File[]) => {
    const pdfs = list.filter((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
    if (pdfs.length === 0) {
      toast.push("error", "Please drop PDF files only for merging.");
      return;
    }
    setBusy(true);
    try {
      const metas = await uploadFiles(pdfs);
      setFiles((cur) => [...cur, ...metas]);
      toast.push("success", `Added ${metas.length} PDF${metas.length > 1 ? "s" : ""}.`);
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (f: UploadedFile) => {
    setFiles((cur) => cur.filter((x) => x.id !== f.id));
    deleteFile(f.id).catch(() => {});
  };

  const merge = async () => {
    if (files.length < 2) {
      toast.push("error", "Add at least two PDF files.");
      return;
    }
    setBusy(true);
    try {
      const { task_id } = await opMerge(files.map((f) => f.id));
      setTaskId(task_id);
      toast.push("info", "Merge started.");
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className={SECTION_TITLE}>Merge PDFs</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Drop PDFs, drag to set the order, then merge. Outputs are written to your output folder -
          original files are never modified.
        </p>
      </div>

      {files.length === 0 && (
        <FileDrop
          onFiles={addFiles}
          accept=".pdf,application/pdf"
          label="Drop PDF files here or click to browse"
          hint="2-24 files - order can be adjusted after adding"
          disabled={busy}
        />
      )}

      {files.length > 0 && (
        <>
          <FileDrop onFiles={addFiles} accept=".pdf,application/pdf" label="Add more PDFs" disabled={busy} />
          <ul className="space-y-2">
            {files.map((f, i) => (
              <div key={f.id} {...{ onDragOver: reorder.onDragOver }} onDrop={reorder.onDrop(i)}>
                <div onDragStart={reorder.onDragStart(i)}>
                  <FileCard file={f} draggable index={i} badge={`#${i + 1}`} onRemove={() => remove(f)} />
                </div>
              </div>
            ))}
          </ul>
          <div className="flex items-center gap-3">
            <button onClick={merge} disabled={busy || files.length < 2} className={BTN_PRIMARY}>
              <Combine size={16} /> Merge {files.length} PDFs
            </button>
            <button
              onClick={() => { files.forEach((f) => deleteFile(f.id).catch(() => {})); setFiles([]); }}
              className="text-sm text-slate-500 hover:text-red-600 dark:text-slate-400"
            >
              Clear list
            </button>
          </div>
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
