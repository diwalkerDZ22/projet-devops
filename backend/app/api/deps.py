"""Ce dont les routers ont besoin, assemblé par create_app et passé explicitement (aucun état global)."""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import AppSettings
from app.errors import ApiError
from app.models import Enseignant, Etudiant, Module
from auth_kit import AuthKit
from auth_kit.models import User

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppContext:
    kit: AuthKit
    get_db: Callable[..., Session]
    settings: AppSettings


def permissions(user: User) -> set[str]:
    return {p.code for p in user.role.permissions}


def a_permission(user: User, code: str) -> bool:
    return code in permissions(user)


def obtenir(db: Session, model: type[T], id_: int, code: str) -> T:
    objet = db.get(model, id_)
    if objet is None:
        raise ApiError(code)
    return objet


def enseignant_de(db: Session, user: User) -> Enseignant | None:
    return db.scalar(select(Enseignant).where(Enseignant.user_id == user.id))


def etudiant_de(db: Session, user: User) -> Etudiant | None:
    return db.scalar(select(Etudiant).where(Etudiant.user_id == user.id))


def est_responsable(db: Session, user: User, module: Module) -> bool:
    enseignant = enseignant_de(db, user)
    return enseignant is not None and module.responsable_id == enseignant.id


def verifier_responsable(db: Session, user: User, module: Module, permission_globale: str) -> None:
    """Accès « de ses modules » : responsable du module, ou permission sur tous les modules."""
    if not a_permission(user, permission_globale) and not est_responsable(db, user, module):
        raise ApiError("pas_responsable")


def enregistrer(db: Session) -> None:
    """commit ; une contrainte d'unicité ou de clé étrangère violée devient une 409 lisible."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Détail en DEBUG seulement : PostgreSQL y recopie les valeurs (emails...)
        logger.debug("Contrainte violée : %s", exc.orig)
        raise ApiError("doublon") from exc


def supprimer(db: Session, objet) -> None:
    try:
        db.delete(objet)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError("suppression_impossible") from exc
