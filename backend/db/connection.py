"""Minimal Supabase/Postgres connectivity test."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.config import get_database_settings


async def test_connection() -> str:
    settings = get_database_settings()
    conn = await asyncpg.connect(settings.database_url, ssl="require")
    try:
        value = await conn.fetchval("select 1")
        return f"ok: select 1 -> {value}"
    finally:
        await conn.close()


def main() -> None:
    print(asyncio.run(test_connection()))


if __name__ == "__main__":
    main()