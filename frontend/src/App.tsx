import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, CheckCircle2, Combine, FileOutput, FilePlus2, FileStack,
  FolderOutput, History as HistoryIcon, Images, LayoutDashboard, Moon, Scissors,
  Settings as SettingsIcon, ShieldCheck, Sun, Video, X, Zap,
} from "lucide-react";
import { NavContext, ToastContext, Toast, Route, useNav } from "./ctx";
import { systemInfo } from "./api";
import { SystemInfo } from "./types";
import { BTN_GHOST } from "./ui";
import Dashboard from "./pages/Dashboard";
import Merge from "./pages/Merge";
import ImagesToPdf from "./pages/ImagesToPdf";
import Organize from "./pages/Organize";
import Split from "./pages/Split";
import Compress from "./pages/Compress";
import ExtractImages from "./pages/ExtractImages";
import PdfToImages from "./pages/PdfToImages";
import Media from "./pages/Media";
import History from "./pages/History";
import SettingsPage from "./pages/Settings";

// ------------------------------------------------------------------ theme
function useTheme() {
  const [dark, setDark] = useState<boolean>(() => {
    const saved = localStorage.getItem("pms-theme");
    if (saved) return saved === "dark";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("pms-theme", dark ? "dark" : "light");
  }, [dark]);
  return { dark, toggle: () => setDark((d) => !d) };
}

// ------------------------------------------------------------------ toasts
function ToastHost({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="alert"
          className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur
            ${t.kind === "error" ? "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/90 dark:text-red-200"
              : t.kind === "success" ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/90 dark:text-emerald-200"
              : "border-slate-300 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"}`}
        >
          {t.kind === "error" ? <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            : t.kind === "success" ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
            : <ShieldCheck size={16} className="mt-0.5 shrink-0" />}
          <span className="whitespace-pre-wrap">{t.text}</span>
          <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="ml-auto shrink-0 opacity-60 hover:opacity-100">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ nav
const NAV: { id: Route; label: string; icon: React.ElementType; group: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, group: "" },
  { id: "merge", label: "Merge PDFs", icon: Combine, group: "PDF Tools" },
  { id: "images", label: "Images to PDF", icon: Images, group: "PDF Tools" },
  { id: "organize", label: "Organize Pages", icon: FileStack, group: "PDF Tools" },
  { id: "split", label: "Split / Extract", icon: Scissors, group: "PDF Tools" },
  { id: "compress", label: "Compress PDF", icon: Zap, group: "PDF Tools" },
  { id: "extract", label: "Extract Images", icon: FilePlus2, group: "PDF Tools" },
  { id: "toimages", label: "PDF to Images", icon: FileOutput, group: "PDF Tools" },
  { id: "media", label: "Media Downloader", icon: Video, group: "Media" },
  { id: "history", label: "Task History", icon: HistoryIcon, group: "General" },
  { id: "settings", label: "Settings", icon: SettingsIcon, group: "General" },
];

function Sidebar() {
  const { route, navigate } = useNav();
  let lastGroup = "";
  return (
    <nav aria-label="Main navigation" className="hidden w-60 shrink-0 flex-col gap-0.5 overflow-y-auto border-r border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900 md:flex">
      {NAV.map((item) => {
        const showGroup = item.group !== lastGroup;
        lastGroup = item.group;
        const Icon = item.icon;
        const active = route === item.id;
        return (
          <div key={item.id}>
            {showGroup && item.group && (
              <div className="mb-1 mt-4 px-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                {item.group}
              </div>
            )}
            <button
              onClick={() => navigate(item.id)}
              aria-current={active ? "page" : undefined}
              className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors
                ${active
                  ? "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}
            >
              <Icon size={17} className="shrink-0" />
              {item.label}
            </button>
          </div>
        );
      })}
    </nav>
  );
}

function MobileNav() {
  const { route, navigate } = useNav();
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-2 py-2 dark:border-slate-800 dark:bg-slate-900 md:hidden">
      {NAV.map((item) => {
        const Icon = item.icon;
        const active = route === item.id;
        return (
          <button
            key={item.id}
            onClick={() => navigate(item.id)}
            className={`flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium
              ${active ? "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300"
                : "text-slate-600 dark:text-slate-300"}`}
          >
            <Icon size={14} /> {item.label}
          </button>
        );
      })}
    </div>
  );
}

function Header({ dark, toggleTheme }: { dark: boolean; toggleTheme: () => void }) {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  useEffect(() => {
    systemInfo().then(setInfo).catch(() => {});
  }, []);
  return (
    <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600 text-white">
          <FileStack size={17} />
        </div>
        <div>
          <h1 className="text-sm font-bold leading-tight text-slate-900 dark:text-slate-100">
            PDF &amp; Media Studio
          </h1>
          <p className="text-[11px] leading-tight text-slate-500 dark:text-slate-400">
            100% local processing - your files never leave this computer
          </p>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        {info && (
          <button
            onClick={() => navigator.clipboard?.writeText(info.output_dir)}
            title={`Output folder: ${info.output_dir} (click to copy path)`}
            className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 lg:flex"
          >
            <FolderOutput size={14} /> {info.output_dir}
          </button>
        )}
        <button onClick={toggleTheme} className={BTN_GHOST} aria-label="Toggle dark mode" title="Toggle theme">
          {dark ? <Sun size={17} /> : <Moon size={17} />}
        </button>
      </div>
    </header>
  );
}

// ------------------------------------------------------------------ app
export default function App() {
  const { dark, toggle } = useTheme();
  const [route, setRoute] = useState<Route>("dashboard");
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((ts) => [...ts.slice(-4), { id, kind, text }]);
    setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), kind === "error" ? 9000 : 4500);
  }, []);
  const dismiss = useCallback((id: number) => setToasts((ts) => ts.filter((t) => t.id !== id)), []);
  const toastCtx = useMemo(() => ({ toasts, push, dismiss }), [toasts, push, dismiss]);
  const navCtx = useMemo(() => ({ route, navigate: setRoute }), [route]);

  const page = {
    dashboard: <Dashboard />,
    merge: <Merge />,
    images: <ImagesToPdf />,
    organize: <Organize />,
    split: <Split />,
    compress: <Compress />,
    extract: <ExtractImages />,
    toimages: <PdfToImages />,
    media: <Media />,
    history: <History />,
    settings: <SettingsPage />,
  }[route];

  return (
    <NavContext.Provider value={navCtx}>
      <ToastContext.Provider value={toastCtx}>
        <div className="flex h-screen flex-col">
          <Header dark={dark} toggleTheme={toggle} />
          <MobileNav />
          <div className="flex min-h-0 flex-1">
            <Sidebar />
            <main className="min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
              <div className="mx-auto max-w-4xl">{page}</div>
            </main>
          </div>
          <ToastHost toasts={toasts} dismiss={dismiss} />
        </div>
      </ToastContext.Provider>
    </NavContext.Provider>
  );
}
