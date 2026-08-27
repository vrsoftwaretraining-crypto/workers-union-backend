import os

# Render (and most cloud platforms) assign a port at runtime via the PORT
# env var and expect the app to listen on 0.0.0.0, not just localhost.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# IMPORTANT: do NOT scale workers by CPU count on small/free-tier hosts.
# Render's Free instance has only 512MB RAM total; each worker is a full
# Python process with Flask+SQLAlchemy loaded (~60-100MB), so cpu_count()*2+1
# workers (often 8-40+ on shared build hosts) blows past the memory limit
# and gets OOM-killed in a crash-restart loop. Default to 2, and let bigger
# paid instances raise it via the WEB_CONCURRENCY env var if needed.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "sync"
timeout = 60
accesslog = "-"   # stdout, so Render's log viewer captures it (a local
errorlog = "-"    # logs/ file wouldn't survive a container restart anyway)
loglevel = "info"
