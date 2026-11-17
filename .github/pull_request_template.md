## Quoi et pourquoi

<!-- Ce que change cette PR, et le besoin auquel elle répond. -->

Closes #

## Comment vérifier

<!-- Étapes pour le relecteur : commandes, comptes de démo, écrans. -->

## Avant la revue

- [ ] `ruff check .` et `python -m pytest` passent (backend)
- [ ] `npm run lint`, `npm test` et `npm run build` passent (frontend)
- [ ] Tests ajoutés ou mis à jour pour le comportement modifié
- [ ] Migration Alembic créée et relue si un modèle a changé (`alembic check` passe)
- [ ] OpenAPI et types frontend régénérés si l'API a changé
- [ ] Aucun secret ni vraie donnée personnelle ajoutés
- [ ] Documentation mise à jour si besoin
