import { RotateCcw, RotateCw, Trash2 } from "lucide-react";
import { useRef } from "react";
import { pageThumbUrl } from "../api";
import { CARD } from "../ui";

export interface PageState {
  page: number;      // 1-based original page number
  rotation: number;  // accumulated display rotation (deg)
}

interface Props {
  fileId: string;
  pages: PageState[];
  setPages: (p: PageState[]) => void;
  selection: Set<number>;
  setSelection: (s: Set<number>) => void;
  allowReorder?: boolean;
  allowRotate?: boolean;
  allowDelete?: boolean;
  allowSelect?: boolean;
  width?: number;
}

export default function PageGrid({
  fileId, pages, setPages, selection, setSelection,
  allowReorder, allowRotate, allowDelete, allowSelect, width = 210,
}: Props) {
  const dragFrom = useRef<number | null>(null);

  const toggleSelect = (page: number) => {
    const next = new Set(selection);
    if (next.has(page)) next.delete(page);
    else next.add(page);
    setSelection(next);
  };

  const rotate = (idx: number, delta: number) => {
    const next = [...pages];
    next[idx] = { ...next[idx], rotation: (next[idx].rotation + delta + 360) % 360 };
    setPages(next);
  };

  const remove = (idx: number) => {
    const p = pages[idx];
    const nextSel = new Set(selection);
    nextSel.delete(p.page);
    setSelection(nextSel);
    setPages(pages.filter((_, i) => i !== idx));
  };

  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4" role="list">
      {pages.map((p, idx) => {
        const selected = selection.has(p.page);
        return (
          <li
            key={`${p.page}-${idx}`}
            draggable={allowReorder}
            onDragStart={() => { dragFrom.current = idx; }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => {
              const from = dragFrom.current;
              dragFrom.current = null;
              if (from == null || from === idx) return;
              const next = [...pages];
              const [moved] = next.splice(from, 1);
              next.splice(idx, 0, moved);
              setPages(next);
            }}
            className={`group relative overflow-hidden rounded-lg border-2 bg-white shadow-sm transition-shadow dark:bg-slate-900
              ${selected ? "border-violet-500 ring-2 ring-violet-300 dark:ring-violet-500/40" : "border-slate-200 dark:border-slate-800"}
              ${allowReorder ? "cursor-grab" : ""}`}
          >
            <button
              type="button"
              onClick={() => allowSelect && toggleSelect(p.page)}
              aria-pressed={selected}
              aria-label={`Page ${p.page}${selected ? " (selected)" : ""}`}
              className="block w-full bg-slate-100 dark:bg-slate-800"
            >
              <img
                src={pageThumbUrl(fileId, p.page, width)}
                alt={`Page ${p.page} thumbnail`}
                loading="lazy"
                className="pointer-events-none h-auto w-full"
                style={{ transform: `rotate(${p.rotation}deg)` }}
              />
            </button>

            <div className="flex items-center justify-between px-2 py-1.5">
              <span className={`text-xs font-semibold ${selected ? "text-violet-600 dark:text-violet-300" : "text-slate-500 dark:text-slate-400"}`}>
                {p.rotation ? `Page ${p.page} (${p.rotation}deg)` : `Page ${p.page}`}
              </span>
              <span className="flex items-center gap-0.5">
                {allowRotate && (
                  <>
                    <button onClick={() => rotate(idx, -90)} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-violet-600 dark:hover:bg-slate-800" aria-label={`Rotate page ${p.page} left`} title="Rotate left">
                      <RotateCcw size={13} />
                    </button>
                    <button onClick={() => rotate(idx, 90)} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-violet-600 dark:hover:bg-slate-800" aria-label={`Rotate page ${p.page} right`} title="Rotate right">
                      <RotateCw size={13} />
                    </button>
                  </>
                )}
                {allowDelete && (
                  <button onClick={() => remove(idx)} className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10" aria-label={`Remove page ${p.page}`} title="Remove page">
                    <Trash2 size={13} />
                  </button>
                )}
              </span>
            </div>

            {selected && (
              <span className="absolute left-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-violet-600 text-[11px] font-bold text-white">
                ✓
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function EmptyGridHint({ children }: { children: React.ReactNode }) {
  return <div className={`${CARD} p-6 text-center text-sm text-slate-500 dark:text-slate-400`}>{children}</div>;
}
