"""Parcours complet d'une session : saisie, validation, délibération, verrouillage, publication, rattrapage."""
from datetime import date

from sqlalchemy import select

from app.models import Note, NoteHistorique


def test_saisie_et_feuille_de_notes(monde, client):
    r = monde.saisir(monde.algo, monde.h_prof, [(0, 14, 15.5), (1, 12, None)])
    assert r.status_code == 200, r.json()
    lignes = {ligne["matricule"]: ligne for ligne in r.json()["lignes"]}
    assert lignes["20260000"]["moyenne"] == "14.90"
    assert lignes["20260001"]["absent"] is True and lignes["20260001"]["note_examen"] is None
    assert lignes["20260002"]["moyenne"] is None          # pas encore saisi
    assert r.json()["validee"] is False


def test_note_hors_bareme_refusee(monde):
    r = monde.saisir(monde.algo, monde.h_prof, [(0, 21, 10)])
    assert r.status_code == 422 and r.json()["code"] == "validation_error"


def test_chaque_modification_est_tracee(monde, db):
    monde.saisir(monde.algo, monde.h_prof, [(0, 10, 10)])
    monde.saisir(monde.algo, monde.h_prof, [(0, 10, 10)])      # identique : pas de trace
    monde.saisir(monde.algo, monde.h_prof, [(0, 10, 12)])
    note = db.scalar(select(Note).where(Note.etudiant_id == monde.etudiants[0].id))
    traces = db.scalars(select(NoteHistorique).where(NoteHistorique.note_id == note.id)).all()
    assert [(str(t.ancien_examen), str(t.nouveau_examen)) for t in traces] == [("None", "10.00"), ("10.00", "12.00")]


def test_validation_exige_toutes_les_notes(monde):
    monde.saisir(monde.algo, monde.h_prof, [(0, 14, 15.5)])
    r = monde.valider(monde.algo, monde.h_prof)
    assert r.status_code == 422 and "2 note(s)" in r.json()["message"]


def test_plus_de_saisie_apres_validation(monde, client):
    monde.session_complete()
    r = monde.saisir(monde.algo, monde.h_prof, [(0, 20, 20)])
    assert r.status_code == 409 and r.json()["code"] == "module_valide"
    # la scolarité peut rouvrir la saisie avant la délibération
    url = f"/sessions/{monde.session.id}/modules/{monde.algo.id}/validation"
    assert client.delete(url, headers=monde.h_prof).status_code == 403
    assert client.delete(url, headers=monde.h_scol).status_code == 204
    assert monde.saisir(monde.algo, monde.h_prof, [(0, 14, 15.5)]).status_code == 200


def test_deliberation_exige_tous_les_modules_valides(monde, client):
    monde.saisir(monde.algo, monde.h_prof, [(0, 14, 15.5), (1, 12, 12), (2, 4, 8)])
    monde.valider(monde.algo, monde.h_prof)
    r = client.post(f"/sessions/{monde.session.id}/deliberation", json={}, headers=monde.h_scol)
    assert r.status_code == 409 and r.json()["code"] == "modules_non_valides"


def test_deliberation_complete(monde, client):
    monde.session_complete()
    delib = monde.deliberer(publier=False)
    resultats = {r["matricule"]: r for r in delib["resultats"]}
    assert [(r["moyenne"], r["decision"], r["credits_acquis"]) for r in resultats.values()] == [
        ("13.74", "admis", 10), ("10.40", "admis", 10), ("6.24", "rattrapage", 0),
    ]
    assert delib["statut"] == "brouillon"   # renvoyé par le calcul, avant validation

    # Session verrouillée après validation du jury
    session = client.get(f"/sessions/{monde.session.id}", headers=monde.h_scol).json()
    assert session["statut"] == "deliberee"
    r = client.delete(f"/sessions/{monde.session.id}/modules/{monde.algo.id}/validation", headers=monde.h_scol)
    assert r.status_code == 409 and r.json()["code"] == "session_verrouillee"
    assert client.post(f"/sessions/{monde.session.id}/deliberation", json={}, headers=monde.h_scol).status_code == 409


def test_seuil_et_compensation_parametrables(monde, client):
    monde.session_complete()
    r = client.post(f"/sessions/{monde.session.id}/deliberation", json={"compensation": False}, headers=monde.h_scol)
    etu1 = next(x for x in r.json()["resultats"] if x["matricule"] == "20260001")
    assert (etu1["decision"], etu1["credits_acquis"]) == ("admis", 6)
    r = client.post(f"/sessions/{monde.session.id}/deliberation", json={"seuil": 12}, headers=monde.h_scol)
    assert [x["decision"] for x in r.json()["resultats"]] == ["admis", "rattrapage", "rattrapage"]


def test_seul_le_jury_valide(monde, client):
    monde.session_complete()
    client.post(f"/sessions/{monde.session.id}/deliberation", json={}, headers=monde.h_scol)
    url = f"/sessions/{monde.session.id}/deliberation/validation"
    assert client.post(url, headers=monde.h_scol).status_code == 403
    assert client.post(url, headers=monde.h_prof).status_code == 403
    assert client.post(url, headers=monde.h_jury).status_code == 200
    assert client.post(url, headers=monde.h_jury).json()["code"] == "deliberation_deja_validee"


def test_publication_et_espace_etudiant(monde, client):
    monde.session_complete()
    monde.deliberer(publier=False)
    assert client.get("/moi/resultats", headers=monde.h_etu[0]).json() == []    # pas encore publié
    assert client.post(f"/sessions/{monde.session.id}/publication", headers=monde.h_scol).status_code == 200

    mes = client.get("/moi/resultats", headers=monde.h_etu[0]).json()
    assert len(mes) == 1 and mes[0]["resultat"]["moyenne"] == "13.74"
    assert [mod["code"] for mod in mes[0]["resultat"]["modules"]] == ["ALGO", "BDD"]


def test_publication_exige_validation(monde, client):
    monde.session_complete()
    client.post(f"/sessions/{monde.session.id}/deliberation", json={}, headers=monde.h_scol)
    r = client.post(f"/sessions/{monde.session.id}/publication", headers=monde.h_scol)
    assert r.status_code == 409 and r.json()["code"] == "deliberation_non_validee"


def test_pdf_pv_et_releve(monde, client):
    monde.session_complete()
    monde.deliberer()
    pv = client.get(f"/sessions/{monde.session.id}/deliberation/pv.pdf", headers=monde.h_jury)
    assert pv.status_code == 200 and pv.headers["content-type"] == "application/pdf"
    assert pv.content.startswith(b"%PDF-")
    releve = client.get(f"/moi/releves/{monde.session.id}.pdf", headers=monde.h_etu[0])
    assert releve.status_code == 200 and releve.content.startswith(b"%PDF-")


def _creer_rattrapage(monde, client) -> int:
    r = client.post("/sessions", headers=monde.h_scol, json={
        "libelle": "Rattrapage S1", "type": "rattrapage", "semestre": 1, "promotion_id": monde.promo.id,
        "session_normale_id": monde.session.id, "date_debut": "2027-02-01", "date_fin": "2027-02-05",
    })
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def test_session_de_rattrapage(monde, client):
    monde.session_complete()
    monde.deliberer()
    sid = _creer_rattrapage(monde, client)

    # Seul l'étudiant 2 rattrape, et seulement ALGO et BDD (non acquis)
    feuille = client.get(f"/sessions/{sid}/modules/{monde.algo.id}/notes", headers=monde.h_prof).json()
    assert [ligne["matricule"] for ligne in feuille["lignes"]] == ["20260002"]
    assert feuille["lignes"][0]["note_cc"] == "4.00"      # CC repris de la session normale
    assert monde.saisir(monde.algo, monde.h_prof, [(0, None, 10)], session_id=sid).json()["code"] == "etudiant_non_concerne"

    # ALGO : 0.4x4 + 0.6x16 = 11.20 ; BDD : 0.4x6 + 0.6x9 = 7.80 -> (33.6 + 15.6) / 5 = 9.84 -> ajourné
    assert monde.saisir(monde.algo, monde.h_prof, [(2, None, 16)], session_id=sid).status_code == 200
    assert monde.saisir(monde.bdd, monde.h_prof2, [(2, None, 9)], session_id=sid).status_code == 200
    monde.valider(monde.algo, monde.h_prof, session_id=sid)
    monde.valider(monde.bdd, monde.h_prof2, session_id=sid)
    delib = monde.deliberer(session_id=sid)
    assert [(r["matricule"], r["moyenne"], r["decision"], r["credits_acquis"]) for r in delib["resultats"]] == [
        ("20260002", "9.84", "ajourne", 6),
    ]


def test_rattrapage_impossible_avant_deliberation_normale(monde, client):
    sid = _creer_rattrapage(monde, client)
    r = client.get(f"/sessions/{sid}/modules/{monde.algo.id}/notes", headers=monde.h_prof)
    assert r.status_code == 409 and r.json()["code"] == "session_normale_non_deliberee"


def test_rattrapage_doit_pointer_une_session_normale(monde, client):
    r = client.post("/sessions", headers=monde.h_scol, json={
        "libelle": "R", "type": "rattrapage", "semestre": 1, "promotion_id": monde.promo.id,
        "date_debut": str(date(2027, 2, 1)), "date_fin": str(date(2027, 2, 2)),
    })
    assert r.status_code == 422 and r.json()["code"] == "session_normale_requise"
