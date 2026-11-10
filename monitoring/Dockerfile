FROM docker:29-cli AS docker-cli

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Ajoute uniquement le client Docker, pas un second moteur Docker
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

# Utilisateur non-root
RUN groupadd --system --gid 10002 monitor \
    && useradd --system --uid 10002 --gid monitor \
        --no-create-home --shell /usr/sbin/nologin monitor

COPY --chown=monitor:monitor serverMoni.py .

USER monitor

CMD ["python", "-u", "serverMoni.py"]
