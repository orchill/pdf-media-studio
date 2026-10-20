/** Shared Tailwind class constants (avoids @apply pitfalls). */
export const CARD =
  "rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900";
export const BTN_BASE =
  "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-slate-900 disabled:opacity-50 disabled:pointer-events-none";
export const BTN_PRIMARY = `${BTN_BASE} bg-violet-600 text-white hover:bg-violet-500`;
export const BTN_SECONDARY = `${BTN_BASE} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700`;
export const BTN_DANGER = `${BTN_BASE} bg-red-600/10 text-red-700 hover:bg-red-600/20 dark:text-red-400`;
export const BTN_GHOST = `${BTN_BASE} text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-slate-800`;
export const INPUT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100";
export const LABEL = "block text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400";
export const SECTION_TITLE = "text-lg font-semibold text-slate-900 dark:text-slate-100";
export const BADGE =
  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";
