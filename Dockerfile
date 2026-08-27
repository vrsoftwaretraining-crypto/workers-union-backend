FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p instance logs backups uploads

ENV FLASK_ENV=production
EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn_conf.py", "wsgi:app"]
