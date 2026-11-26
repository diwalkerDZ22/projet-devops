"""Référentiels : promotions, étudiants (avec import CSV), enseignants, modules, salles.

Lecture : referentiel:lire. Écriture : referentiel:gerer.
"""
import csv
import io

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import roles
from app.api.deps import AppContext, enregistrer, obtenir, supprimer
from app.errors import ApiError
from app.models import Enseignant, Etudiant, Module, Promotion, Salle
from app.schemas import (
    EnseignantIn,
    EnseignantOut,
    EtudiantIn,
    EtudiantOut,
    ImportCsvOut,
    ModuleIn,
    ModuleOut,
    PromotionIn,
    PromotionOut,
    SalleIn,
    SalleOut,
)

COLONNES_CSV = ("matricule", "nom", "prenom", "email")


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter(tags=["référentiels"])
    lire = [Depends(ctx.kit.require_permission(roles.REFERENTIEL_LIRE))]
    gerer = [Depends(ctx.kit.require_permission(roles.REFERENTIEL_GERER))]
    get_db = ctx.get_db

    def crud(prefix: str, model, schema_in, schema_out, code_absent: str, order_by, verifier=None):
        """Routes CRUD standard d'un référentiel."""

        @router.get(f"/{prefix}", response_model=list[schema_out], dependencies=lire, name=f"lister_{prefix}")
        def lister(db: Session = Depends(get_db)):
            return db.scalars(select(model).order_by(order_by)).all()

        @router.get(f"/{prefix}/{{id_}}", response_model=schema_out, dependencies=lire, name=f"lire_{prefix}")
        def lire_un(id_: int, db: Session = Depends(get_db)):
            return obtenir(db, model, id_, code_absent)

        @router.post(f"/{prefix}", response_model=schema_out, status_code=201, dependencies=gerer, name=f"creer_{prefix}")
        def creer(data: schema_in, db: Session = Depends(get_db)):
            if verifier:
                verifier(db, data)
            objet = model(**data.model_dump())
            db.add(objet)
            enregistrer(db)
            return objet

        @router.put(f"/{prefix}/{{id_}}", response_model=schema_out, dependencies=gerer, name=f"modifier_{prefix}")
        def modifier(id_: int, data: schema_in, db: Session = Depends(get_db)):
            objet = obtenir(db, model, id_, code_absent)
            if verifier:
                verifier(db, data)
            for champ, valeur in data.model_dump().items():
                setattr(objet, champ, valeur)
            enregistrer(db)
            return objet

        @router.delete(f"/{prefix}/{{id_}}", status_code=204, dependencies=gerer, name=f"supprimer_{prefix}")
        def supprimer_un(id_: int, db: Session = Depends(get_db)):
            supprimer(db, obtenir(db, model, id_, code_absent))

    def verifier_promotion(db: Session, data) -> None:
        obtenir(db, Promotion, data.promotion_id, "promotion_introuvable")

    def verifier_module(db: Session, data: ModuleIn) -> None:
        verifier_promotion(db, data)
        if data.responsable_id is not None:
            obtenir(db, Enseignant, data.responsable_id, "enseignant_introuvable")

    # L'import CSV est déclaré avant les routes /etudiants/{id_} pour ne pas être masqué
    @router.post("/etudiants/import", response_model=ImportCsvOut, dependencies=gerer)
    async def importer_etudiants(promotion_id: int, fichier: UploadFile = File(...), db: Session = Depends(get_db)):
        """CSV avec en-tête matricule,nom,prenom,email (séparateur , ou ;). Les matricules existants sont ignorés."""
        obtenir(db, Promotion, promotion_id, "promotion_introuvable")
        contenu = await fichier.read(2 * 1024 * 1024 + 1)
        if len(contenu) > 2 * 1024 * 1024:
            raise ApiError("fichier_trop_gros")
        try:
            texte = contenu.decode("utf-8-sig")
            lecteur = csv.DictReader(io.StringIO(texte), dialect=csv.Sniffer().sniff(texte.split("\n", 1)[0], ",;"))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ApiError("csv_invalide") from exc
        if lecteur.fieldnames is None or not set(COLONNES_CSV) <= {c.strip().lower() for c in lecteur.fieldnames}:
            raise ApiError("csv_invalide", message=f"Colonnes attendues : {', '.join(COLONNES_CSV)}.")

        existants = set(db.scalars(select(Etudiant.matricule)))
        emails = set(db.scalars(select(Etudiant.email)))
        crees, ignores, erreurs = 0, 0, []
        for numero, ligne in enumerate(lecteur, start=2):
            ligne = {(k or "").strip().lower(): (v or "").strip() for k, v in ligne.items()}
            try:
                data = EtudiantIn(promotion_id=promotion_id, **{c: ligne.get(c, "") for c in COLONNES_CSV})
            except ValidationError as exc:
                erreurs.append(f"Ligne {numero} : {exc.errors()[0]['loc'][0]} invalide")
                continue
            if data.matricule in existants or data.email.lower() in emails:
                ignores += 1
                continue
            db.add(Etudiant(**data.model_dump()))
            existants.add(data.matricule)
            emails.add(data.email.lower())
            crees += 1
        if erreurs:
            db.rollback()
            return ImportCsvOut(crees=0, ignores=ignores, erreurs=erreurs[:50])
        enregistrer(db)
        return ImportCsvOut(crees=crees, ignores=ignores, erreurs=[])

    crud("promotions", Promotion, PromotionIn, PromotionOut, "promotion_introuvable", Promotion.code)
    crud("etudiants", Etudiant, EtudiantIn, EtudiantOut, "etudiant_introuvable", Etudiant.nom, verifier_promotion)
    crud("enseignants", Enseignant, EnseignantIn, EnseignantOut, "enseignant_introuvable", Enseignant.nom)
    crud("modules", Module, ModuleIn, ModuleOut, "module_introuvable", Module.code, verifier_module)
    crud("salles", Salle, SalleIn, SalleOut, "salle_introuvable", Salle.nom)
    return router
