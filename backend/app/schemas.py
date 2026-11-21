"""Schémas d'entrée / sortie de l'API Dari (source de la documentation OpenAPI).

Validation des entrées : longueurs bornées, notes entre 0 et 20 au centième, dates cohérentes.
"""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

Texte = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")]
NoteSur20 = Annotated[Decimal, Field(ge=0, le=20, max_digits=4, decimal_places=2)]
Annee = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{4}$")]


class Sortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Référentiels ------------------------------------------------------------------------------

class PromotionIn(BaseModel):
    code: Code
    libelle: Texte
    annee_universitaire: Annee


class PromotionOut(Sortie):
    id: int
    code: str
    libelle: str
    annee_universitaire: str


class EtudiantIn(BaseModel):
    matricule: Code
    nom: Texte
    prenom: Texte
    email: EmailStr
    promotion_id: int


class EtudiantOut(Sortie):
    id: int
    matricule: str
    nom: str
    prenom: str
    email: str
    promotion_id: int
    user_id: int | None


class ImportCsvOut(BaseModel):
    crees: int
    ignores: int
    erreurs: list[str]


class EnseignantIn(BaseModel):
    nom: Texte
    prenom: Texte
    email: EmailStr
    grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None


class EnseignantOut(Sortie):
    id: int
    nom: str
    prenom: str
    email: str
    grade: str | None
    user_id: int | None


class ModuleIn(BaseModel):
    code: Code
    intitule: Texte
    promotion_id: int
    semestre: Literal[1, 2]
    coefficient: Annotated[Decimal, Field(gt=0, le=20, max_digits=4, decimal_places=2)]
    credits: Annotated[int, Field(ge=0, le=30)]
    poids_cc: Annotated[Decimal, Field(ge=0, le=1, max_digits=3, decimal_places=2)] = Decimal("0.40")
    responsable_id: int | None = None


class ModuleOut(Sortie):
    id: int
    code: str
    intitule: str
    promotion_id: int
    semestre: int
    coefficient: Decimal
    credits: int
    poids_cc: Decimal
    responsable_id: int | None


class SalleIn(BaseModel):
    nom: Texte
    capacite: Annotated[int, Field(gt=0, le=2000)]


class SalleOut(Sortie):
    id: int
    nom: str
    capacite: int


# --- Sessions et épreuves ----------------------------------------------------------------------

class SessionExamenIn(BaseModel):
    libelle: Texte
    type: Literal["normale", "rattrapage"]
    semestre: Literal[1, 2]
    promotion_id: int
    session_normale_id: int | None = None
    date_debut: date
    date_fin: date

    @model_validator(mode="after")
    def _dates(self):
        if self.date_fin < self.date_debut:
            raise ValueError("La date de fin précède la date de début.")
        return self


class SessionExamenOut(Sortie):
    id: int
    libelle: str
    type: str
    semestre: int
    promotion_id: int
    session_normale_id: int | None
    date_debut: date
    date_fin: date
    statut: str


class EpreuveIn(BaseModel):
    module_id: int
    date: date
    heure_debut: time
    duree_minutes: Annotated[int, Field(gt=0, le=480)]
    salle_id: int | None = None
    surveillant_ids: list[int] = Field(default_factory=list, max_length=20)


class EpreuveOut(Sortie):
    id: int
    session_id: int
    module_id: int
    date: date
    heure_debut: time
    duree_minutes: int
    salle_id: int | None
    surveillant_ids: list[int]
    sujet_depose: bool


class ConflitOut(BaseModel):
    type: str
    message: str
    epreuve_id: int | None


class SujetOut(Sortie):
    id: int
    epreuve_id: int
    nom_fichier: str
    taille: int
    sha256: str
    depose_le: datetime


# --- Notes -------------------------------------------------------------------------------------

class NoteLigneIn(BaseModel):
    etudiant_id: int
    note_cc: NoteSur20 | None = None
    note_examen: NoteSur20 | None = None
    absent: bool = False


class NotesIn(BaseModel):
    notes: list[NoteLigneIn] = Field(max_length=2000)


class NoteLigneOut(BaseModel):
    etudiant_id: int
    matricule: str
    nom: str
    prenom: str
    note_cc: Decimal | None
    note_examen: Decimal | None
    absent: bool
    moyenne: Decimal | None


class FeuilleNotesOut(BaseModel):
    session_id: int
    module_id: int
    type_session: str
    poids_cc: Decimal
    validee: bool
    verrouillee: bool
    lignes: list[NoteLigneOut]


class EtatModuleOut(BaseModel):
    module: ModuleOut
    notes_saisies: int
    etudiants: int
    validee: bool


# --- Délibérations -----------------------------------------------------------------------------

class CalculIn(BaseModel):
    seuil: Annotated[Decimal, Field(ge=0, le=20)] | None = None
    compensation: bool | None = None


class ResultatModuleOut(BaseModel):
    module_id: int
    code: str
    intitule: str
    coefficient: Decimal
    credits: int
    moyenne: Decimal
    acquis: bool


class ResultatOut(BaseModel):
    etudiant_id: int
    matricule: str
    nom: str
    prenom: str
    moyenne: Decimal
    credits_acquis: int
    decision: str
    modules: list[ResultatModuleOut]


class DeliberationOut(BaseModel):
    id: int
    session_id: int
    statut: str
    seuil: Decimal
    compensation: bool
    calculee_le: datetime
    validee_le: datetime | None
    resultats: list[ResultatOut]


# --- Espace étudiant ---------------------------------------------------------------------------

class ProfilOut(BaseModel):
    user_id: int
    username: str
    role: str
    permissions: list[str]
    etudiant: EtudiantOut | None
    enseignant: EnseignantOut | None


class MesResultatsOut(BaseModel):
    session: SessionExamenOut
    resultat: ResultatOut


# --- Réclamations ------------------------------------------------------------------------------

class ReclamationIn(BaseModel):
    session_id: int
    module_id: int
    motif: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]


class TraitementIn(BaseModel):
    statut: Literal["en_cours", "acceptee", "rejetee"]
    reponse: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    # Réclamation acceptée : nouvelles notes (laisser vide pour garder l'ancienne valeur)
    nouvelle_note_cc: NoteSur20 | None = None
    nouvelle_note_examen: NoteSur20 | None = None

    @model_validator(mode="after")
    def _reponse(self):
        if self.statut in ("acceptee", "rejetee") and not self.reponse:
            raise ValueError("Une réponse motivée est obligatoire pour clore une réclamation.")
        return self


class EvenementOut(Sortie):
    statut: str
    commentaire: str | None
    auteur_id: int | None
    cree_le: datetime


class ReclamationOut(BaseModel):
    id: int
    etudiant_id: int
    etudiant: str
    session_id: int
    module_id: int
    module: str
    motif: str
    statut: str
    reponse: str | None
    cree_le: datetime
    traitee_le: datetime | None
    evenements: list[EvenementOut]


# --- Statistiques ------------------------------------------------------------------------------

class StatModuleOut(BaseModel):
    module_id: int
    code: str
    intitule: str
    moyenne: Decimal | None
    minimum: Decimal | None
    maximum: Decimal | None
    taux_validation: float


class StatsSessionOut(BaseModel):
    session_id: int
    etudiants: int
    taux_reussite: float
    decisions: dict[str, int]
    moyenne_generale: Decimal | None
    distribution: list[int]          # 10 tranches de 2 points : [0, 2[, [2, 4[ ... [18, 20]
    modules: list[StatModuleOut]


class SanteOut(BaseModel):
    status: str
    database: str
    version: str
    environment: str
