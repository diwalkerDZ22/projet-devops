"""Détection des conflits de planning d'une épreuve. Fonctions pures.

Deux épreuves se chevauchent si elles ont lieu le même jour et que leurs créneaux
[début, début + durée[ se recouvrent. En cas de chevauchement :
- même salle -> conflit de salle ;
- un surveillant commun -> conflit de surveillant ;
- même promotion -> conflit d'étudiants (ils ne peuvent pas passer deux épreuves à la fois).
La salle doit aussi pouvoir accueillir l'effectif de la promotion.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class Creneau:
    epreuve_id: int | None
    libelle: str
    date: date
    heure_debut: time
    duree_minutes: int
    salle_id: int | None
    promotion_id: int
    surveillants: frozenset[int] = field(default_factory=frozenset)

    @property
    def debut(self) -> datetime:
        return datetime.combine(self.date, self.heure_debut)

    @property
    def fin(self) -> datetime:
        return self.debut + timedelta(minutes=self.duree_minutes)


@dataclass(frozen=True)
class Conflit:
    type: str          # salle, surveillant, promotion, capacite
    message: str
    epreuve_id: int | None = None


def se_chevauchent(a: Creneau, b: Creneau) -> bool:
    return a.date == b.date and a.debut < b.fin and b.debut < a.fin


def detecter_conflits(
    nouvelle: Creneau,
    existantes: list[Creneau],
    capacite_salle: int | None = None,
    effectif: int = 0,
) -> list[Conflit]:
    conflits: list[Conflit] = []
    if capacite_salle is not None and effectif > capacite_salle:
        conflits.append(Conflit("capacite", f"Salle trop petite : {effectif} étudiants pour {capacite_salle} places."))
    for autre in existantes:
        if autre.epreuve_id is not None and autre.epreuve_id == nouvelle.epreuve_id:
            continue
        if not se_chevauchent(nouvelle, autre):
            continue
        if nouvelle.salle_id is not None and nouvelle.salle_id == autre.salle_id:
            conflits.append(Conflit("salle", f"Salle déjà occupée par « {autre.libelle} ».", autre.epreuve_id))
        communs = nouvelle.surveillants & autre.surveillants
        if communs:
            conflits.append(Conflit(
                "surveillant", f"{len(communs)} surveillant(s) déjà affecté(s) à « {autre.libelle} ».", autre.epreuve_id,
            ))
        if nouvelle.promotion_id == autre.promotion_id:
            conflits.append(Conflit(
                "promotion", f"La promotion passe déjà « {autre.libelle} » sur ce créneau.", autre.epreuve_id,
            ))
    return conflits
