FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Utilisateur non-root (UID fixe : il doit pouvoir écrire dans mailserver/config/postfix-accounts.cf)
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py index.html ./

USER app

EXPOSE 9000

CMD ["gunicorn", "--bind", "0.0.0.0:9000", "--workers", "2", "--threads", "4", "--access-logfile", "-", "app:app"]
