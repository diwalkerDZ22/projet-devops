"""Codes d'erreur de Dari, ajoutés au catalogue du kit : même format {"code", "message"} partout.

Dans les routes : raise ApiError("code"), jamais HTTPException.
"""
from auth_kit.errors import ApiError

__all__ = ["ApiError", "ERREURS"]

ERREURS: dict[str, tuple[int, str]] = {
    # Référentiels
    "promotion_introuvable": (404, "Promotion introuvable."),
    "etudiant_introuvable": (404, "Étudiant introuvable."),
    "enseignant_introuvable": (404, "Enseignant introuvable."),
    "module_introuvable": (404, "Module introuvable."),
    "salle_introuvable": (404, "Salle introuvable."),
    "doublon": (409, "Un élément avec ces informations existe déjà."),
    "suppression_impossible": (409, "Suppression impossible : cet élément est utilisé ailleurs."),
    "csv_invalide": (422, "Fichier CSV invalide."),
    # Sessions et planning
    "session_introuvable": (404, "Session d'examen introuvable."),
    "epreuve_introuvable": (404, "Épreuve introuvable."),
    "session_normale_requise": (422, "Une session de rattrapage doit indiquer la session normale qu'elle rattrape."),
    "session_normale_non_deliberee": (409, "La session normale n'a pas encore de délibération validée."),
    "session_verrouillee": (409, "Session délibérée : les notes sont verrouillées."),
    "conflit_planning": (409, "Conflit de planning."),
    "module_hors_session": (422, "Ce module n'appartient pas à la promotion et au semestre de la session."),
    # Sujets
    "sujet_introuvable": (404, "Aucun sujet déposé pour cette épreuve."),
    "fichier_invalide": (422, "Le sujet doit être un fichier PDF."),
    "fichier_trop_gros": (413, "Fichier trop volumineux."),
    # Notes
    "pas_responsable": (403, "Vous n'êtes pas responsable de ce module."),
    "module_valide": (409, "Les notes de ce module sont validées : plus de modification possible."),
    "module_non_valide": (409, "Les notes de ce module ne sont pas validées."),
    "etudiant_non_concerne": (422, "Cet étudiant n'est pas concerné par ce module dans cette session."),
    "note_hors_bareme": (422, "Une note doit être comprise entre 0 et 20."),
    # Délibération
    "deliberation_introuvable": (404, "Aucune délibération pour cette session."),
    "modules_non_valides": (409, "Tous les modules doivent être validés avant la délibération."),
    "deliberation_deja_validee": (409, "Délibération déjà validée."),
    "deliberation_non_validee": (409, "La délibération doit être validée par le jury."),
    "calcul_impossible": (422, "Calcul impossible : vérifiez les coefficients des modules."),
    # Résultats et réclamations
    "profil_etudiant_absent": (403, "Votre compte n'est rattaché à aucun étudiant."),
    "resultats_non_publies": (404, "Résultats non publiés."),
    "reclamation_introuvable": (404, "Réclamation introuvable."),
    "reclamation_deja_traitee": (409, "Cette réclamation est déjà traitée."),
    "reclamation_en_double": (409, "Vous avez déjà une réclamation en cours pour ce module."),
}
