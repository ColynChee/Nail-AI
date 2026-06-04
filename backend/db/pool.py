"""Async connection pool helpers for Postgres (asyncpg)."""
from __future__ import annotations

import asyncpg
from typing import Optional

from db.config import get_database_settings


async def create_pool(**kwargs) -> asyncpg.pool.Pool:
    settings = get_database_settings()
    # Allow callers to override ssl or other asyncpg.create_pool kwargs
    opts = {"dsn": settings.database_url, "ssl": "require"}
    opts.update(kwargs)
    return await asyncpg.create_pool(**opts)


async def close_pool(pool: Optional[asyncpg.pool.Pool]) -> None:
    if pool is None:
        return
    await pool.close()
