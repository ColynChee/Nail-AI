"""Database configuration helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


@dataclass(frozen=True)
class DatabaseSettings:
    database_url: str


def get_database_settings() -> DatabaseSettings:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL is not set in backend/.env")
    return DatabaseSettings(database_url=database_url)