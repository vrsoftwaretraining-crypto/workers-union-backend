"""Windows desktop launcher for the Workers Union App.

This does NOT reimplement the app for desktop -- it opens the same Flask
web app in a native, chrome-less window (via pywebview), so double-clicking
a desktop icon feels like a normal Windows application while reusing 100%
of the existing web backend.

Usage (on the machine that runs it):
    pip install pywebview
    python launcher.py            # opens a window pointing at APP_URL

To ship a single .exe to end users, build it on a Windows machine with:
    pip install pyinstaller pywebview
    pyinstaller --noconsole --onefile --name "WorkersUnionApp" launcher.py
The resulting dist/WorkersUnionApp.exe can be pinned to the Start Menu /
Desktop like any other Windows app.

Set APP_URL to your deployed HTTPS server, or to http://127.0.0.1:8000 if
you also bundle/run the Flask server locally (see run_local_server.py).
"""
import os

import webview

APP_URL = os.environ.get("WORKERS_UNION_APP_URL", "https://yourunion.example.com")

if __name__ == "__main__":
    webview.create_window("Workers Union App", APP_URL, width=1280, height=800, min_size=(900, 600))
    webview.start()
