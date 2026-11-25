"""Fixtures des tests de Dari : application complète sur une base SQLite temporaire.

Connexion sans étape email (login_email_required=False) : les tests du parcours de connexion
complet sont dans tests/kit. Les données sont fictives.
"""
import tempfile
from datetime import date, time
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import AppSettings
from app.main import create_app
from app.models import Enseignant, Etudiant, Module, Promotion, Salle, SessionExamen
from auth_kit import AuthSettings
from auth_kit.adapters import LimitsRateLimiter, MemoryEmailSender
from auth_kit.models import Base, Role, User
from auth_kit.security import get_password_hash

PASSWORD = "cheval-batterie-agrafe"
HASH = get_password_hash(PASSWORD)   # bcrypt est lent : un seul hash pour tous les comptes de test
_DOSSIER = Path(tempfile.mkdtemp(prefix="dari-tests-"))

settings = AppSettings(
    DATABASE_URL=f"sqlite:///{_DOSSIER / 'test.db'}", UPLOAD_DIR=_DOSSIER / "uploads",
    LOG_FORMAT="text", LOG_LEVEL="WARNING", ENVIRONMENT="test", APP_VERSION="test",
    _env_file=None,
)
auth_settings = AuthSettings(
    secret_key="cle-de-test-uniquement-pour-pytest-0123456789", login_email_required=False, cookie_secure=False,
)
app = create_app(settings, auth_settings, MemoryEmailSender(), LimitsRateLimiter("memory://", enabled=False))
engine = app.state.engine
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
kit = app.state.ctx.kit


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    kit.seed_roles(db)
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def make_user(username: str, role: str = "user", email: str | None = None) -> int:
    db = SessionLocal()
    user = User(
        username=username, email=email or f"{username}@univ-bejaia.dz", hashed_password=HASH,
        role_id=db.query(Role).filter(Role.name == role).one().id, is_verified=True, disabled=False,
    )
    db.add(user)
    db.commit()
    db.close()
    return user.id


def auth(client: TestClient, username: str) -> dict:
    r = client.post("/auth/token", data={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class Monde:
    """Jeu de données minimal : une promotion, 3 étudiants, 2 modules, 2 enseignants, une session S1."""

    def __init__(self, client: TestClient):
        # Comptes d'abord : make_user ouvre sa propre session (SQLite n'accepte qu'un écrivain à la fois)
        self.prof_id = make_user("prof", "enseignant")
        self.prof2_id = make_user("prof2", "enseignant")
        self.etu_ids = [make_user(f"etu{i}", "etudiant") for i in range(3)]
        make_user("scol", "scolarite")
        make_user("jury", "jury")

        db = SessionLocal()
        self.promo = Promotion(code="L3-INFO", libelle="L3 Informatique", annee_universitaire="2026-2027")
        db.add(self.promo)
        db.flush()
        self.prof =Enseignant(nom="Benali", prenom="Karim", email="prof@univ-bejaia.dz", user_id=self.prof_id)
        self.prof2 = Enseignant(nom="Haddad", prenom="Sonia", email="prof2@univ-bejaia.dz", user_id=self.prof2_id)
        db.add_all([self.prof, self.prof2])
        db.flush()
        self.algo = Module(code="ALGO", intitule="Algorithmique", promotion_id=self.promo.id, semestre=1,
                           coefficient=Decimal("3"), credits=6, poids_cc=Decimal("0.40"), responsable_id=self.prof.id)
        self.bdd = Module(code="BDD", intitule="Bases de données", promotion_id=self.promo.id, semestre=1,
                          coefficient=Decimal("2"), credits=4, poids_cc=Decimal("0.40"), responsable_id=self.prof2.id)
        db.add_all([self.algo, self.bdd])
        self.etudiants = [
            Etudiant(matricule=f"2026000{i}", nom=f"Nom{i}", prenom=f"Prenom{i}", email=f"etu{i}@univ-bejaia.dz",
                     promotion_id=self.promo.id, user_id=self.etu_ids[i])
            for i in range(3)
        ]
        db.add_all(self.etudiants)
        self.salle = Salle(nom="Amphi A", capacite=120)
        db.add(self.salle)
        self.session = SessionExamen(libelle="S1 2026-2027", type="normale", semestre=1, promotion_id=self.promo.id,
                                     date_debut=date(2027, 1, 10), date_fin=date(2027, 1, 20), statut="ouverte")
        db.add(self.session)
        db.commit()
        db.close()
        self.client = client
        self.h_prof, self.h_prof2 = auth(client, "prof"), auth(client, "prof2")
        self.h_scol, self.h_jury = auth(client, "scol"), auth(client, "jury")
        self.h_etu = [auth(client, f"etu{i}") for i in range(3)]

    def saisir(self, module: Module, headers: dict, notes: list[tuple], session_id: int | None = None):
        """notes : (indice étudiant, cc, examen)."""
        lignes = [
            {"etudiant_id": self.etudiants[i].id, "note_cc": cc, "note_examen": ex, "absent": ex is None}
            for i, cc, ex in notes
        ]
        return self.client.put(
            f"/sessions/{session_id or self.session.id}/modules/{module.id}/notes", json={"notes": lignes}, headers=headers,
        )

    def valider(self, module: Module, headers: dict, session_id: int | None = None):
        return self.client.post(f"/sessions/{session_id or self.session.id}/modules/{module.id}/validation", headers=headers)

    def session_complete(self):
        """Notes saisies et validées : étudiant 0 admis, 1 admis par compensation, 2 en rattrapage."""
        # ALGO (coef 3, 40 % CC) : 0.4x14 + 0.6x15.5 = 14.90 ; 12.00 ; 0.4x4 + 0.6x8 = 6.40
        # BDD (coef 2) : 12.00 ; 8.00 ; 6.00
        # Semestre : (14.90x3 + 12x2) / 5 = 13.74 ; (12x3 + 8x2) / 5 = 10.40 ; (6.40x3 + 6x2) / 5 = 6.24
        assert self.saisir(self.algo, self.h_prof, [(0, 14, 15.5), (1, 12, 12), (2, 4, 8)]).status_code == 200
        assert self.saisir(self.bdd, self.h_prof2, [(0, 12, 12), (1, 8, 8), (2, 6, 6)]).status_code == 200
        assert self.valider(self.algo, self.h_prof).status_code == 204
        assert self.valider(self.bdd, self.h_prof2).status_code == 204

    def deliberer(self, session_id: int | None = None, publier: bool = True):
        sid = session_id or self.session.id
        r = self.client.post(f"/sessions/{sid}/deliberation", json={}, headers=self.h_scol)
        assert r.status_code == 200, r.json()
        assert self.client.post(f"/sessions/{sid}/deliberation/validation", headers=self.h_jury).status_code == 200
        if publier:
            assert self.client.post(f"/sessions/{sid}/publication", headers=self.h_scol).status_code == 200
        return r.json()


@pytest.fixture
def monde(client) -> Monde:
    return Monde(client)


__all__ = ["PASSWORD", "Monde", "auth", "make_user", "time"]
