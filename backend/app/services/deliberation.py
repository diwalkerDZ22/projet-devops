"""Délibération : relie le moteur de calcul (services/calcul.py) aux tables.

Sans FastAPI : lève ApiError, que les routes laissent remonter.
"""
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    Deliberation,
    Etudiant,
    Module,
    Note,
    Resultat,
    ResultatModule,
    SessionExamen,
    ValidationModule,
)
from app.observability import DUREE_CALCUL_DELIBERATION
from app.services.calcul import ErreurCalcul, NotesModule, Regles, calculer_etudiant

logger = logging.getLogger(__name__)


def modules_de_session(db: Session, session: SessionExamen) -> list[Module]:
    return list(db.scalars(
        select(Module)
        .where(Module.promotion_id == session.promotion_id, Module.semestre == session.semestre)
        .order_by(Module.code)
    ))


def deliberation_validee(db: Session, session_id: int) -> Deliberation | None:
    return db.scalar(select(Deliberation).where(
        Deliberation.session_id == session_id, Deliberation.statut == "validee",
    ))


def modules_a_rattraper(db: Session, session: SessionExamen) -> dict[int, set[int]]:
    """Session de rattrapage : {etudiant_id: {module_id non acquis}} pour les étudiants en rattrapage."""
    parent = deliberation_validee(db, session.session_normale_id) if session.session_normale_id else None
    if parent is None:
        raise ApiError("session_normale_non_deliberee")
    concernes: dict[int, set[int]] = {}
    for resultat in parent.resultats:
        if resultat.decision == "rattrapage":
            concernes[resultat.etudiant_id] = {rm.module_id for rm in resultat.modules if not rm.acquis}
    return concernes


def etudiants_concernes(db: Session, session: SessionExamen, module_id: int | None = None) -> list[Etudiant]:
    """Étudiants qui composent dans cette session (et ce module, si précisé)."""
    query = select(Etudiant).where(Etudiant.promotion_id == session.promotion_id).order_by(Etudiant.nom, Etudiant.prenom)
    etudiants = list(db.scalars(query))
    if session.type == "normale":
        return etudiants
    concernes = modules_a_rattraper(db, session)
    return [
        e for e in etudiants
        if e.id in concernes and (module_id is None or module_id in concernes[e.id])
    ]


def _notes(db: Session, session_id: int) -> dict[tuple[int, int], Note]:
    return {(n.etudiant_id, n.module_id): n for n in db.scalars(select(Note).where(Note.session_id == session_id))}


def _notes_etudiant(
    db: Session, session: SessionExamen, etudiant_id: int, modules: list[Module],
    notes: dict[tuple[int, int], Note], notes_normale: dict[tuple[int, int], Note],
) -> list[NotesModule]:
    resultat = []
    for module in modules:
        if session.type == "normale":
            note = notes.get((etudiant_id, module.id))
            resultat.append(NotesModule(
                module.id, module.coefficient, module.credits, module.poids_cc,
                note.note_cc if note else None, note.note_examen if note else None,
            ))
        else:
            normale = notes_normale.get((etudiant_id, module.id))
            ratt = notes.get((etudiant_id, module.id))
            resultat.append(NotesModule(
                module.id, module.coefficient, module.credits, module.poids_cc,
                normale.note_cc if normale else None, normale.note_examen if normale else None,
                note_rattrapage=(ratt.note_examen if ratt and ratt.note_examen is not None else None),
            ))
    return resultat


def modules_valides(db: Session, session_id: int) -> set[int]:
    return set(db.scalars(select(ValidationModule.module_id).where(ValidationModule.session_id == session_id)))


def modules_attendus(db: Session, session: SessionExamen) -> list[Module]:
    """Modules dont les notes doivent être validées avant de délibérer."""
    modules = modules_de_session(db, session)
    if session.type == "normale":
        return modules
    a_rattraper = set().union(*modules_a_rattraper(db, session).values()) if session.session_normale_id else set()
    return [m for m in modules if m.id in a_rattraper]


def _calculer(db: Session, session: SessionExamen, regles: Regles, etudiants: list[Etudiant]) -> list[Resultat]:
    modules = modules_de_session(db, session)
    notes = _notes(db, session.id)
    notes_normale = _notes(db, session.session_normale_id) if session.session_normale_id else {}
    resultats = []
    for etudiant in etudiants:
        try:
            calcul = calculer_etudiant(
                _notes_etudiant(db, session, etudiant.id, modules, notes, notes_normale), session.type, regles,
            )
        except ErreurCalcul as exc:
            logger.warning("Calcul impossible pour la session %s : %s", session.id, exc)
            raise ApiError("calcul_impossible") from exc
        resultats.append(Resultat(
            etudiant_id=etudiant.id,
            moyenne=calcul.moyenne,
            credits_acquis=calcul.credits_acquis,
            decision=calcul.decision,
            modules=[ResultatModule(module_id=d.module_id, moyenne=d.moyenne, acquis=d.acquis) for d in calcul.modules],
        ))
    return resultats


def calculer(db: Session, session: SessionExamen, user_id: int, regles: Regles) -> Deliberation:
    """Calcule (ou recalcule) la délibération en brouillon de la session."""
    if session.statut != "ouverte":
        raise ApiError("session_verrouillee")
    attendus = modules_attendus(db, session)
    if not attendus or {m.id for m in attendus} - modules_valides(db, session.id):
        raise ApiError("modules_non_valides")

    debut = time.perf_counter()
    resultats = _calculer(db, session, regles, etudiants_concernes(db, session))
    delib = db.scalar(select(Deliberation).where(Deliberation.session_id == session.id))
    if delib is None:
        delib = Deliberation(session_id=session.id)
        db.add(delib)
    delib.statut = "brouillon"
    delib.seuil = regles.seuil
    delib.compensation = regles.compensation
    delib.calculee_le = datetime.now(timezone.utc)
    delib.calculee_par_id = user_id
    # Supprimer les anciens résultats avant d'insérer les nouveaux (unicité délibération + étudiant)
    delib.resultats.clear()
    db.flush()
    delib.resultats.extend(resultats)
    db.commit()
    duree = time.perf_counter() - debut
    DUREE_CALCUL_DELIBERATION.observe(duree)
    logger.info("Délibération calculée : session=%s etudiants=%s duree_ms=%.1f", session.id, len(resultats), duree * 1000)
    return delib


def valider(db: Session, delib: Deliberation, user_id: int) -> Deliberation:
    if delib.statut == "validee":
        raise ApiError("deliberation_deja_validee")
    delib.statut = "validee"
    delib.validee_le = datetime.now(timezone.utc)
    delib.validee_par_id = user_id
    delib.session.statut = "deliberee"   # verrouille la saisie des notes
    db.commit()
    logger.info("Délibération validée : session=%s par user=%s", delib.session_id, user_id)
    return delib


def recalculer_etudiant(db: Session, delib: Deliberation, etudiant: Etudiant) -> Resultat:
    """Après une réclamation acceptée : met à jour la décision d'un seul étudiant."""
    regles = Regles(seuil=Decimal(delib.seuil), compensation=delib.compensation)
    [nouveau] = _calculer(db, delib.session, regles, [etudiant])
    ancien = next((r for r in delib.resultats if r.etudiant_id == etudiant.id), None)
    if ancien is None:
        delib.resultats.append(nouveau)
        return nouveau
    ancien.moyenne, ancien.credits_acquis, ancien.decision = nouveau.moyenne, nouveau.credits_acquis, nouveau.decision
    # Mise à jour en place : ne pas déplacer les objets de `nouveau`, qui serait alors inséré lui aussi
    par_module = {rm.module_id: rm for rm in nouveau.modules}
    for rm in ancien.modules:
        rm.moyenne, rm.acquis = par_module[rm.module_id].moyenne, par_module[rm.module_id].acquis
    return ancien
