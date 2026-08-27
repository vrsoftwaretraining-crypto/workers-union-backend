# Windows Desktop Shortcut for Workers Union App

You asked for a "Windows application" that is really the browser-based web
app, made to feel like a native desktop app. Two ways to do that:

## Option A — simplest: pin the browser tab
Open the deployed URL in Chrome/Edge → menu → "Install as app" (or "Create
shortcut" → check "Open as window"). This needs zero extra code and updates
automatically whenever you redeploy the web app.

## Option B — branded .exe (this folder)
`launcher.py` opens the same web app in a native window using `pywebview`,
so it looks like a normal Windows program with its own icon.

On a Windows machine with Python installed:
    pip install pywebview pyinstaller
    set WORKERS_UNION_APP_URL=https://yourunion.example.com
    pyinstaller --noconsole --onefile --icon app.ico --name "WorkersUnionApp" launcher.py

This produces `dist/WorkersUnionApp.exe` — copy it to the office PC, pin it
to the Start Menu/Desktop, done. This step must be run on Windows (or with
a Windows cross-build tool) — it cannot be produced from this sandbox,
which has no Windows toolchain or internet access.

## Option C — fully local/offline union server
Use `run_local_server.py` instead of `launcher.py` if a union wants to run
the whole app locally on one office PC with no internet dependency at all
(data then only backs up/restores from that one PC — remember to schedule
regular Backups from Admin → Backup).
