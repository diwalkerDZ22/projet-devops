"""Observabilité : journaux structurés, identifiant de requête, métriques Prometheus.

- Chaque requête reçoit un identifiant (en-tête X-Request-ID repris ou généré), renvoyé dans la
  réponse et présent dans tous les journaux émis pendant la requête.
- GET /metrics expose les métriques HTTP et métier au format Prometheus.
"""
import contextvars
import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from starlette.responses import Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Registre propre à l'application : les tests peuvent créer plusieurs applications sans doublon
REGISTRY = CollectorRegistry()

REQUETES = Counter(
    "dari_http_requests_total", "Requêtes HTTP traitées", ["method", "route", "status"], registry=REGISTRY,
)
DUREE_REQUETES = Histogram(
    "dari_http_request_duration_seconds", "Durée des requêtes HTTP", ["method", "route"], registry=REGISTRY,
)
NOTES_SAISIES = Counter("dari_notes_saisies_total", "Notes saisies ou modifiées", registry=REGISTRY)
DUREE_CALCUL_DELIBERATION = Histogram(
    "dari_deliberation_calcul_seconds", "Durée du calcul d'une délibération", registry=REGISTRY,
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
RECLAMATIONS_EN_ATTENTE = Gauge(
    "dari_reclamations_en_attente", "Réclamations déposées ou en cours de traitement", registry=REGISTRY,
)
BASE_DISPONIBLE = Gauge("dari_database_up", "1 si la base répond au healthcheck", registry=REGISTRY)

_CHAMPS_STANDARD = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        data.update({k: v for k, v in record.__dict__.items() if k not in _CHAMPS_STANDARD and k != "request_id"})
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def configurer_logs(level: str, fmt: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    for name in ("app", "auth_kit"):
        logger = logging.getLogger(name)
        logger.setLevel(level.upper())
        logger.handlers = [handler]


def _route(request: Request) -> str:
    """Gabarit de la route (/sessions/{session_id}) plutôt que l'URL : cardinalité bornée."""
    route = request.scope.get("route")
    return getattr(route, "path", "inconnue")


def installer_observabilite(app: FastAPI) -> None:
    logger = logging.getLogger("app.http")

    @app.middleware("http")
    async def journaliser(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        debut = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duree = time.perf_counter() - debut
            route = _route(request)
            if route != "/metrics":
                REQUETES.labels(request.method, route, str(status)).inc()
                DUREE_REQUETES.labels(request.method, route).observe(duree)
                logger.info(
                    "%s %s %s", request.method, request.url.path, status,
                    extra={"status": status, "duration_ms": round(duree * 1000, 1), "route": route},
                )
            request_id_var.reset(token)


def metrics_response() -> Response:
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
