"""Procès-verbaux de délibération et relevés de notes en PDF (reportlab, polices standard intégrées).

Rendu reproductible : aucune dépendance au système (polices Helvetica de base, pas de police
installée à chercher), identique sur un poste de dev, en CI et dans le conteneur.
"""
import io
from datetime import datetime, timezone
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Deliberation, Resultat, SessionExamen

LIBELLES_DECISION = {"admis": "Admis", "rattrapage": "Rattrapage", "ajourne": "Ajourné"}
EN_TETE = ("Université de Béjaïa", "Faculté des Sciences Exactes", "Département d'Informatique")

_STYLES = getSampleStyleSheet()
_PETIT = ParagraphStyle("petit", parent=_STYLES["Normal"], fontSize=8, leading=10)
_TITRE = ParagraphStyle("titre", parent=_STYLES["Title"], fontSize=15, spaceAfter=4)
_STYLE_TABLE = TableStyle([
    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
    ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3d5e")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f7")]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa9b5")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (2, 1), (-1, -1), "CENTER"),
])


def _f(valeur: Decimal | None) -> str:
    return "-" if valeur is None else f"{Decimal(valeur):.2f}"


def _en_tete(titre: str, sous_titre: str) -> list:
    return [
        Paragraph("<br/>".join(EN_TETE), _PETIT),
        Spacer(1, 0.4 * cm),
        Paragraph(titre, _TITRE),
        Paragraph(sous_titre, _STYLES["Normal"]),
        Spacer(1, 0.4 * cm),
    ]


def _pied(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    genere = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    canvas.drawString(1.5 * cm, 1 * cm, f"Document généré par Dari le {genere}")
    canvas.drawRightString(doc.pagesize[0] - 1.5 * cm, 1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def proces_verbal(delib: Deliberation, modules: list, resultats: list[Resultat]) -> bytes:
    """PV de délibération : une ligne par étudiant, une colonne par module, signatures du jury."""
    session: SessionExamen = delib.session
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm,
        bottomMargin=1.5 * cm, title=f"PV - {session.libelle}", author="Dari",
    )
    statut = "validée par le jury" if delib.statut == "validee" else "BROUILLON - non validée"
    elements = _en_tete(
        "Procès-verbal de délibération",
        f"{session.promotion.libelle} ({session.promotion.annee_universitaire}) - {session.libelle} - "
        f"semestre {session.semestre} - délibération {statut}<br/>"
        f"Seuil d'admission : {_f(delib.seuil)} / 20 - compensation : {'oui' if delib.compensation else 'non'}",
    )
    entetes = ["Matricule", "Nom et prénom", *[m.code for m in modules], "Moyenne", "Crédits", "Décision"]
    lignes = [entetes]
    for r in resultats:
        par_module = {rm.module_id: rm for rm in r.modules}
        lignes.append([
            r.etudiant.matricule, f"{r.etudiant.nom} {r.etudiant.prenom}",
            *[_f(par_module[m.id].moyenne) if m.id in par_module else "-" for m in modules],
            _f(r.moyenne), str(r.credits_acquis), LIBELLES_DECISION[r.decision],
        ])
    table = Table(lignes, repeatRows=1)
    table.setStyle(_STYLE_TABLE)
    elements.append(table)

    effectifs = {d: sum(1 for r in resultats if r.decision == d) for d in LIBELLES_DECISION}
    total = len(resultats) or 1
    elements += [
        Spacer(1, 0.5 * cm),
        Paragraph(
            " - ".join(f"{LIBELLES_DECISION[d]} : {n}" for d, n in effectifs.items())
            + f" - taux de réussite : {effectifs['admis'] * 100 / total:.1f} %",
            _STYLES["Normal"],
        ),
        Spacer(1, 1 * cm),
        Table(
            [["Le président du jury", "Les membres du jury", "Le chef de département"]],
            colWidths=[8 * cm, 8 * cm, 8 * cm],
            style=[("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 9), ("ALIGN", (0, 0), (-1, -1), "CENTER")],
        ),
    ]
    doc.build(elements, onFirstPage=_pied, onLaterPages=_pied)
    return buffer.getvalue()


def releve_notes(session: SessionExamen, resultat: Resultat) -> bytes:
    """Relevé de notes individuel d'un étudiant pour une session."""
    etudiant = resultat.etudiant
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Relevé de notes - {etudiant.matricule}", author="Dari",
    )
    elements = _en_tete(
        "Relevé de notes",
        f"{etudiant.nom} {etudiant.prenom} - matricule {etudiant.matricule}<br/>"
        f"{session.promotion.libelle} ({session.promotion.annee_universitaire}) - {session.libelle}",
    )
    lignes = [["Code", "Module", "Coef.", "Crédits", "Moyenne", "Acquis"]]
    for rm in resultat.modules:
        lignes.append([
            rm.module.code, Paragraph(rm.module.intitule, _PETIT), _f(rm.module.coefficient),
            str(rm.module.credits), _f(rm.moyenne), "Oui" if rm.acquis else "Non",
        ])
    table = Table(lignes, repeatRows=1, colWidths=[2.2 * cm, 7.3 * cm, 1.6 * cm, 1.8 * cm, 2 * cm, 1.8 * cm])
    table.setStyle(_STYLE_TABLE)
    elements += [
        table,
        Spacer(1, 0.6 * cm),
        Paragraph(
            f"<b>Moyenne du semestre : {_f(resultat.moyenne)} / 20</b> - crédits acquis : {resultat.credits_acquis}"
            f" - décision : <b>{LIBELLES_DECISION[resultat.decision]}</b>",
            _STYLES["Normal"],
        ),
    ]
    doc.build(elements, onFirstPage=_pied, onLaterPages=_pied)
    return buffer.getvalue()
