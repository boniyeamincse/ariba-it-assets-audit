FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . /app/
COPY --chown=root:root infa/entrypoint.sh /usr/local/bin/ag-audit-entrypoint
RUN chmod 0555 /usr/local/bin/ag-audit-entrypoint \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app

USER app:app
EXPOSE 8000
STOPSIGNAL SIGTERM

ENTRYPOINT ["/usr/local/bin/ag-audit-entrypoint"]
