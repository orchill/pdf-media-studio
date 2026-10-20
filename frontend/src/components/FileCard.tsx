import { FileText, GripVertical, Image as ImageIcon, X } from "lucide-react";
import { thumbUrl } from "../api";
import { UploadedFile, humanSize } from "../types";

interface Props {
  file: UploadedFile;
  onRemove?: () => void;
  draggable?: boolean;
  index?: number;
  badge?: string;
}

export default function FileCard({ file, onRemove, draggable, index, badge }: Props) {
  return (
    <li
      draggable={draggable}
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        (e.currentTarget as HTMLElement).dataset.index = String(index);
      }}
      onDragOver={(e) => e.preventDefault()}
      className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-2.5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      {draggable && (
        <span className="cursor-grab text-slate-400" title="Drag to reorder" aria-hidden>
          <GripVertical size={16} />
        </span>
      )}
      {file.kind === "pdf" ? (
        <div className="flex h-12 w-10 shrink-0 items-center justify-center overflow-hidden rounded-md bg-slate-100 dark:bg-slate-800">
          <img src={thumbUrl(file.id, 120)} alt="" className="h-full w-full object-cover" loading="lazy" />
        </div>
      ) : (
        <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-md bg-slate-100 dark:bg-slate-800">
          <img src={thumbUrl(file.id, 120)} alt="" className="h-full w-full object-cover" loading="lazy" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{file.name}</p>
        <p className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
          {file.kind === "pdf" ? <FileText size={11} /> : <ImageIcon size={11} />}
          {file.kind.toUpperCase()} - {humanSize(file.size)}
          {file.kind === "pdf" && ` - ${file.pages} pages`}
          {file.kind === "image" && file.width ? ` - ${file.width}x${file.height}` : ""}
          {badge && <span className="ml-1 rounded bg-violet-100 px-1.5 text-[10px] font-semibold text-violet-700 dark:bg-violet-500/20 dark:text-violet-300">{badge}</span>}
        </p>
      </div>
      {onRemove && (
        <button onClick={onRemove} className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10" aria-label={`Remove ${file.name}`}>
          <X size={15} />
        </button>
      )}
    </li>
  );
}
