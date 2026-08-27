"""Optional: run the Flask app locally (e.g. bundled inside the .exe) and
then open the desktop window against it. Useful for a fully offline/local
deployment where each union runs its own server on one office PC.
"""
import threading
import time

import webview

from app import app as flask_app


def _run_flask():
    flask_app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)


if __name__ == "__main__":
    t = threading.Thread(target=_run_flask, daemon=True)
    t.start()
    time.sleep(1.5)  # give Flask a moment to bind the port
    webview.create_window("Workers Union App", "http://127.0.0.1:8000", width=1280, height=800)
    webview.start()
