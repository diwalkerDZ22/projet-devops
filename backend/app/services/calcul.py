"""Moteur de calcul des moyennes et des décisions. Fonctions pures : ni base, ni FastAPI.

Règles (docs/Regles-de-calcul.md) :
- moyenne de module = poids_cc x CC + (1 - poids_cc) x examen, arrondie au centième (demi vers le haut) ;
  une note absente compte 0 ;
- rattrapage : la note de rattrapage remplace l'examen ; on retient la meilleure des deux moyennes ;
- moyenne de semestre = moyenne des moyennes de modules pondérée par les coefficients, arrondie au centième ;
- module acquis si sa moyenne atteint le seuil ; avec compensation, tous les crédits sont acquis
  dès que la moyenne du semestre atteint le seuil ;
- décision : admis si moyenne >= seuil ; sinon rattrapage après une session normale, ajourné après
  un rattrapage.

Tout est en Decimal : 0.1 + 0.2 doit valoir 0.3, et 9.995 s'arrondir à 10.00.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENTIEME = Decimal("0.01")
ZERO = Decimal("0")
VINGT = Decimal("20")


class ErreurCalcul(ValueError):
    """Données incohérentes (coefficients nuls, note hors barème...)."""


@dataclass(frozen=True)
class Regles:
    seuil: Decimal = Decimal("10")
    compensation: bool = True


@dataclass(frozen=True)
class NotesModule:
    module_id: int
    coefficient: Decimal
    credits: int
    poids_cc: Decimal
    note_cc: Decimal | None = None
    note_examen: Decimal | None = None
    # Note de l'épreuve de rattrapage, uniquement pour une délibération de rattrapage
    note_rattrapage: Decimal | None = None


@dataclass(frozen=True)
class ResultatModuleCalcule:
    module_id: int
    moyenne: Decimal
    acquis: bool


@dataclass(frozen=True)
class ResultatCalcule:
    moyenne: Decimal
    credits_acquis: int
    decision: str
    modules: tuple[ResultatModuleCalcule, ...]


def arrondir(valeur: Decimal) -> Decimal:
    return valeur.quantize(CENTIEME, rounding=ROUND_HALF_UP)


def _note(valeur: Decimal | None) -> Decimal:
    if valeur is None:
        return ZERO
    valeur = Decimal(valeur)
    if valeur < ZERO or valeur > VINGT:
        raise ErreurCalcul(f"Note hors barème : {valeur}")
    return valeur


def moyenne_module(poids_cc: Decimal, note_cc: Decimal | None, note_examen: Decimal | None) -> Decimal:
    poids_cc = Decimal(poids_cc)
    if poids_cc < ZERO or poids_cc > 1:
        raise ErreurCalcul(f"Poids du contrôle continu invalide : {poids_cc}")
    return arrondir(poids_cc * _note(note_cc) + (1 - poids_cc) * _note(note_examen))


def moyenne_retenue(notes: NotesModule) -> Decimal:
    """Moyenne du module ; avec un rattrapage, la meilleure des deux."""
    normale = moyenne_module(notes.poids_cc, notes.note_cc, notes.note_examen)
    if notes.note_rattrapage is None:
        return normale
    return max(normale, moyenne_module(notes.poids_cc, notes.note_cc, notes.note_rattrapage))


def moyenne_ponderee(valeurs: list[tuple[Decimal, Decimal]]) -> Decimal:
    """valeurs : (moyenne, coefficient)."""
    total_coef = sum((Decimal(c) for _, c in valeurs), ZERO)
    if total_coef <= ZERO:
        raise ErreurCalcul("Somme des coefficients nulle : aucun module à moyenner")
    return arrondir(sum((Decimal(m) * Decimal(c) for m, c in valeurs), ZERO) / total_coef)


def decider(moyenne: Decimal, type_session: str, regles: Regles) -> str:
    if type_session not in ("normale", "rattrapage"):
        raise ErreurCalcul(f"Type de session inconnu : {type_session}")
    if moyenne >= regles.seuil:
        return "admis"
    return "rattrapage" if type_session == "normale" else "ajourne"


def calculer_etudiant(modules: list[NotesModule], type_session: str, regles: Regles = Regles()) -> ResultatCalcule:
    if not modules:
        raise ErreurCalcul("Aucun module pour cet étudiant")
    moyennes = [(m, moyenne_retenue(m)) for m in modules]
    moyenne = moyenne_ponderee([(moy, m.coefficient) for m, moy in moyennes])
    compense = regles.compensation and moyenne >= regles.seuil
    details = tuple(
        ResultatModuleCalcule(m.module_id, moy, acquis=compense or moy >= regles.seuil) for m, moy in moyennes
    )
    credits = sum(m.credits for m, d in zip(modules, details, strict=True) if d.acquis)
    return ResultatCalcule(moyenne, credits, decider(moyenne, type_session, regles), details)
