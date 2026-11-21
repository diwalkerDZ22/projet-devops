"""Réglages de l'application Dari (sans préfixe).

Les réglages de l'authentification sont lus séparément par AuthSettings (préfixe AUTH_).
Aucun secret n'a de valeur par défaut : tout vient de l'environnement ou du fichier .env.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Dari - Examens du département d'informatique"
    APP_VERSION: str = "dev"          # remplacé par le SHA du commit à la construction de l'image
    ENVIRONMENT: str = "dev"          # dev, test, staging, production

    DATABASE_URL: str
    # "require" pour une base distante (Supabase), "disable" pour le Postgres de Docker Compose
    DATABASE_SSLMODE: str | None = "require"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"          # json (exploitation) ou text (lecture humaine en dev)

    # console : les mails sont écrits dans les logs (DEV UNIQUEMENT) ; resend : envoi réel
    EMAIL_BACKEND: str = "console"
    RESEND_API_KEY: str = ""
    MAIL_FROM: str = "onboarding@resend.dev"
    MAIL_FROM_NAME: str = "Dari"

    RATE_LIMIT_STORAGE_URI: str = "memory://"
    PASSWORD_BREACH_CHECK: bool = False

    # Dossier des sujets d'examen déposés (volume Docker sauvegardé en production)
    UPLOAD_DIR: Path = Path("data/uploads")
    MAX_UPLOAD_MB: int = 10

    # Règles de délibération par défaut (modifiables par session)
    SEUIL_ADMISSION: float = 10.0
    COMPENSATION: bool = True
