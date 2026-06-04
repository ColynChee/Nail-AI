# Database

This folder will hold the backend database layer for Nail AI.

Planned files:
- `config.py` for `DATABASE_URL` loading
- `session.py` for DB connection/session setup
- `models.py` or `schemas/` for tables
- `migrations/` for Alembic migrations

Current minimal setup:
- `config.py` reads `DATABASE_URL` from `backend/.env`
- `connection.py` provides a small async connectivity test using `asyncpg`
