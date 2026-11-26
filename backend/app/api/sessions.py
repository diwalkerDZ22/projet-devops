"""Sessions d'examen (S1, S2, rattrapage), épreuves avec détection de conflits, sujets confidentiels."""
import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import roles
from app.api.deps import AppContext, a_permission, enregistrer, obtenir, supprimer, verifier_responsable
from app.errors import ApiError
from app.models import Enseignant, Epreuve, Etudiant, Module, Promotion, Salle, SessionExamen, Sujet
from app.schemas import ConflitOut, EpreuveIn, EpreuveOut, SessionExamenIn, SessionExamenOut, SujetOut
from app.services.planning import Creneau, detecter_conflits
from auth_kit.models import User

logger = logging.getLogger(__name__)


def epreuve_out(epreuve: Epreuve, sujet_depose: bool) -> EpreuveOut:
    return EpreuveOut(
        id=epreuve.id, session_id=epreuve.session_id, module_id=epreuve.module_id, date=epreuve.date,
        heure_debut=epreuve.heure_debut, duree_minutes=epreuve.duree_minutes, salle_id=epreuve.salle_id,
        surveillant_ids=sorted(s.id for s in epreuve.surveillants), sujet_depose=sujet_depose,
    )


def _creneau(epreuve: Epreuve) -> Creneau:
    return Creneau(
        epreuve.id, f"{epreuve.module.code} ({epreuve.session.libelle})", epreuve.date, epreuve.heure_debut,
        epreuve.duree_minutes, epreuve.salle_id, epreuve.module.promotion_id,
        frozenset(s.id for s in epreuve.surveillants),
    )


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter(tags=["sessions et planning"])
    lire = [Depends(ctx.kit.require_permission(roles.REFERENTIEL_LIRE))]
    gerer = [Depends(ctx.kit.require_permission(roles.PLANNING_GERER))]
    get_db = ctx.get_db
    upload_dir = ctx.settings.UPLOAD_DIR

    # --- Sessions --------------------------------------------------------------------------

    def verifier_session(db: Session, data: SessionExamenIn) -> None:
        obtenir(db, Promotion, data.promotion_id, "promotion_introuvable")
        if data.type == "rattrapage":
            if data.session_normale_id is None:
                raise ApiError("session_normale_requise")
            normale = obtenir(db, SessionExamen, data.session_normale_id, "session_introuvable")
            if normale.type != "normale" or normale.promotion_id != data.promotion_id or normale.semestre != data.semestre:
                raise ApiError("session_normale_requise")
        elif data.session_normale_id is not None:
            raise ApiError("validation_error", fields={"session_normale_id": "Réservé aux sessions de rattrapage."})

    @router.get("/sessions", response_model=list[SessionExamenOut], dependencies=lire)
    def lister_sessions(promotion_id: int | None = None, db: Session = Depends(get_db)):
        query = select(SessionExamen).order_by(SessionExamen.date_debut.desc())
        if promotion_id is not None:
            query = query.where(SessionExamen.promotion_id == promotion_id)
        return db.scalars(query).all()

    @router.get("/sessions/{session_id}", response_model=SessionExamenOut, dependencies=lire)
    def lire_session(session_id: int, db: Session = Depends(get_db)):
        return obtenir(db, SessionExamen, session_id, "session_introuvable")

    @router.post("/sessions", response_model=SessionExamenOut, status_code=201, dependencies=gerer)
    def creer_session(data: SessionExamenIn, db: Session = Depends(get_db)):
        verifier_session(db, data)
        session = SessionExamen(**data.model_dump(), statut="ouverte")
        db.add(session)
        enregistrer(db)
        return session

    @router.put("/sessions/{session_id}", response_model=SessionExamenOut, dependencies=gerer)
    def modifier_session(session_id: int, data: SessionExamenIn, db: Session = Depends(get_db)):
        session = obtenir(db, SessionExamen, session_id, "session_introuvable")
        if session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        verifier_session(db, data)
        for champ, valeur in data.model_dump().items():
            setattr(session, champ, valeur)
        enregistrer(db)
        return session

    @router.delete("/sessions/{session_id}", status_code=204, dependencies=gerer)
    def supprimer_session(session_id: int, db: Session = Depends(get_db)):
        session = obtenir(db, SessionExamen, session_id, "session_introuvable")
        if session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        supprimer(db, session)

    # --- Épreuves --------------------------------------------------------------------------

    def _appliquer(db: Session, session: SessionExamen, epreuve: Epreuve, data: EpreuveIn) -> JSONResponse | None:
        """Renseigne l'épreuve ; renvoie une réponse 409 avec la liste des conflits s'il y en a."""
        module = obtenir(db, Module, data.module_id, "module_introuvable")
        if module.promotion_id != session.promotion_id or module.semestre != session.semestre:
            raise ApiError("module_hors_session")
        salle = obtenir(db, Salle, data.salle_id, "salle_introuvable") if data.salle_id is not None else None
        surveillants = [obtenir(db, Enseignant, i, "enseignant_introuvable") for i in dict.fromkeys(data.surveillant_ids)]

        nouvelle = Creneau(
            epreuve.id, module.code, data.date, data.heure_debut, data.duree_minutes, data.salle_id,
            module.promotion_id, frozenset(s.id for s in surveillants),
        )
        existantes = [_creneau(e) for e in db.scalars(select(Epreuve).where(Epreuve.date == data.date))]
        effectif = db.scalar(select(func.count(Etudiant.id)).where(Etudiant.promotion_id == module.promotion_id)) or 0
        conflits = detecter_conflits(nouvelle, existantes, salle.capacite if salle else None, effectif)
        if conflits:
            db.rollback()
            return JSONResponse(status_code=409, content={
                "code": "conflit_planning",
                "message": "Conflit de planning : " + " ".join(c.message for c in conflits),
                "conflits": [ConflitOut(**c.__dict__).model_dump() for c in conflits],
            })
        epreuve.module_id, epreuve.date, epreuve.heure_debut = module.id, data.date, data.heure_debut
        epreuve.duree_minutes, epreuve.salle_id, epreuve.surveillants = data.duree_minutes, data.salle_id, surveillants
        return None

    def _sujet_depose(db: Session, epreuve_id: int) -> bool:
        return db.scalar(select(Sujet.id).where(Sujet.epreuve_id == epreuve_id)) is not None

    @router.get("/sessions/{session_id}/epreuves", response_model=list[EpreuveOut], dependencies=lire)
    def lister_epreuves(session_id: int, db: Session = Depends(get_db)):
        obtenir(db, SessionExamen, session_id, "session_introuvable")
        epreuves = db.scalars(
            select(Epreuve).where(Epreuve.session_id == session_id).order_by(Epreuve.date, Epreuve.heure_debut)
        ).all()
        deposes = set(db.scalars(select(Sujet.epreuve_id).where(Sujet.epreuve_id.in_([e.id for e in epreuves]))))
        return [epreuve_out(e, e.id in deposes) for e in epreuves]

    @router.post(
        "/sessions/{session_id}/epreuves", response_model=EpreuveOut, status_code=201, dependencies=gerer,
        responses={409: {"description": "Conflit de planning (salle, surveillant, promotion, capacité)"}},
    )
    def creer_epreuve(session_id: int, data: EpreuveIn, db: Session = Depends(get_db)):
        session = obtenir(db, SessionExamen, session_id, "session_introuvable")
        if session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        epreuve = Epreuve(session_id=session.id)
        if (conflit := _appliquer(db, session, epreuve, data)) is not None:
            return conflit
        db.add(epreuve)
        enregistrer(db)
        return epreuve_out(epreuve, False)

    @router.put("/epreuves/{epreuve_id}", response_model=EpreuveOut, dependencies=gerer)
    def modifier_epreuve(epreuve_id: int, data: EpreuveIn, db: Session = Depends(get_db)):
        epreuve = obtenir(db, Epreuve, epreuve_id, "epreuve_introuvable")
        if epreuve.session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        if (conflit := _appliquer(db, epreuve.session, epreuve, data)) is not None:
            return conflit
        enregistrer(db)
        return epreuve_out(epreuve, _sujet_depose(db, epreuve.id))

    @router.delete("/epreuves/{epreuve_id}", status_code=204, dependencies=gerer)
    def supprimer_epreuve(epreuve_id: int, db: Session = Depends(get_db)):
        epreuve = obtenir(db, Epreuve, epreuve_id, "epreuve_introuvable")
        if epreuve.session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        supprimer(db, epreuve)

    # --- Sujets (confidentiels) ------------------------------------------------------------

    deposer = [Depends(ctx.kit.require_permission(roles.SUJETS_DEPOSER))]

    @router.post("/epreuves/{epreuve_id}/sujet", response_model=SujetOut, status_code=201, dependencies=deposer)
    async def deposer_sujet(
        epreuve_id: int, fichier: UploadFile = File(...),
        user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db),
    ):
        """PDF uniquement. Remplace le sujet déjà déposé. Réservé au responsable du module et à la scolarité."""
        epreuve = obtenir(db, Epreuve, epreuve_id, "epreuve_introuvable")
        verifier_responsable(db, user, epreuve.module, roles.PLANNING_GERER)
        limite = ctx.settings.MAX_UPLOAD_MB * 1024 * 1024
        contenu = await fichier.read(limite + 1)
        if len(contenu) > limite:
            raise ApiError("fichier_trop_gros")
        if not contenu.startswith(b"%PDF-"):
            raise ApiError("fichier_invalide")

        upload_dir.mkdir(parents=True, exist_ok=True)
        nom_stockage = f"sujet-{epreuve.id}-{uuid.uuid4().hex}.pdf"   # jamais le nom fourni par le client
        (upload_dir / nom_stockage).write_bytes(contenu)

        sujet = db.scalar(select(Sujet).where(Sujet.epreuve_id == epreuve.id))
        ancien = sujet.chemin if sujet else None
        if sujet is None:
            sujet = Sujet(epreuve_id=epreuve.id)
            db.add(sujet)
        sujet.nom_fichier = (fichier.filename or "sujet.pdf")[-255:]
        sujet.chemin, sujet.taille = nom_stockage, len(contenu)
        sujet.sha256, sujet.depose_par_id = hashlib.sha256(contenu).hexdigest(), user.id
        enregistrer(db)
        if ancien:
            (upload_dir / ancien).unlink(missing_ok=True)
        logger.info("Sujet déposé : epreuve=%s user=%s taille=%s", epreuve.id, user.id, len(contenu))
        return sujet

    @router.get("/epreuves/{epreuve_id}/sujet", response_class=FileResponse, dependencies=deposer)
    def telecharger_sujet(epreuve_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        epreuve = obtenir(db, Epreuve, epreuve_id, "epreuve_introuvable")
        verifier_responsable(db, user, epreuve.module, roles.PLANNING_GERER)
        sujet = db.scalar(select(Sujet).where(Sujet.epreuve_id == epreuve.id))
        if sujet is None or not (upload_dir / sujet.chemin).is_file():
            raise ApiError("sujet_introuvable")
        logger.info("Sujet consulté : epreuve=%s user=%s", epreuve.id, user.id)
        return FileResponse(upload_dir / sujet.chemin, media_type="application/pdf", filename=sujet.nom_fichier)

    @router.get("/epreuves/{epreuve_id}/sujet/infos", response_model=SujetOut, dependencies=deposer)
    def infos_sujet(epreuve_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        epreuve = obtenir(db, Epreuve, epreuve_id, "epreuve_introuvable")
        if not a_permission(user, roles.PLANNING_GERER):
            verifier_responsable(db, user, epreuve.module, roles.PLANNING_GERER)
        sujet = db.scalar(select(Sujet).where(Sujet.epreuve_id == epreuve.id))
        if sujet is None:
            raise ApiError("sujet_introuvable")
        return sujet

    return router
