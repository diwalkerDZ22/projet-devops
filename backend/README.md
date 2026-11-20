# Backend Dari

API FastAPI de Dari (`app/`) et module d'authentification auth-kit (`src/auth_kit/`, installé en mode éditable
par `requirements.txt`). Voir le [README principal](../README.md) et [docs/Architecture.md](../docs/Architecture.md).

```bash
python -m pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade heads                         # migrations du kit et de Dari
python -m scripts.seed_demo                   # données de démonstration (DEMO_PASSWORD)
python -m uvicorn --factory app.main:create_app --reload
ruff check . && python -m pytest
```
