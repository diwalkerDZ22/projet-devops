"""Planning des épreuves : conflits de salle, de surveillant, de promotion et de capacité."""
from datetime import date, time

import pytest

from app.services.planning import Creneau, detecter_conflits, se_chevauchent

J = date(2027, 1, 12)


def c(id_=None, debut=time(9), duree=90, salle=1, promo=1, surv=(), jour=J) -> Creneau:
    return Creneau(id_, f"E{id_}", jour, debut, duree, salle, promo, frozenset(surv))


@pytest.mark.parametrize("a, b, attendu", [
    (c(debut=time(9)), c(debut=time(10)), True),            # 9:00-10:30 et 10:00-11:30
    (c(debut=time(9)), c(debut=time(10, 30)), False),       # bout à bout : pas de chevauchement
    (c(debut=time(9), duree=240), c(debut=time(10)), True),  # inclus
    (c(debut=time(9)), c(debut=time(9), jour=date(2027, 1, 13)), False),
])
def test_chevauchement(a, b, attendu):
    assert se_chevauchent(a, b) is attendu
    assert se_chevauchent(b, a) is attendu


def test_aucun_conflit():
    assert detecter_conflits(c(salle=1, promo=1), [c(1, salle=2, promo=2, surv=(5,))]) == []


def test_conflits_detectes():
    types = {x.type for x in detecter_conflits(c(salle=1, promo=1, surv=(5,)), [c(1, salle=1, promo=1, surv=(5, 6))])}
    assert types == {"salle", "surveillant", "promotion"}


def test_une_epreuve_ne_se_gene_pas_elle_meme():
    assert detecter_conflits(c(1), [c(1)]) == []


def test_capacite():
    [conflit] = detecter_conflits(c(), [], capacite_salle=30, effectif=45)
    assert conflit.type == "capacite" and "45" in conflit.message




