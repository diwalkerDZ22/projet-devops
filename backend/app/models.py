"""Tables de Dari, déclarées sur la Base du kit (une seule metadata, un seul autogenerate Alembic).

Notes sur 20, stockées en Numeric(4, 2) : jamais de flottant pour une note.
"""
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth_kit.models import Base, User
from auth_kit.sqltypes import UTCDateTime

NOTE = Numeric(4, 2)

TYPES_SESSION = ("normale", "rattrapage")
STATUTS_SESSION = ("ouverte", "deliberee", "publiee")
DECISIONS = ("admis", "rattrapage", "ajourne")
STATUTS_RECLAMATION = ("deposee", "en_cours", "acceptee", "rejetee")


class Promotion(Base):
    """Une promotion d'une année universitaire, par exemple « L3 Informatique 2026-2027 »."""
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    libelle: Mapped[str] = mapped_column(String(120))
    annee_universitaire: Mapped[str] = mapped_column(String(9))   # 2026-2027

    etudiants: Mapped[list["Etudiant"]] = relationship(back_populates="promotion")
    modules: Mapped[list["Module"]] = relationship(back_populates="promotion")


class Etudiant(Base):
    __tablename__ = "etudiants"

    id: Mapped[int] = mapped_column(primary_key=True)
    matricule: Mapped[str] = mapped_column(String(32), unique=True)
    nom: Mapped[str] = mapped_column(String(80))
    prenom: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    promotion_id: Mapped[int] = mapped_column(ForeignKey("promotions.id", ondelete="RESTRICT"), index=True)
    # Compte rattaché quand l'étudiant s'inscrit avec cet email (vérifié par le kit)
    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"), unique=True)

    promotion: Mapped[Promotion] = relationship(back_populates="etudiants")


class Enseignant(Base):
    __tablename__ = "enseignants"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(80))
    prenom: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    grade: Mapped[str | None] = mapped_column(String(40))
    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"), unique=True)


class Module(Base):
    __tablename__ = "modules"
    __table_args__ = (
        CheckConstraint("poids_cc >= 0 AND poids_cc <= 1", name="ck_modules_poids_cc"),
        CheckConstraint("coefficient > 0", name="ck_modules_coefficient"),
        CheckConstraint("credits >= 0", name="ck_modules_credits"),
        CheckConstraint("semestre IN (1, 2)", name="ck_modules_semestre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    intitule: Mapped[str] = mapped_column(String(160))
    promotion_id: Mapped[int] = mapped_column(ForeignKey("promotions.id", ondelete="RESTRICT"), index=True)
    semestre: Mapped[int] = mapped_column(Integer)
    coefficient: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    credits: Mapped[int] = mapped_column(Integer)
    # Part du contrôle continu dans la moyenne du module (0.40 = 40 % CC, 60 % examen)
    poids_cc: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.40"))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("enseignants.id", ondelete="SET NULL"))

    promotion: Mapped[Promotion] = relationship(back_populates="modules")
    responsable: Mapped[Enseignant | None] = relationship()


class Salle(Base):
    __tablename__ = "salles"
    __table_args__ = (CheckConstraint("capacite > 0", name="ck_salles_capacite"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(60), unique=True)
    capacite: Mapped[int] = mapped_column(Integer)


class SessionExamen(Base):
    """Session S1, S2 ou rattrapage d'une promotion.

    Une session de rattrapage pointe vers la session normale qu'elle rattrape : seuls les
    étudiants ajournés en « rattrapage » par la délibération de cette session y sont concernés.
    """
    __tablename__ = "sessions_examen"
    __table_args__ = (
        CheckConstraint("type IN ('normale', 'rattrapage')", name="ck_sessions_type"),
        CheckConstraint("statut IN ('ouverte', 'deliberee', 'publiee')", name="ck_sessions_statut"),
        CheckConstraint("semestre IN (1, 2)", name="ck_sessions_semestre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(16))
    semestre: Mapped[int] = mapped_column(Integer)
    promotion_id: Mapped[int] = mapped_column(ForeignKey("promotions.id", ondelete="RESTRICT"), index=True)
    session_normale_id: Mapped[int | None] = mapped_column(ForeignKey("sessions_examen.id", ondelete="RESTRICT"))
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String(16), default="ouverte")
    cree_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    promotion: Mapped[Promotion] = relationship()
    session_normale: Mapped["SessionExamen | None"] = relationship(remote_side=[id])


epreuve_surveillants = Table(
    "epreuve_surveillants",
    Base.metadata,
    Column("epreuve_id", ForeignKey("epreuves.id", ondelete="CASCADE"), primary_key=True),
    Column("enseignant_id", ForeignKey("enseignants.id", ondelete="CASCADE"), primary_key=True),
)


class Epreuve(Base):
    __tablename__ = "epreuves"
    __table_args__ = (
        UniqueConstraint("session_id", "module_id", name="uq_epreuves_session_module"),
        CheckConstraint("duree_minutes > 0", name="ck_epreuves_duree"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions_examen.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date)
    heure_debut: Mapped[time] = mapped_column(Time)
    duree_minutes: Mapped[int] = mapped_column(Integer)
    salle_id: Mapped[int | None] = mapped_column(ForeignKey("salles.id", ondelete="SET NULL"))

    session: Mapped[SessionExamen] = relationship()
    module: Mapped[Module] = relationship()
    salle: Mapped[Salle | None] = relationship()
    surveillants: Mapped[list[Enseignant]] = relationship(secondary=epreuve_surveillants)


class Sujet(Base):
    """Sujet d'une épreuve (PDF). Confidentiel : responsable du module et scolarité uniquement."""
    __tablename__ = "sujets"

    id: Mapped[int] = mapped_column(primary_key=True)
    epreuve_id: Mapped[int] = mapped_column(ForeignKey("epreuves.id", ondelete="CASCADE"), unique=True)
    nom_fichier: Mapped[str] = mapped_column(String(255))
    chemin: Mapped[str] = mapped_column(String(255))        # relatif à UPLOAD_DIR
    taille: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    depose_par_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))
    depose_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class Note(Base):
    """Notes d'un étudiant dans un module pour une session.

    Session normale : contrôle continu + examen. Session de rattrapage : seule note_examen est
    saisie (note de l'épreuve de rattrapage) ; le CC est repris de la session normale.
    """
    __tablename__ = "notes"
    __table_args__ = (
        UniqueConstraint("session_id", "module_id", "etudiant_id", name="uq_notes_session_module_etudiant"),
        CheckConstraint("note_cc IS NULL OR (note_cc >= 0 AND note_cc <= 20)", name="ck_notes_cc"),
        CheckConstraint("note_examen IS NULL OR (note_examen >= 0 AND note_examen <= 20)", name="ck_notes_examen"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions_examen.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="RESTRICT"))
    etudiant_id: Mapped[int] = mapped_column(ForeignKey("etudiants.id", ondelete="CASCADE"), index=True)
    note_cc: Mapped[Decimal | None] = mapped_column(NOTE)
    note_examen: Mapped[Decimal | None] = mapped_column(NOTE)
    absent: Mapped[bool] = mapped_column(Boolean, default=False)
    saisie_par_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))
    modifie_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    etudiant: Mapped[Etudiant] = relationship()
    module: Mapped[Module] = relationship()


class NoteHistorique(Base):
    """Trace de chaque modification d'une note : qui, quand, avant / après, pourquoi."""
    __tablename__ = "notes_historique"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    ancien_cc: Mapped[Decimal | None] = mapped_column(NOTE)
    ancien_examen: Mapped[Decimal | None] = mapped_column(NOTE)
    nouveau_cc: Mapped[Decimal | None] = mapped_column(NOTE)
    nouveau_examen: Mapped[Decimal | None] = mapped_column(NOTE)
    motif: Mapped[str] = mapped_column(String(255))
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class ValidationModule(Base):
    """Validation des notes d'un module par son responsable : plus de saisie ensuite."""
    __tablename__ = "validations_module"

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions_examen.id", ondelete="CASCADE"), primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), primary_key=True)
    valide_par_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))
    valide_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class Deliberation(Base):
    __tablename__ = "deliberations"
    __table_args__ = (CheckConstraint("statut IN ('brouillon', 'validee')", name="ck_deliberations_statut"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions_examen.id", ondelete="CASCADE"), unique=True)
    statut: Mapped[str] = mapped_column(String(16), default="brouillon")
    seuil: Mapped[Decimal] = mapped_column(NOTE)
    compensation: Mapped[bool] = mapped_column(Boolean)
    calculee_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    calculee_par_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))
    validee_le: Mapped[datetime | None] = mapped_column(UTCDateTime())
    validee_par_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))

    session: Mapped[SessionExamen] = relationship()
    resultats: Mapped[list["Resultat"]] = relationship(
        back_populates="deliberation", cascade="all, delete-orphan", order_by="Resultat.id",
    )


class Resultat(Base):
    """Décision du jury pour un étudiant dans une délibération."""
    __tablename__ = "resultats"
    __table_args__ = (
        UniqueConstraint("deliberation_id", "etudiant_id", name="uq_resultats_deliberation_etudiant"),
        CheckConstraint("decision IN ('admis', 'rattrapage', 'ajourne')", name="ck_resultats_decision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    deliberation_id: Mapped[int] = mapped_column(ForeignKey("deliberations.id", ondelete="CASCADE"), index=True)
    etudiant_id: Mapped[int] = mapped_column(ForeignKey("etudiants.id", ondelete="CASCADE"))
    moyenne: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    credits_acquis: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))

    deliberation: Mapped[Deliberation] = relationship(back_populates="resultats")
    etudiant: Mapped[Etudiant] = relationship()
    modules: Mapped[list["ResultatModule"]] = relationship(
        back_populates="resultat", cascade="all, delete-orphan", order_by="ResultatModule.id",
    )


class ResultatModule(Base):
    __tablename__ = "resultats_module"

    id: Mapped[int] = mapped_column(primary_key=True)
    resultat_id: Mapped[int] = mapped_column(ForeignKey("resultats.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"))
    moyenne: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    acquis: Mapped[bool] = mapped_column(Boolean)

    resultat: Mapped[Resultat] = relationship(back_populates="modules")
    module: Mapped[Module] = relationship()


class Reclamation(Base):
    __tablename__ = "reclamations"
    __table_args__ = (
        CheckConstraint(
            "statut IN ('deposee', 'en_cours', 'acceptee', 'rejetee')", name="ck_reclamations_statut",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    etudiant_id: Mapped[int] = mapped_column(ForeignKey("etudiants.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions_examen.id", ondelete="CASCADE"))
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"))
    motif: Mapped[str] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(16), default="deposee")
    reponse: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    traitee_le: Mapped[datetime | None] = mapped_column(UTCDateTime())
    traitee_par_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))

    etudiant: Mapped[Etudiant] = relationship()
    module: Mapped[Module] = relationship()
    session: Mapped[SessionExamen] = relationship()
    evenements: Mapped[list["ReclamationEvenement"]] = relationship(
        back_populates="reclamation", cascade="all, delete-orphan", order_by="ReclamationEvenement.id",
    )


class ReclamationEvenement(Base):
    """Historique d'une réclamation : dépôt, prise en charge, décision."""
    __tablename__ = "reclamations_evenements"

    id: Mapped[int] = mapped_column(primary_key=True)
    reclamation_id: Mapped[int] = mapped_column(ForeignKey("reclamations.id", ondelete="CASCADE"), index=True)
    statut: Mapped[str] = mapped_column(String(16))
    commentaire: Mapped[str | None] = mapped_column(Text)
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    reclamation: Mapped[Reclamation] = relationship(back_populates="evenements")
