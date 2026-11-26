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

# --- API ---------------------------------------------------------------------------------------

def _epreuve(monde, module, heure="09:00", salle=True, surveillants=None):
    return monde.client.post(f"/sessions/{monde.session.id}/epreuves", headers=monde.h_scol, json={
        "module_id": module.id, "date": "2027-01-12", "heure_debut": heure, "duree_minutes": 90,
        "salle_id": monde.salle.id if salle else None, "surveillant_ids": surveillants or [monde.prof.id],
    })


def test_creer_epreuve(monde):
    r = _epreuve(monde, monde.algo)
    assert r.status_code == 201, r.json()
    assert r.json()["surveillant_ids"] == [monde.prof.id] and r.json()["sujet_depose"] is False


def test_conflit_renvoie_le_detail(monde):
    _epreuve(monde, monde.algo, "09:00")
    r = _epreuve(monde, monde.bdd, "10:00")
    assert r.status_code == 409 and r.json()["code"] == "conflit_planning"
    assert {x["type"] for x in r.json()["conflits"]} == {"salle", "surveillant", "promotion"}
    # rien n'a été créé
    assert len(monde.client.get(f"/sessions/{monde.session.id}/epreuves", headers=monde.h_scol).json()) == 1


def test_epreuves_successives_sans_conflit(monde):
    _epreuve(monde, monde.algo, "09:00")
    assert _epreuve(monde, monde.bdd, "13:00").status_code == 201


def test_seule_la_scolarite_planifie(monde, client):
    r = client.post(f"/sessions/{monde.session.id}/epreuves", headers=monde.h_prof, json={
        "module_id": monde.algo.id, "date": "2027-01-12", "heure_debut": "09:00", "duree_minutes": 90,
    })
    assert r.status_code == 403


def test_module_hors_session(monde, client):
    autre = client.post("/modules", headers=monde.h_scol, json={
        "code": "RES", "intitule": "Réseaux", "promotion_id": monde.promo.id, "semestre": 2, "coefficient": 2, "credits": 4,
    }).json()
    r = client.post(f"/sessions/{monde.session.id}/epreuves", headers=monde.h_scol, json={
        "module_id": autre["id"], "date": "2027-01-12", "heure_debut": "09:00", "duree_minutes": 90,
    })
    assert r.json()["code"] == "module_hors_session"


PDF = b"%PDF-1.4\n%fictif\n"


def test_sujet_confidentiel(monde, client):
    eid = _epreuve(monde, monde.algo).json()["id"]
    url = f"/epreuves/{eid}/sujet"
    assert client.post(url, files={"fichier": ("s.pdf", PDF, "application/pdf")}, headers=monde.h_prof2).status_code == 403
    r = client.post(url, files={"fichier": ("algo.pdf", PDF, "application/pdf")}, headers=monde.h_prof)
    assert r.status_code == 201 and r.json()["taille"] == len(PDF)

    assert client.get(url, headers=monde.h_prof).content == PDF
    assert client.get(url, headers=monde.h_scol).status_code == 200
    assert client.get(url, headers=monde.h_prof2).status_code == 403
    assert client.get(url, headers=monde.h_etu[0]).status_code == 403
    assert client.get(url, headers=monde.h_jury).status_code == 403


def test_sujet_doit_etre_un_pdf(monde, client):
    eid = _epreuve(monde, monde.algo).json()["id"]
    r = client.post(f"/epreuves/{eid}/sujet", files={"fichier": ("x.pdf", b"MZ exe", "application/pdf")}, headers=monde.h_prof)
    assert r.status_code == 422 and r.json()["code"] == "fichier_invalide"


