import { useState } from "react";
import { FileImage, RotateCcw, RotateCw } from "lucide-react";
import FileDrop from "../components/FileDrop";
import TaskPanel from "../components/TaskPanel";
import { deleteFile, opImagesToPdf, thumbUrl, uploadFiles } from "../api";
import { useToast } from "../ctx";
import { useReorder } from "../hooks";
import { UploadedFile } from "../types";
import { BTN_PRIMARY, INPUT, LABEL, SECTION_TITLE } from "../ui";

const PAGE_SIZES = [
  ["a4", "A4 (210x297 mm)"],
  ["letter", "Letter (216x279 mm)"],
  ["legal", "Legal (216x356 mm)"],
  ["a3", "A3 (297x420 mm)"],
  ["a5", "A5 (148x210 mm)"],
  ["image", "Match image size"],
];

export default function ImagesToPdf() {
  const [images, setImages] = useState<UploadedFile[]>([]);
  const [rotations, setRotations] = useState<Record<string, number>>({});
  const [pageSize, setPageSize] = useState("a4");
  const [orientation, setOrientation] = useState("auto");
  const [marginMm, setMarginMm] = useState(10);
  const [imageDpi, setImageDpi] = useState(96);
  const [recompress, setRecompress] = useState(false);
  const [quality, setQuality] = useState(80);
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const toast = useToast();
  const reorder = useReorder(images, setImages);

  const addFiles = async (list: File[]) => {
    const imgs = list.filter((f) => /\.(png|jpe?g|webp|gif|bmp|tiff?)$/i.test(f.name) || f.type.startsWith("image/"));
    if (!imgs.length) {
      toast.push("error", "Please drop image files (PNG, JPEG, WebP, GIF, BMP, TIFF).");
      return;
    }
    setBusy(true);
    try {
      const metas = await uploadFiles(imgs);
      setImages((cur) => [...cur, ...metas]);
      toast.push("success", `Added ${metas.length} image${metas.length > 1 ? "s" : ""}.`);
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  const rotate = (id: string, delta: number) =>
    setRotations((r) => ({ ...r, [id]: ((r[id] || 0) + delta + 360) % 360 }));

  const convert = async () => {
    if (!images.length) return;
    setBusy(true);
    try {
      const { task_id } = await opImagesToPdf({
        items: images.map((f) => ({ id: f.id, rotation: rotations[f.id] || 0 })),
        page_size: pageSize,
        orientation,
        margin_mm: marginMm,
        image_dpi: imageDpi,
        jpeg_quality: recompress ? quality : null,
      });
      setTaskId(task_id);
      toast.push("info", "Conversion started.");
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className={SECTION_TITLE}>Images to PDF</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Choose page size, margins and orientation; drag thumbnails to reorder and rotate individual
          images. Original image data is embedded without recompression unless you opt into it.
        </p>
      </div>

      {images.length === 0 && (
        <FileDrop
          onFiles={addFiles}
          accept="image/*"
          label="Drop images here or click to browse"
          hint="PNG, JPEG, WebP, GIF, BMP, TIFF"
          disabled={busy}
        />
      )}

      {images.length > 0 && (
        <>
          <FileDrop onFiles={addFiles} accept="image/*" label="Add more images" disabled={busy} />

          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
            {images.map((img, i) => {
              const rot = rotations[img.id] || 0;
              return (
                <div
                  key={img.id}
                  {...{ onDragOver: reorder.onDragOver }}
                  onDrop={reorder.onDrop(i)}
                  onDragStart={reorder.onDragStart(i)}
                  draggable
                >
                  <li className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <div className="flex h-28 items-center justify-center bg-slate-100 dark:bg-slate-800">
                      <img
                        src={thumbUrl(img.id, 240)}
                        alt={img.name}
                        className="max-h-full max-w-full object-contain transition-transform"
                        style={{ transform: `rotate(${rot}deg)` }}
                        loading="lazy"
                      />
                    </div>
                    <div className="flex items-center justify-between gap-1 px-2 py-1.5">
                      <span className="truncate text-xs text-slate-500 dark:text-slate-400" title={img.name}>
                        #{i + 1} {img.name}
                      </span>
                      <span className="flex shrink-0">
                        <button onClick={() => rotate(img.id, -90)} className="rounded p-1 text-slate-400 hover:text-violet-600" aria-label={`Rotate ${img.name} left`}><RotateCcw size={13} /></button>
                        <button onClick={() => rotate(img.id, 90)} className="rounded p-1 text-slate-400 hover:text-violet-600" aria-label={`Rotate ${img.name} right`}><RotateCw size={13} /></button>
                        <button onClick={() => { setImages((c) => c.filter((x) => x.id !== img.id)); deleteFile(img.id).catch(() => {}); }} className="rounded p-1 text-slate-400 hover:text-red-600" aria-label={`Remove ${img.name}`}>x</button>
                      </span>
                    </div>
                  </li>
                </div>
              );
            })}
          </ul>

          <div className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-2">
            <div>
              <label className={LABEL} htmlFor="pagesize">Page size</label>
              <select id="pagesize" value={pageSize} onChange={(e) => setPageSize(e.target.value)} className={`${INPUT} mt-1`}>
                {PAGE_SIZES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className={LABEL} htmlFor="orient">Orientation</label>
              <select id="orient" value={orientation} onChange={(e) => setOrientation(e.target.value)} className={`${INPUT} mt-1`} disabled={pageSize === "image"}>
                <option value="auto">Auto (per image)</option>
                <option value="portrait">Portrait</option>
                <option value="landscape">Landscape</option>
              </select>
            </div>
            <div>
              <label className={LABEL} htmlFor="margin">Margin: {marginMm} mm</label>
              <input id="margin" type="range" min={0} max={40} value={marginMm} onChange={(e) => setMarginMm(+e.target.value)} className="mt-2 w-full accent-violet-600" />
            </div>
            {pageSize === "image" && (
              <div>
                <label className={LABEL} htmlFor="dpi">Image DPI (page size = pixels / DPI)</label>
                <select id="dpi" value={imageDpi} onChange={(e) => setImageDpi(+e.target.value)} className={`${INPUT} mt-1`}>
                  <option value={72}>72 (screen)</option>
                  <option value={96}>96 (default)</option>
                  <option value={150}>150 (print draft)</option>
                  <option value={300}>300 (print)</option>
                </select>
              </div>
            )}
            <div className="sm:col-span-2">
              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <input type="checkbox" checked={recompress} onChange={(e) => setRecompress(e.target.checked)} className="accent-violet-600" />
                Recompress images as JPEG to reduce size (default: off, preserves original quality)
              </label>
              {recompress && (
                <label className="mt-2 block text-xs text-slate-500 dark:text-slate-400" htmlFor="q">
                  JPEG quality: {quality}
                  <input id="q" type="range" min={30} max={95} value={quality} onChange={(e) => setQuality(+e.target.value)} className="ml-3 w-48 accent-violet-600" />
                </label>
              )}
            </div>
          </div>

          <button onClick={convert} disabled={busy} className={BTN_PRIMARY}>
            <FileImage size={16} /> Convert {images.length} image{images.length > 1 ? "s" : ""} to PDF
          </button>
        </>
      )}

      <TaskPanel taskId={taskId} onDismiss={() => setTaskId(null)} />
    </div>
  );
}
