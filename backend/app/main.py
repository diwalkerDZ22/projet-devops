"""Application Dari : gestion des examens du département d'informatique.

    cd backend
    python -m uvicorn --factory app.main:create_app --reload     # Swagger : http://127.0.0.1:8000/docs

Assemble auth-kit (comptes, connexion, rôles), les routes métier et l'observabilité.
Aucun état global : create_app() peut être appelée plusieurs fois (tests).
"""
from dataclasses import replace

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from app import roles
from app.api import notes, referentiels, resultats, sessions, stats
from app.api.deps import AppContext
from app.config import AppSettings
from app.errors import ERREURS
from app.observability import configurer_logs, installer_observabilite
from auth_kit import CSRF_HEADER, AuthKit, AuthSettings, EmailTemplates
from auth_kit.adapters import ConsoleEmailSender, HibpBreachChecker, LimitsRateLimiter, ResendEmailSender
from auth_kit.db import create_engine_from_url, session_dependency
from auth_kit.ports import EmailSender

DESCRIPTION = """
API de gestion des examens du département d'informatique (thème 3 du mini-projet DevOps).

Cycle couvert : référentiels, sessions S1 / S2 / rattrapage, planning des épreuves, sujets,
saisie et validation des notes, délibération, procès-verbaux, publication, réclamations,
statistiques.

Authentification : `POST /auth/token` puis `Authorization: Bearer <access_token>`.
Toutes les erreurs ont le format `{"code", "message"}`.
"""


def _email(settings: AppSettings) -> EmailSender:
    if settings.EMAIL_BACKEND == "console":
        return ConsoleEmailSender()
    return ResendEmailSender(settings.RESEND_API_KEY, f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>")


def create_app(
    settings: AppSettings | None = None,
    auth_settings: AuthSettings | None = None,
    email: EmailSender | None = None,
    rate_limiter=None,
) -> FastAPI:
    settings = settings or AppSettings()
    auth_settings = auth_settings or AuthSettings(_env_file=".env")
    configurer_logs(settings.LOG_LEVEL, settings.LOG_FORMAT)

    engine = create_engine_from_url(settings.DATABASE_URL, sslmode=settings.DATABASE_SSLMODE, pool_pre_ping=True)
    get_db = session_dependency(sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))

    kit = AuthKit(
        settings=auth_settings,
        get_db=get_db,
        email=email or _email(settings),
        rate_limiter=rate_limiter or LimitsRateLimiter(settings.RATE_LIMIT_STORAGE_URI),
        breach_checker=HibpBreachChecker() if settings.PASSWORD_BREACH_CHECK else None,
        templates=replace(EmailTemplates(), brand_color="#0f3d5e"),
        permissions=roles.PERMISSIONS,
        roles=roles.ROLES,
        errors=ERREURS,
    )

    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, description=DESCRIPTION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", CSRF_HEADER],
    )
    installer_observabilite(app)
    kit.install(app, error_scope="app")   # format {"code", "message"} sur toute l'API

    ctx = AppContext(kit=kit, get_db=get_db, settings=settings)
    for module in (stats, referentiels, sessions, notes, resultats):
        app.include_router(module.build_router(ctx))

    app.state.ctx = ctx
    app.state.engine = engine
    return app
