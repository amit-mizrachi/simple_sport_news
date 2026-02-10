"""Redis Set-based deduplication cache for fast article existence checks."""
from typing import Optional

import redis

from src.shared.appconfig_client import get_config_service
from src.shared.interfaces.dedup_cache import DedupCache
from src.shared.observability.logs.logger import Logger


class RedisDedupCache(DedupCache):
    _SET_KEY = "dedup:seen_articles"

    def __init__(self):
        self._logger = Logger()
        config = get_config_service()
        host = config.get("redis.host")
        port = config.get("redis.port")
        self._client = redis.Redis(host=host, port=port, decode_responses=True)

    def exists(self, source: str, source_id: str) -> bool:
        """Check if an article has already been seen."""
        member = f"{source}:{source_id}"
        try:
            return self._client.sismember(self._SET_KEY, member)
        except Exception as e:
            self._logger.warning(f"Dedup cache unavailable, deferring to fallback: {e}")
            return False

    def mark_seen(self, source: str, source_id: str) -> None:
        """Mark an article as seen."""
        member = f"{source}:{source_id}"
        try:
            self._client.sadd(self._SET_KEY, member)
        except Exception as e:
            self._logger.warning(f"Failed to mark article in dedup cache: {e}")


def get_dedup_cache() -> Optional[DedupCache]:
    """Create a Redis dedup cache, falling back to None if unavailable."""
    try:
        return RedisDedupCache()
    except Exception as e:
        Logger().warning(f"Dedup cache not available, falling back to MongoDB-only: {e}")
        return None
