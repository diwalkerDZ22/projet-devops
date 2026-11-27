"""Saisie des notes par module et par session, validation par le responsable, historique des modifications.

Règles :
- saisie réservée au responsable du module (notes:saisir) ou à la scolarité (notes:gerer) ;
- plus aucune saisie après validation du module, ni après la délibération (session verrouillée) ;
- en rattrapage, seuls les étudiants qui rattrapent ce module apparaissent, et seule la note
  d'examen est saisie (le CC reste celui de la session normale) ;
- chaque modification est tracée dans notes_historique.
"""
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import roles
from app.api.deps import AppContext, a_permission, enregistrer, enseignant_de, obtenir, verifier_responsable
from app.errors import ApiError
from app.models import Module, Note, NoteHistorique, SessionExamen, ValidationModule
from app.observability import NOTES_SAISIES
from app.schemas import EtatModuleOut, FeuilleNotesOut, ModuleOut, NoteLigneOut, NotesIn
from app.services.calcul import moyenne_module
from app.services.deliberation import etudiants_concernes, modules_attendus
from auth_kit.models import User

logger = logging.getLogger(__name__)


def _contexte(db: Session, session_id: int, module_id: int) -> tuple[SessionExamen, Module]:
    session = obtenir(db, SessionExamen, session_id, "session_introuvable")
    module = obtenir(db, Module, module_id, "module_introuvable")
    if module.promotion_id != session.promotion_id or module.semestre != session.semestre:
        raise ApiError("module_hors_session")
    return session, module


def _validation(db: Session, session_id: int, module_id: int) -> ValidationModule | None:
    return db.get(ValidationModule, (session_id, module_id))


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter(tags=["notes"])
    get_db = ctx.get_db
    saisir = [Depends(ctx.kit.require_permission(roles.REFERENTIEL_LIRE))]

    def _autoriser(db: Session, user: User, module: Module) -> None:
        if not (a_permission(user, roles.NOTES_SAISIR) or a_permission(user, roles.NOTES_GERER)):
            raise ApiError("permission_denied")
        verifier_responsable(db, user, module, roles.NOTES_GERER)

    @router.get("/sessions/{session_id}/modules", response_model=list[EtatModuleOut], dependencies=saisir)
    def etat_modules(session_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Modules de la session avec l'avancement de la saisie. Un enseignant ne voit que ses modules."""
        session = obtenir(db, SessionExamen, session_id, "session_introuvable")
        modules = modules_attendus(db, session)
        if not a_permission(user, roles.NOTES_GERER) and not a_permission(user, roles.DELIBERATION_VALIDER):
            enseignant = enseignant_de(db, user)
            modules = [m for m in modules if enseignant is not None and m.responsable_id == enseignant.id]
        saisies = dict(db.execute(
            select(Note.module_id, func.count(Note.id))
            .where(Note.session_id == session.id, or_(Note.note_examen.is_not(None), Note.absent.is_(True)))
            .group_by(Note.module_id)
        ).all())
        valides = set(db.scalars(select(ValidationModule.module_id).where(ValidationModule.session_id == session.id)))
        return [
            EtatModuleOut(
                module=ModuleOut.model_validate(m), notes_saisies=saisies.get(m.id, 0),
                etudiants=len(etudiants_concernes(db, session, m.id)), validee=m.id in valides,
            )
            for m in modules
        ]

    @router.get("/sessions/{session_id}/modules/{module_id}/notes", response_model=FeuilleNotesOut)
    def feuille(session_id: int, module_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        session, module = _contexte(db, session_id, module_id)
        if not a_permission(user, roles.DELIBERATION_VALIDER):
            _autoriser(db, user, module)
        notes = {n.etudiant_id: n for n in db.scalars(select(Note).where(Note.session_id == session.id, Note.module_id == module.id))}
        notes_cc = {}
        if session.type == "rattrapage":
            notes_cc = {n.etudiant_id: n.note_cc for n in db.scalars(
                select(Note).where(Note.session_id == session.session_normale_id, Note.module_id == module.id)
            )}
        lignes = []
        for e in etudiants_concernes(db, session, module.id):
            note = notes.get(e.id)
            cc = notes_cc.get(e.id) if session.type == "rattrapage" else (note.note_cc if note else None)
            examen = note.note_examen if note else None
            saisie = note is not None and (examen is not None or note.absent)
            lignes.append(NoteLigneOut(
                etudiant_id=e.id, matricule=e.matricule, nom=e.nom, prenom=e.prenom, note_cc=cc,
                note_examen=examen, absent=note.absent if note else False,
                moyenne=moyenne_module(module.poids_cc, cc, examen) if saisie else None,
            ))
        return FeuilleNotesOut(
            session_id=session.id, module_id=module.id, type_session=session.type, poids_cc=module.poids_cc,
            validee=_validation(db, session.id, module.id) is not None, verrouillee=session.statut != "ouverte",
            lignes=lignes,
        )

    @router.put("/sessions/{session_id}/modules/{module_id}/notes", response_model=FeuilleNotesOut)
    def enregistrer_notes(
        session_id: int, module_id: int, data: NotesIn,
        user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db),
    ):
        """Enregistre (crée ou met à jour) les lignes envoyées ; les autres ne changent pas."""
        session, module = _contexte(db, session_id, module_id)
        _autoriser(db, user, module)
        if session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        if _validation(db, session.id, module.id) is not None:
            raise ApiError("module_valide")

        concernes = {e.id for e in etudiants_concernes(db, session, module.id)}
        existantes = {n.etudiant_id: n for n in db.scalars(select(Note).where(Note.session_id == session.id, Note.module_id == module.id))}
        modifiees = 0
        for ligne in data.notes:
            if ligne.etudiant_id not in concernes:
                raise ApiError("etudiant_non_concerne")
            cc = None if session.type == "rattrapage" else ligne.note_cc
            examen = None if ligne.absent else ligne.note_examen
            note = existantes.get(ligne.etudiant_id)
            if note is None:
                note = Note(session_id=session.id, module_id=module.id, etudiant_id=ligne.etudiant_id)
                db.add(note)
                existantes[ligne.etudiant_id] = note
            elif (note.note_cc, note.note_examen, note.absent) == (cc, examen, ligne.absent):
                continue
            ancien_cc, ancien_examen = note.note_cc, note.note_examen
            note.note_cc, note.note_examen, note.absent, note.saisie_par_id = cc, examen, ligne.absent, user.id
            db.flush()
            db.add(NoteHistorique(
                note_id=note.id, ancien_cc=ancien_cc, ancien_examen=ancien_examen,
                nouveau_cc=cc, nouveau_examen=examen, motif="saisie", auteur_id=user.id,
            ))
            modifiees += 1
        enregistrer(db)
        NOTES_SAISIES.inc(modifiees)
        logger.info("Notes enregistrées : session=%s module=%s lignes=%s user=%s", session.id, module.id, modifiees, user.id)
        return feuille(session_id, module_id, user, db)

    @router.post("/sessions/{session_id}/modules/{module_id}/validation", status_code=204)
    def valider_module(session_id: int, module_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Le responsable valide les notes du module : toutes les notes d'examen doivent être saisies."""
        session, module = _contexte(db, session_id, module_id)
        _autoriser(db, user, module)
        if session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        if _validation(db, session.id, module.id) is not None:
            return
        notes = {n.etudiant_id: n for n in db.scalars(select(Note).where(Note.session_id == session.id, Note.module_id == module.id))}
        manquants = [
            e for e in etudiants_concernes(db, session, module.id)
            if e.id not in notes or (notes[e.id].note_examen is None and not notes[e.id].absent)
        ]
        if manquants:
            raise ApiError("validation_error", message=f"{len(manquants)} note(s) d'examen manquante(s).")
        db.add(ValidationModule(session_id=session.id, module_id=module.id, valide_par_id=user.id))
        enregistrer(db)
        logger.info("Module validé : session=%s module=%s user=%s", session.id, module.id, user.id)

    @router.delete(
        "/sessions/{session_id}/modules/{module_id}/validation", status_code=204,
        dependencies=[Depends(ctx.kit.require_permission(roles.NOTES_GERER))],
    )
    def devalider_module(session_id: int, module_id: int, user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db)):
        """Réouverture de la saisie par la scolarité, avant la délibération uniquement."""
        session, module = _contexte(db, session_id, module_id)
        if session.statut != "ouverte":
            raise ApiError("session_verrouillee")
        validation = _validation(db, session.id, module.id)
        if validation is None:
            raise ApiError("module_non_valide")
        db.delete(validation)
        enregistrer(db)
        logger.info("Module dévalidé : session=%s module=%s user=%s", session.id, module.id, user.id)

    @router.get("/notes/{session_id}/{module_id}/{etudiant_id}/historique")
    def historique(
        session_id: int, module_id: int, etudiant_id: int,
        user: User = Depends(ctx.kit.current_user), db: Session = Depends(get_db),
    ) -> list[dict]:
        _, module = _contexte(db, session_id, module_id)
        _autoriser(db, user, module)
        note = db.scalar(select(Note).where(
            Note.session_id == session_id, Note.module_id == module_id, Note.etudiant_id == etudiant_id,
        ))
        if note is None:
            return []
        lignes = db.scalars(select(NoteHistorique).where(NoteHistorique.note_id == note.id).order_by(NoteHistorique.id))
        return [
            {
                "ancien_cc": _txt(h.ancien_cc), "ancien_examen": _txt(h.ancien_examen),
                "nouveau_cc": _txt(h.nouveau_cc), "nouveau_examen": _txt(h.nouveau_examen),
                "motif": h.motif, "auteur_id": h.auteur_id, "cree_le": h.cree_le,
            }
            for h in lignes
        ]

    return router


def _txt(valeur: Decimal | None) -> str | None:
    return None if valeur is None else str(valeur)
