from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    dart_api_key: str
    frontend_origin: str
    cache_ttl_seconds: int
    database_path: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    dart_api_key = os.getenv("DART_API_KEY", "").strip()
    if not dart_api_key:
        raise RuntimeError("DART_API_KEY is required.")

    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip()
    cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
    database_path = os.getenv("DATABASE_PATH", "financial_statements.db").strip()

    return Settings(
        dart_api_key=dart_api_key,
        frontend_origin=frontend_origin,
        cache_ttl_seconds=cache_ttl_seconds,
        database_path=database_path,
    )
