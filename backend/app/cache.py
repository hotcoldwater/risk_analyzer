from __future__ import annotations

from cachetools import TTLCache

from app.config import get_settings


settings = get_settings()
analysis_cache: TTLCache[str, dict] = TTLCache(maxsize=256, ttl=settings.cache_ttl_seconds)


def build_cache_key(query: str, analysis_type: str) -> str:
    return f"{analysis_type}:{query.strip().lower()}"


def get_cached_analysis(cache_key: str) -> dict | None:
    return analysis_cache.get(cache_key)


def set_cached_analysis(cache_key: str, payload: dict) -> None:
    analysis_cache[cache_key] = payload
