# Contribuer

## Branches et pull requests

- `main` est protégée : aucun push direct, fusion uniquement par pull request avec la CI verte et **au moins une relecture par un autre membre**.
- Une branche par tâche, nommée d'après l'issue : `feat/12-import-csv`, `fix/27-arrondi-moyenne`, `ci/31-cache-docker`, `docs/40-manuel`.
- Une pull request = une tâche, petite et relisible. Elle référence son issue (`Closes #12`) et suit le modèle `.github/pull_request_template.md`.
- Le relecteur vérifie le comportement, les tests et la lisibilité, puis approuve ou demande des changements. L'auteur fusionne après approbation.

## Messages de commit

Format court, en français, au présent : `type(portée): description`.

```
feat(notes): validation du module par son responsable
fix(calcul): arrondi au centième demi vers le haut
test(droits): un étudiant ne voit pas les résultats des autres
ci: test de restauration de la sauvegarde
```

Types : `feat`, `fix`, `test`, `refactor`, `docs`, `ci`, `build`, `chore`.

## Tableau de tâches

Les issues GitHub servent de tableau (projet GitHub en colonnes : À faire, En cours, En revue, Terminé), avec les
étiquettes `backend`, `frontend`, `devops`, `docs`, `bug` et un responsable par issue.

## Avant d'ouvrir une pull request

```bash
cd backend && ruff check . && python -m pytest
cd frontend && npm run lint && npm test && npm run build
```

- Un modèle SQLAlchemy modifié : `alembic revision --autogenerate --head dari@head -m "..."`, relire la migration, puis `alembic check`.
- Un schéma ou une route de l'API modifiés : `python -m scripts.openapi` (backend), puis `npm run gen:api` (frontend).
- Commentaires, messages d'erreur, journaux et documentation en français.
- Aucun secret, aucune vraie donnée d'étudiant dans le dépôt (données de test fictives).
