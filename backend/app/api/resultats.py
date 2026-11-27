"""Délibérations (calcul, validation par le jury, PV), publication et espace étudiant."""
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import roles
from app.api.deps import AppContext, enregistrer, enseignant_de, etudiant_de, obtenir, permissions
from app.errors import ApiError
from app.models import Deliberation, Enseignant, Etudiant, Resultat, SessionExamen
from app.schemas import (
    CalculIn,
    DeliberationOut,
    EnseignantOut,
    EtudiantOut,
    MesResultatsOut,
    ProfilOut,
    ResultatModuleOut,
    ResultatOut,
    SessionExamenOut,
)
from app.services import deliberation as service
from app.services.calcul import Regles
from app.services.pdf import proces_verbal, releve_notes
from auth_kit.models import Role, User

logger = logging.getLogger(__name__)


def resultat_out(r: Resultat) -> ResultatOut:
    return ResultatOut(
        etudiant_id=r.etudiant_id, matricule=r.etudiant.matricule, nom=r.etudiant.nom, prenom=r.etudiant.prenom,
        moyenne=r.moyenne, credits_acquis=r.credits_acquis, decision=r.decision,
        modules=[
            ResultatModuleOut(
                module_id=rm.module_id, code=rm.module.code, intitule=rm.module.intitule,
                coefficient=rm.module.coefficient, credits=rm.module.credits, moyenne=rm.moyenne, acquis=rm.acquis,
            )
            for rm in r.modules
        ],
    )


def deliberation_out(d: Deliberation) -> DeliberationOut:
    resultats = sorted(d.resultats, key=lambda r: (r.etudiant.nom, r.etudiant.prenom))
    return DeliberationOut(
        id=d.id, session_id=d.session_id, statut=d.statut, seuil=d.seuil, compensation=d.compensation,
        calculee_le=d.calculee_le, validee_le=d.validee_le, resultats=[resultat_out(r) for r in resultats],
    )


def _pdf(contenu: bytes, nom: str) -> Response:
    return Response(contenu, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{nom}"'})


def rattacher(db: Session, user: User) -> tuple[Etudiant | None, Enseignant | None]:
    """Rattache le compte à la fiche étudiant ou enseignant qui porte le même email.

    L'email a été vérifié par le kit (lien envoyé à l'inscription) : seul son propriétaire peut
    s'en prévaloir. Un compte « user » est alors promu étudiant ou enseignant.
    """
    etudiant, enseignant = etudiant_de(db, user), enseignant_de(db, user)
    if etudiant or enseignant:
        return etudiant, enseignant
    email = user.email.lower()
    etudiant = db.scalar(select(Etudiant).where(func.lower(Etudiant.email) == email, Etudiant.user_id.is_(None)))
    enseignant = None if etudiant else db.scalar(
        select(Enseignant).where(func.lower(Enseignant.email) == email, Enseignant.user_id.is_(None))
    )
    fiche, role = (etudiant, "etudiant") if etudiant else (enseignant, "enseignant") if enseignant else (None, None)
    if fiche is None:
        return None, None
    fiche.user_id = user.id
    if user.role.name == "user":
        user.role = db.scalar(select(Role).where(Role.name == role))
    enregistrer(db)
    logger.info("Compte rattaché : user=%s %s=%s", user.id, role, fiche.id)
    return etudiant, enseignant


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    get_db = ctx.get_db
    gerer = [Depends(ctx.kit.require_permission(roles.DELIBERATION_GERER))]

    def _session_et_delib(db: Session, session_id: int) -> tuple[SessionExamen, Deliberation]:
        session = obtenir(db, SessionExamen, session_id, "session_introuvable")
        delib = db.scalar(select(Deliberation).where(Deliberation.session_id == session.id))
        if delib is None:
            raise ApiError("deliberation_introuvable")
        return session, delib

    # --- Délibérations ---------------------------------------------------------------------

    @router.post("/sessions/{session_id}/deliberation", response_model=DeliberationOut, dependencies=gerer, tags=["délibérations"])
    def calculer(session_id: int, data: CalculIn, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Calcule (ou recalcule) la délibération en brouillon. Tous les modules doivent être validés."""
        session = obtenir(db, SessionExamen, session_id, "session_introuvable")
        regles = Regles(
            seuil=data.seuil if data.seuil is not None else Decimal(str(ctx.settings.SEUIL_ADMISSION)),
            compensation=data.compensation if data.compensation is not None else ctx.settings.COMPENSATION,
        )
        return deliberation_out(service.calculer(db, session, user.id, regles))

    @router.get(
        "/sessions/{session_id}/deliberation", response_model=DeliberationOut, tags=["délibérations"],
        dependencies=[Depends(ctx.kit.require_permission(roles.STATS_CONSULTER))],
    )
    def lire(session_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        _, delib = _session_et_delib(db, session_id)
        perms = permissions(user)
        if roles.DELIBERATION_GERER not in perms and roles.DELIBERATION_VALIDER not in perms and delib.statut != "validee":
            raise ApiError("deliberation_introuvable")   # un enseignant ne voit pas les brouillons
        return deliberation_out(delib)

    @router.post(
        "/sessions/{session_id}/deliberation/validation", response_model=DeliberationOut, tags=["délibérations"],
        dependencies=[Depends(ctx.kit.require_permission(roles.DELIBERATION_VALIDER))],
    )
    def valider(session_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Validation finale par le jury : la session est verrouillée, les notes ne bougent plus."""
        _, delib = _session_et_delib(db, session_id)
        return deliberation_out(service.valider(db, delib, user.id))

    @router.get(
        "/sessions/{session_id}/deliberation/pv.pdf", response_class=Response, tags=["délibérations"],
        dependencies=[Depends(ctx.kit.require_permission(roles.STATS_CONSULTER))],
    )
    def pv(session_id: int, db: Session = Depends(get_db)):
        session, delib = _session_et_delib(db, session_id)
        resultats = sorted(delib.resultats, key=lambda r: (r.etudiant.nom, r.etudiant.prenom))
        return _pdf(proces_verbal(delib, service.modules_de_session(db, session), resultats), f"pv-session-{session.id}.pdf")

    @router.post("/sessions/{session_id}/publication", response_model=SessionExamenOut, dependencies=gerer, tags=["délibérations"])
    def publier(session_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Publie les résultats dans l'espace étudiant. Exige une délibération validée."""
        session, delib = _session_et_delib(db, session_id)
        if delib.statut != "validee":
            raise ApiError("deliberation_non_validee")
        session.statut = "publiee"
        enregistrer(db)
        logger.info("Résultats publiés : session=%s user=%s", session.id, user.id)
        return session

    # --- Espace personnel ------------------------------------------------------------------

    @router.get("/moi", response_model=ProfilOut, tags=["espace personnel"])
    def moi(user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Profil Dari du compte connecté ; rattache le compte à sa fiche au premier appel."""
        etudiant, enseignant = rattacher(db, user)
        return ProfilOut(
            user_id=user.id, username=user.username, role=user.role.name, permissions=sorted(permissions(user)),
            etudiant=EtudiantOut.model_validate(etudiant) if etudiant else None,
            enseignant=EnseignantOut.model_validate(enseignant) if enseignant else None,
        )

    consulter = [Depends(ctx.kit.require_permission(roles.RESULTATS_CONSULTER))]

    def _mes_resultats(db: Session, user: User) -> list[tuple[SessionExamen, Resultat]]:
        etudiant = etudiant_de(db, user)
        if etudiant is None:
            raise ApiError("profil_etudiant_absent")
        lignes = db.execute(
            select(SessionExamen, Resultat)
            .join(Deliberation, Deliberation.session_id == SessionExamen.id)
            .join(Resultat, Resultat.deliberation_id == Deliberation.id)
            .where(Resultat.etudiant_id == etudiant.id, SessionExamen.statut == "publiee")
            .order_by(SessionExamen.date_debut)
        ).all()
        return [(s, r) for s, r in lignes]

    @router.get("/moi/resultats", response_model=list[MesResultatsOut], dependencies=consulter, tags=["espace personnel"])
    def mes_resultats(user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Résultats publiés de l'étudiant connecté, et seulement les siens."""
        return [
            MesResultatsOut(session=SessionExamenOut.model_validate(s), resultat=resultat_out(r))
            for s, r in _mes_resultats(db, user)
        ]

    @router.get("/moi/releves/{session_id}.pdf", response_class=Response, dependencies=consulter, tags=["espace personnel"])
    def mon_releve(session_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        for session, resultat in _mes_resultats(db, user):
            if session.id == session_id:
                return _pdf(releve_notes(session, resultat), f"releve-{resultat.etudiant.matricule}-{session.id}.pdf")
        raise ApiError("resultats_non_publies")

    return router
