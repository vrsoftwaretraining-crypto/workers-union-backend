"""Entry point for gunicorn / production WSGI servers.

Example:
    gunicorn -c gunicorn_conf.py wsgi:app
"""
from app import app

if __name__ == "__main__":
    app.run()
