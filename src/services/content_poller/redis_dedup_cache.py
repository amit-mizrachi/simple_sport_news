"""Redis key-per-article deduplication cache with automatic TTL expiration."""
from typing import Optional

import redis

from src.shared.appconfig_client import get_config_service
from src.shared.interfaces.dedup_cache import DedupCache
from src.shared.observability.logs.logger import Logger

_KEY_PREFIX = "dedup:seen"
_TTL_SECONDS = 3600


class RedisDedupCache(DedupCache):

    def __init__(self, host: str, port: int):
        self._logger = Logger()
        self._client = redis.Redis(host=host, port=port, decode_responses=True)

    @staticmethod
    def _make_key(source: str, source_id: str) -> str:
        return f"{_KEY_PREFIX}:{source}:{source_id}"

    def exists(self, source: str, source_id: str) -> bool:
        """Check if an article has already been seen."""
        key = self._make_key(source, source_id)
        try:
            return self._client.exists(key) == 1
        except Exception as e:
            self._logger.warning(f"Dedup cache unavailable, deferring to fallback: {e}")
            return False

    def mark_seen(self, source: str, source_id: str) -> None:
        """Mark an article as seen with a 1-hour TTL."""
        key = self._make_key(source, source_id)
        try:
            self._client.set(key, 1, ex=_TTL_SECONDS)
        except Exception as e:
            self._logger.warning(f"Failed to mark article in dedup cache: {e}")


def get_dedup_cache() -> Optional[DedupCache]:
    """Create a Redis dedup cache, falling back to None if unavailable."""
    try:
        config = get_config_service()
        host = config.get("redis.host")
        port = int(config.get("redis.port"))
        return RedisDedupCache(host=host, port=port)
    except Exception as e:
        Logger().warning(f"Dedup cache not available, falling back to MongoDB-only: {e}")
        return None
