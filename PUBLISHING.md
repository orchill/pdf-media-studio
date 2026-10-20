# Publishing to GitHub (safely)

This project is **safe to publish as-is**. There are no API keys, tokens or
secrets baked into the source — the app talks to YouTube/PDF libraries without
any accounts. Still, read the one rule below before your first push.

## The one rule: never commit your runtime data folder

When you run the app it creates two folders next to the code:

| Folder / file        | What it contains                                   | Secret? |
|----------------------|----------------------------------------------------|---------|
| `data/cookies.txt`   | **Your real YouTube cookies** (your login session) | **YES — treat like a password** |
| `data/`              | Thumbnails, task history, temp files               | Personal, don't share |
| `outputs/`           | Your downloaded videos / converted PDFs            | Personal |
| `config.json`        | Your local settings (paths, port)                  | No, but machine-specific |

The included `.gitignore` already blocks all of these — **don't delete those
lines**. If you ever see `data/cookies.txt` in `git status`, stop.

## First-time publish (Windows, step by step)

1. **Create an empty repo on GitHub**
   - Go to <https://github.com/new>
   - Name it (e.g. `pdf-media-studio`), keep it **Private** unless you want it public
   - Do **NOT** tick "Add a README" / ".gitignore" / "license" (we already have them)

2. **Push from the project folder** (extract the ZIP first), in PowerShell/CMD:

   ```bat
   cd path\to\pdf-media-studio
   git init -b main
   git add .
   git status          :: sanity check — no data/, outputs/ or config.json listed
   git commit -m "Initial release: PDF toolbox + media downloader"
   git remote add origin https://github.com/YOUR_USERNAME/pdf-media-studio.git
   git push -u origin main
   ```

   GitHub will ask you to sign in on first push (browser popup) — that's it.

3. **Post-push check**

   ```bat
   git ls-files | findstr /i "cookie config.json data outputs"
   ```

   Expected output: only source files like `backend/app/services/cookie_store.py`
   and `backend/tests/test_cookies.py` (code, not your cookies) plus
   `config.example.json`. If `data/` or `outputs/` ever appear here, remove them
   before continuing:

   ```bat
   git rm -r --cached data outputs config.json
   git commit -m "Remove runtime data from repo"
   ```

## Pushing future updates

```bat
git add .
git status        :: glance for data/ or outputs/ — should never appear
git commit -m "Describe your change"
git push
```

## Extra hygiene (optional but recommended)

- **GitHub secret scanning** (free on public repos) will warn you if a cookie
  ever leaks — don't ignore its alerts. If a real cookie file is ever pushed:
  1. Clear cookies in the app (Cookies tab → Clear), and sign out / re-login on
     YouTube to invalidate that session,
  2. rewrite history (`git filter-repo`) or just delete the repo and re-push,
  3. only then re-publish.
- **Keep the repo private** if you don't want your fork/usage visible; the MIT
  license only applies to whatever you choose to publish.
- If you change code and it starts failing for others, keep the honest
  "Testing & verification status" section in `README.md` up to date.
