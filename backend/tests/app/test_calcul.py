"""Moteur de calcul : cas limites vérifiés à la main (pièce maîtresse du pipeline)."""
from decimal import Decimal as D

import pytest

from app.services.calcul import (
    ErreurCalcul,
    NotesModule,
    Regles,
    arrondir,
    calculer_etudiant,
    decider,
    moyenne_module,
    moyenne_ponderee,
    moyenne_retenue,
)


def m(module_id=1, coef="1", credits=5, poids="0.40", cc=None, ex=None, ratt=None) -> NotesModule:
    def d(v):
        return None if v is None else D(str(v))
    return NotesModule(module_id, D(coef), credits, D(poids), d(cc), d(ex), d(ratt))


# --- Arrondi -----------------------------------------------------------------------------------

@pytest.mark.parametrize("valeur, attendu", [
    ("9.995", "10.00"),     # demi vers le haut : un étudiant à 9.995 est admis
    ("9.994", "9.99"),
    ("10.005", "10.01"),
    ("12.345", "12.35"),
    ("0", "0.00"),
    ("20", "20.00"),
])
def test_arrondi_demi_vers_le_haut(valeur, attendu):
    assert arrondir(D(valeur)) == D(attendu)


def test_pas_d_erreur_de_flottant():
    # En flottant, 0.1 x 3 + 0.2 x 3 donne 0.9000000000000001
    assert moyenne_module(D("0.50"), D("0.6"), D("1.2")) == D("0.90")


# --- Moyenne de module -------------------------------------------------------------------------

@pytest.mark.parametrize("poids, cc, ex, attendu", [
    ("0.40", 14, 15.5, "14.90"),
    ("0.40", 10, 10, "10.00"),
    ("0.40", 20, 20, "20.00"),
    ("0.40", 0, 0, "0.00"),
    ("0.00", 18, 9, "9.00"),      # module sans CC : examen seul
    ("1.00", 18, 9, "18.00"),     # module en CC intégral
    ("0.40", None, 12, "7.20"),   # CC absent : compte 0
    ("0.40", 15, None, "6.00"),   # examen absent : compte 0
    ("0.40", None, None, "0.00"),
    ("0.33", 11, 13, "12.34"),    # 3.63 + 8.71 = 12.34
])
def test_moyenne_module(poids, cc, ex, attendu):
    notes = m(poids=poids, cc=cc, ex=ex)
    assert moyenne_module(notes.poids_cc, notes.note_cc, notes.note_examen) == D(attendu)


@pytest.mark.parametrize("note", ["-0.01", "20.01", "25"])
def test_note_hors_bareme_refusee(note):
    with pytest.raises(ErreurCalcul):
        moyenne_module(D("0.40"), D(note), D("10"))


@pytest.mark.parametrize("poids", ["-0.1", "1.01"])
def test_poids_invalide_refuse(poids):
    with pytest.raises(ErreurCalcul):
        moyenne_module(D(poids), D("10"), D("10"))


# --- Rattrapage --------------------------------------------------------------------------------

def test_rattrapage_remplace_l_examen_si_meilleur():
    # normale : 0.4x8 + 0.6x6 = 6.80 ; rattrapage : 0.4x8 + 0.6x12 = 10.40
    assert moyenne_retenue(m(cc=8, ex=6, ratt=12)) == D("10.40")


def test_rattrapage_moins_bon_ne_penalise_pas():
    # normale : 9.20 ; rattrapage : 0.4x8 + 0.6x5 = 6.20 -> on garde 9.20
    assert moyenne_retenue(m(cc=8, ex=10, ratt=5)) == D("9.20")


def test_absent_au_rattrapage_garde_la_note_normale():
    assert moyenne_retenue(m(cc=8, ex=10, ratt=None)) == D("9.20")


# --- Moyenne pondérée --------------------------------------------------------------------------

def test_moyenne_ponderee():
    assert moyenne_ponderee([(D("14.90"), D("3")), (D("12"), D("2"))]) == D("13.74")


def test_coefficients_nuls_refuses():
    with pytest.raises(ErreurCalcul):
        moyenne_ponderee([(D("12"), D("0"))])
    with pytest.raises(ErreurCalcul):
        moyenne_ponderee([])


def test_coefficients_decimaux():
    # (12 x 1.5 + 8 x 0.5) / 2 = 11.00
    assert moyenne_ponderee([(D("12"), D("1.5")), (D("8"), D("0.5"))]) == D("11.00")


# --- Décisions ---------------------------------------------------------------------------------

@pytest.mark.parametrize("moyenne, session, attendu", [
    ("10.00", "normale", "admis"),       # seuil atteint pile
    ("9.99", "normale", "rattrapage"),
    ("9.99", "rattrapage", "ajourne"),
    ("10.00", "rattrapage", "admis"),
    ("0", "normale", "rattrapage"),
])
def test_decision(moyenne, session, attendu):
    assert decider(D(moyenne), session, Regles()) == attendu


def test_type_de_session_inconnu():
    with pytest.raises(ErreurCalcul):
        decider(D("12"), "speciale", Regles())


def test_seuil_parametrable():
    assert decider(D("11"), "normale", Regles(seuil=D("12"))) == "rattrapage"


# --- Calcul complet d'un étudiant --------------------------------------------------------------

MODULES = dict(algo=dict(module_id=1, coef="3", credits=6), bdd=dict(module_id=2, coef="2", credits=4))


def test_admis_sans_compensation_necessaire():
    r = calculer_etudiant([m(**MODULES["algo"], cc=14, ex=15.5), m(**MODULES["bdd"], cc=12, ex=12)], "normale")
    assert (r.moyenne, r.decision, r.credits_acquis) == (D("13.74"), "admis", 10)
    assert all(d.acquis for d in r.modules)


def test_compensation_donne_tous_les_credits():
    # ALGO 12.00, BDD 8.00 -> 10.40 : BDD < 10 mais compensé
    r = calculer_etudiant([m(**MODULES["algo"], cc=12, ex=12), m(**MODULES["bdd"], cc=8, ex=8)], "normale")
    assert (r.moyenne, r.decision, r.credits_acquis) == (D("10.40"), "admis", 10)
    assert [d.acquis for d in r.modules] == [True, True]


def test_sans_compensation_seuls_les_modules_valides_comptent():
    r = calculer_etudiant(
        [m(**MODULES["algo"], cc=12, ex=12), m(**MODULES["bdd"], cc=8, ex=8)], "normale", Regles(compensation=False),
    )
    assert (r.decision, r.credits_acquis) == ("admis", 6)
    assert [d.acquis for d in r.modules] == [True, False]


def test_echec_garde_les_credits_des_modules_valides():
    # ALGO 12.00 (acquis), BDD 4.00 : (36 + 8) / 5 = 8.80 -> rattrapage, 6 crédits
    r = calculer_etudiant([m(**MODULES["algo"], cc=12, ex=12), m(**MODULES["bdd"], cc=4, ex=4)], "normale")
    assert (r.moyenne, r.decision, r.credits_acquis) == (D("8.80"), "rattrapage", 6)


def test_rattrapage_reussi():
    # BDD : normale 4.00, rattrapage 0.4x4 + 0.6x14 = 10.00 -> (36 + 20) / 5 = 11.20
    r = calculer_etudiant(
        [m(**MODULES["algo"], cc=12, ex=12), m(**MODULES["bdd"], cc=4, ex=4, ratt=14)], "rattrapage",
    )
    assert (r.moyenne, r.decision, r.credits_acquis) == (D("11.20"), "admis", 10)


def test_rattrapage_echoue_ajourne():
    r = calculer_etudiant(
        [m(**MODULES["algo"], cc=12, ex=12), m(**MODULES["bdd"], cc=4, ex=4, ratt=5)], "rattrapage",
    )
    assert (r.decision, r.credits_acquis) == ("ajourne", 6)


def test_aucun_module():
    with pytest.raises(ErreurCalcul):
        calculer_etudiant([], "normale")


def test_tout_absent():
    r = calculer_etudiant([m(**MODULES["algo"]), m(**MODULES["bdd"])], "normale")
    assert (r.moyenne, r.decision, r.credits_acquis) == (D("0.00"), "rattrapage", 0)
