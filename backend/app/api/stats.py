"""Santé de l'application et métriques Prometheus."""
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import AppContext
from app.models import Reclamation
from app.observability import BASE_DISPONIBLE, RECLAMATIONS_EN_ATTENTE, metrics_response
from app.schemas import SanteOut

logger = logging.getLogger(__name__)


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    get_db = ctx.get_db

    @router.get("/health", response_model=SanteOut, tags=["exploitation"], responses={503: {"model": SanteOut}})
    def sante(db: Session = Depends(get_db)):
        """Contrôle de santé : l'application répond et la base aussi (utilisé par Docker et le déploiement)."""
        try:
            db.execute(text("SELECT 1"))
            base = "ok"
        except Exception:   # noqa: BLE001 : toute erreur de base rend l'application indisponible
            logger.exception("Healthcheck : base indisponible")
            base = "indisponible"
        BASE_DISPONIBLE.set(1 if base == "ok" else 0)
        corps = SanteOut(
            status="ok" if base == "ok" else "degrade", database=base,
            version=ctx.settings.APP_VERSION, environment=ctx.settings.ENVIRONMENT,
        )
        return JSONResponse(corps.model_dump(), status_code=200 if base == "ok" else 503)

    @router.get("/metrics", include_in_schema=False)
    def metrics(db: Session = Depends(get_db)):
        """Métriques Prometheus ; les jauges métier sont lues en base à chaque collecte."""
        try:
            en_attente = db.scalar(select(func.count(Reclamation.id)).where(Reclamation.statut.in_(("deposee", "en_cours"))))
            RECLAMATIONS_EN_ATTENTE.set(en_attente or 0)
            BASE_DISPONIBLE.set(1)
        except Exception:   # noqa: BLE001
            logger.exception("Métriques : base indisponible")
            BASE_DISPONIBLE.set(0)
        return metrics_response()

    return router
