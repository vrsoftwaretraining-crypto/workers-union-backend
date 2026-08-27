import multiprocessing
import os

# Render (and most cloud platforms) assign a port at runtime via the PORT
# env var and expect the app to listen on 0.0.0.0, not just localhost.
# Binding to 127.0.0.1 (the old default here) makes the app invisible to
# Render's router -- the deploy would "succeed" but every request would
# time out with "no open ports detected".
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 60
accesslog = "-"   # stdout, so Render's log viewer captures it (a local
errorlog = "-"    # logs/ file wouldn't survive a container restart anyway)
loglevel = "info"
