# Règles de calcul des moyennes et des décisions

Implémentées dans `backend/app/services/calcul.py` (fonctions pures, sans base de données) et testées dans
`backend/tests/app/test_calcul.py` sur des cas vérifiés à la main. Ces règles sont des **valeurs par défaut
à confirmer avec le département** ; le seuil et la compensation sont paramétrables à chaque délibération.

## Moyenne d'un module

```
moyenne = poids_cc × CC + (1 − poids_cc) × examen
```

- `poids_cc` est propre à chaque module (0,40 par défaut ; 0 pour un module sans contrôle continu, 1 pour un module en CC intégral).
- Une note absente (étudiant absent, note non saisie) compte **0**.
- Arrondi au centième, **demi vers le haut** : 9,995 donne 10,00.
- Tous les calculs sont faits en décimal exact (`Decimal`), jamais en flottant : 0,1 + 0,2 vaut exactement 0,3.

Exemple : CC 14, examen 15,5, poids 0,40 : 0,4 × 14 + 0,6 × 15,5 = 5,60 + 9,30 = **14,90**.

## Rattrapage

- Seuls les étudiants dont la décision est « rattrapage » à la session normale composent, et seulement dans les modules **non acquis**.
- Le CC est repris de la session normale ; la note de rattrapage remplace l'examen.
- On retient la **meilleure** des deux moyennes : un rattrapage raté ne fait pas baisser la note.

Exemple : CC 8, examen 6, rattrapage 12 : normale 6,80, rattrapage 10,40 : **10,40**.

## Moyenne du semestre

```
moyenne = Σ (moyenne_module × coefficient) / Σ coefficients
```

arrondie au centième, calculée à partir des moyennes de modules déjà arrondies.

Exemple : ALGO 14,90 (coef. 3), BDD 12,00 (coef. 2) : (44,70 + 24,00) / 5 = **13,74**.

## Crédits

- Un module est acquis si sa moyenne atteint le seuil (10 par défaut) : ses crédits sont acquis.
- **Compensation** (activée par défaut) : si la moyenne du semestre atteint le seuil, tous les modules sont acquis, donc tous les crédits.

## Décision

| Session | Moyenne ≥ seuil | Moyenne < seuil |
|---------|-----------------|-----------------|
| Normale | Admis | Rattrapage |
| Rattrapage | Admis | Ajourné |

## Cycle d'une session

1. Les responsables de modules saisissent les notes puis **valident** leur module (plus de modification ensuite ; la scolarité peut rouvrir la saisie avant la délibération).
2. La scolarité **calcule** la délibération (brouillon, recalculable).
3. Le jury **valide** : la session passe à « délibérée », toutes les notes sont **verrouillées**.
4. La scolarité **publie** : les étudiants voient leurs résultats et leurs relevés.
5. Après publication, une **réclamation acceptée** peut corriger une note : la modification est tracée (`notes_historique`) et la décision de l'étudiant est recalculée.
