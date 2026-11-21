"""Rôles et permissions de Dari, passés à AuthKit (kit.seed_roles les crée / synchronise).

Les permissions « de ses modules » sont complétées par un contrôle d'appartenance dans les
routes : un enseignant ne saisit que les notes des modules dont il est responsable.
"""
from auth_kit import RoleSpec

ADMIN = "users:manage"
REFERENTIEL_LIRE = "referentiel:lire"
REFERENTIEL_GERER = "referentiel:gerer"
PLANNING_GERER = "planning:gerer"
SUJETS_DEPOSER = "sujets:deposer"
NOTES_SAISIR = "notes:saisir"
NOTES_GERER = "notes:gerer"
DELIBERATION_GERER = "deliberation:gerer"
DELIBERATION_VALIDER = "deliberation:valider"
RESULTATS_CONSULTER = "resultats:consulter"
RECLAMATIONS_DEPOSER = "reclamations:deposer"
RECLAMATIONS_TRAITER = "reclamations:traiter"
RECLAMATIONS_GERER = "reclamations:gerer"
STATS_CONSULTER = "stats:consulter"

PERMISSIONS: dict[str, str] = {
    ADMIN: "Gérer les comptes et leurs rôles",
    REFERENTIEL_LIRE: "Consulter promotions, étudiants, enseignants, modules et salles",
    REFERENTIEL_GERER: "Gérer promotions, étudiants, enseignants, modules et salles",
    PLANNING_GERER: "Gérer les sessions d'examen et les épreuves",
    SUJETS_DEPOSER: "Déposer et consulter les sujets de ses modules",
    NOTES_SAISIR: "Saisir et valider les notes de ses modules",
    NOTES_GERER: "Saisir et valider les notes de tous les modules",
    DELIBERATION_GERER: "Calculer les délibérations, éditer les PV et publier les résultats",
    DELIBERATION_VALIDER: "Valider une délibération (jury)",
    RESULTATS_CONSULTER: "Consulter ses résultats et ses relevés",
    RECLAMATIONS_DEPOSER: "Déposer une réclamation sur une note",
    RECLAMATIONS_TRAITER: "Traiter les réclamations de ses modules",
    RECLAMATIONS_GERER: "Traiter toutes les réclamations",
    STATS_CONSULTER: "Consulter les statistiques",
}

_LECTURE = (REFERENTIEL_LIRE, STATS_CONSULTER)

ROLES: dict[str, RoleSpec] = {
    # Rôle donné à l'inscription : promu en étudiant / enseignant au rattachement de son email
    "user": RoleSpec("Compte inscrit, en attente de rattachement"),
    "etudiant": RoleSpec("Étudiant", (RESULTATS_CONSULTER, RECLAMATIONS_DEPOSER)),
    "enseignant": RoleSpec("Enseignant", (*_LECTURE, NOTES_SAISIR, SUJETS_DEPOSER, RECLAMATIONS_TRAITER)),
    "scolarite": RoleSpec(
        "Administration et scolarité",
        (*_LECTURE, REFERENTIEL_GERER, PLANNING_GERER, SUJETS_DEPOSER, NOTES_GERER,
         DELIBERATION_GERER, RECLAMATIONS_GERER),
    ),
    "jury": RoleSpec("Membre du jury", (*_LECTURE, DELIBERATION_VALIDER)),
    "admin": RoleSpec("Administrateur", tuple(PERMISSIONS)),
}
