import { useEffect, useState } from "react";
import {
  CheckCircle2, Cookie, FileText, Globe, KeyRound, Loader2, Lock,
  ShieldAlert, TestTube2, Trash2, XCircle,
} from "lucide-react";
import {
  clearCookiePrefs, saveCookiePrefs, testCookiePrefs,
} from "../api";
import { useToast } from "../ctx";
import { CookieStatus, CookieTestResult } from "../types";
import {
  BTN_DANGER, BTN_PRIMARY, BTN_SECONDARY, CARD, INPUT, LABEL,
} from "../ui";

type Mode = "none" | "file" | "browser";

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex gap-2">
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-100 text-[10px] font-bold text-violet-700 dark:bg-violet-500/20 dark:text-violet-300">
        {n}
      </span>
      <span>{children}</span>
    </li>
  );
}

export default function CookiesPanel({
  status, refresh,
}: {
  status: CookieStatus | null;
  refresh: () => Promise<CookieStatus>;
}) {
  const toast = useToast();
  const [mode, setMode] = useState<Mode>("none");
  const [browser, setBrowser] = useState("chrome");
  const [text, setText] = useState("");
  const [domain, setDomain] = useState(".youtube.com");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [result, setResult] = useState<CookieTestResult | null>(null);

  // keep the selected mode in sync with the server state
  useEffect(() => {
    if (status) setMode(status.source);
  }, [status?.source]); // eslint-disable-line react-hooks/exhaustive-deps

  const active = status && status.source !== "none";

  const save = async () => {
    setSaving(true);
    setResult(null);
    try {
      if (mode === "none") {
        await saveCookiePrefs({ source: "none" });
        toast.push("info", "Cookie sign-in disabled - downloads run signed out.");
      } else if (mode === "browser") {
        await saveCookiePrefs({ source: "browser", browser });
        toast.push("success", `Will use cookies from ${browser}.`);
      } else {
        await saveCookiePrefs({ source: "file", cookies_text: text, domain });
        toast.push("success", "Cookies saved locally - sign-in enabled.");
        setText("");
      }
      await refresh();
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setSaving(false);
    }
  };

  const runTest = async () => {
    setTesting(true);
    setResult(null);
    try {
      const r = await testCookiePrefs();
      setResult(r);
      if (r.ok) toast.push("success", "Cookie sign-in works.");
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setTesting(false);
    }
  };

  const clear = async () => {
    if (!confirm("Delete the stored cookies file and disable sign-in?")) return;
    setClearing(true);
    try {
      await clearCookiePrefs();
      setText("");
      setResult(null);
      await refresh();
      toast.push("info", "Cookies cleared.");
    } catch (e: any) {
      toast.push("error", e.message);
    } finally {
      setClearing(false);
    }
  };

  const statusText = !status
    ? "Loading..."
    : status.source === "file" && status.file_present
      ? `Active - cookie file with ${status.cookie_count} cookie${status.cookie_count === 1 ? "" : "s"} for ${(status.domains || []).join(", ") || "your sites"}`
      : status.source === "browser"
        ? `Active - reading cookies from ${status.browser} on every download (close ${status.browser} fully first)`
        : "Not configured - downloads run signed out";

  return (
    <div className="space-y-4" data-testid="cookies-panel">
      {/* current state */}
      <div className={`${CARD} flex flex-wrap items-center gap-3 p-4`}>
        <Cookie size={22} className={active ? "text-emerald-500" : "text-slate-400"} />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            YouTube sign-in status
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">{statusText}</p>
        </div>
        {active && (
          <button onClick={clear} disabled={clearing} className={`${BTN_DANGER} py-1.5 text-xs`}>
            {clearing ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
            Clear cookies
          </button>
        )}
      </div>

      {/* explanation */}
      <div className={`${CARD} space-y-3 p-4 text-sm leading-relaxed text-slate-600 dark:text-slate-300`}>
        <h3 className="font-semibold text-slate-900 dark:text-slate-100">
          Why does YouTube ask to &quot;confirm you&apos;re not a bot&quot;?
        </h3>
        <p>
          When YouTube sees automated, signed-out requests (especially from VPNs or cloud IPs) it
          asks for verification and blocks the download. The reliable, officially supported fix is
          to <strong className="text-slate-800 dark:text-slate-100">sign in with your own
          account</strong>: yt-dlp then sends your session cookies exactly like your browser does.
          This is normal authentication, not a bypass - content you cannot access while signed in
          (private, members-only, DRM) stays inaccessible.
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Two ways to sign in below: let yt-dlp read cookies straight from your browser, or paste
          an exported cookies file.
        </p>
      </div>

      {/* mode selection */}
      <div className={`${CARD} space-y-4 p-4`}>
        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Sign-in method">
          {([
            ["none", "Don't sign in", Globe],
            ["browser", "Use browser cookies", KeyRound],
            ["file", "Paste cookies file", FileText],
          ] as [Mode, string, React.ElementType][]).map(([m, label, Icon]) => (
            <button
              key={m}
              role="radio"
              aria-checked={mode === m}
              onClick={() => setMode(m)}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium ${
                mode === m
                  ? "border-violet-500 bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300"
                  : "border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300"
              }`}
            >
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>

        {mode === "browser" && (
          <div className="space-y-2">
            <label className={LABEL} htmlFor="cookiebrowser">Browser to read cookies from</label>
            <select
              id="cookiebrowser"
              value={browser}
              onChange={(e) => setBrowser(e.target.value)}
              className={INPUT}
            >
              {(status?.supported_browsers || ["chrome", "firefox", "edge"]).map((b) => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
            <ul className="list-disc space-y-1 pl-5 text-xs text-slate-500 dark:text-slate-400">
              <li>Fully close the browser (all windows) before downloading, otherwise its
                cookie database is locked and yt-dlp cannot read it.</li>
              <li>Sign in to youtube.com in that browser at least once, and only select a
                browser you actually use for YouTube.</li>
              <li>On Windows, Chrome/Edge cookies are encrypted per user - run the app under
                the same Windows user as the browser.</li>
            </ul>
          </div>
        )}

        {mode === "file" && (
          <div className="space-y-3">
            <div>
              <label className={LABEL} htmlFor="cookietext">cookies.txt export or Cookie header</label>
              <textarea
                id="cookietext"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={7}
                spellCheck={false}
                autoComplete="off"
                placeholder={"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1900000000\tSID\t...\n\n-- or a single line: --\nVISITOR_INFO1_LIVE=...; SID=...; HSID=..."}
                className={`${INPUT} mt-1 font-mono text-xs`}
              />
            </div>
            <div>
              <label className={LABEL} htmlFor="cookiedomain">
                Cookie domain (only used for header-style input - leave as .youtube.com for YouTube)
              </label>
              <input
                id="cookiedomain"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className={`${INPUT} mt-1 font-mono text-xs`}
              />
            </div>
            <details className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
              <summary className="cursor-pointer font-medium text-slate-700 dark:text-slate-200">
                How do I get my cookies? (2 ways)
              </summary>
              <ol className="mt-2 space-y-2">
                <Step n={1}>
                  Log in to youtube.com in your normal browser.
                </Step>
                <Step n={2}>
                  Install a cookie-export extension such as
                  &quot;Get cookies.txt LOCALLY&quot; (Chrome/Edge/Firefox store).
                </Step>
                <Step n={3}>
                  While on youtube.com, click the extension and export the cookies
                  for the current site.
                </Step>
                <Step n={4}>
                  Open the downloaded .txt file, copy <em>everything</em> and paste it
                  into the box above.
                </Step>
                <Step n={1}>
                  Devtools alternative: F12 &rarr; Network tab &rarr; refresh the page
                  &rarr; click the first request &rarr; under &quot;Request Headers&quot;
                  copy the whole <code>Cookie:</code> value and paste it above.
                </Step>
              </ol>
            </details>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
          <button onClick={save} disabled={saving} className={BTN_PRIMARY}>
            {saving ? <Loader2 size={15} className="animate-spin" /> : <Lock size={15} />}
            Save sign-in settings
          </button>
          <button onClick={runTest} disabled={testing} className={BTN_SECONDARY}>
            {testing ? <Loader2 size={15} className="animate-spin" /> : <TestTube2 size={15} />}
            Test sign-in
          </button>
          {status?.file_present && status.source !== "file" && (
            <span className="text-xs text-slate-400">
              A stored cookies file exists and will be re-used if you select file mode.
            </span>
          )}
        </div>

        {result && (
          <div
            role="status"
            className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm ${
              result.ok
                ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200"
                : "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200"
            }`}
          >
            {result.ok ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <XCircle size={16} className="mt-0.5 shrink-0" />}
            <span className="whitespace-pre-wrap">
              {result.message}
              {result.elapsed_s != null && (
                <span className="ml-1 opacity-70">({result.elapsed_s}s)</span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* privacy */}
      <div className={`${CARD} border-amber-300 p-4 dark:border-amber-800`}>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-400">
          <ShieldAlert size={15} /> Keep your cookies private
        </h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
          <li>Cookies are your login session - anyone holding them can use your YouTube
            account. Treat the cookies file like a password.</li>
          <li>Storage is local only: <code>data/cookies.txt</code> inside the app folder.
            Values are never displayed, logged, or sent anywhere except to the video site itself.</li>
          <li>Use your own account only, and only download content you have the right to
            save. Private, members-only and DRM-protected content stays inaccessible.</li>
          <li>Clear the cookies here before sharing your data folder or screen, and
            re-export fresh cookies if downloads start failing again (they expire).</li>
        </ul>
      </div>
    </div>
  );
}
