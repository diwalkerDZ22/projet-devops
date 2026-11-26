# Image de l'API Dari. Construction en deux étapes : dépendances compilées à part, image finale minimale.
#   docker build -t dari-backend --build-arg APP_VERSION=$(git rev-parse --short HEAD) backend

FROM python:3.13-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
# Le kit (src/auth_kit) est installé avec le code ci-dessous : on retire la ligne "-e ." ici
RUN grep -v "^-e" requirements.txt > /tmp/requirements.txt \
    && python -m venv /venv \
    && /venv/bin/pip install -r /tmp/requirements.txt

FROM python:3.13-slim
ARG APP_VERSION=dev
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    UPLOAD_DIR=/data/uploads
WORKDIR /app
COPY --from=deps /venv /venv
COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

# Utilisateur sans privilèges ; /data est le volume des sujets déposés
RUN useradd --system --uid 10001 dari && mkdir -p /data/uploads && chown -R dari /data
USER dari
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

# --proxy-headers : IP réelle du client derrière Nginx (rate-limit, journaux).
# Un seul processus : métriques Prometheus et rate-limit en mémoire sont propres au processus.
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
