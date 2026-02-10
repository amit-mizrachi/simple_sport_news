"""Redis key-per-article processed cache with automatic TTL expiration."""
from typing import Optional

import redis

from src.shared.appconfig_client import get_config_service
from src.shared.interfaces.processed_cache import ProcessedCache
from src.shared.observability.logs.logger import Logger

_KEY_PREFIX = "processed:seen"
_TTL_SECONDS = 3600
# TODO: Migrate to AppConfig

class RedisProcessedCache(ProcessedCache):
    def __init__(self, host: str, port: int):
        self._logger = Logger()
        self._client = redis.Redis(host=host, port=port, decode_responses=True)

    def exists(self, source: str, source_id: str) -> bool:
        key = self._make_key(source, source_id)
        try:
            return self._client.exists(key) == 1
        except Exception as e:
            self._logger.warning(f"Processed cache unavailable, deferring to fallback: {e}")
            return False

    @staticmethod
    def _make_key(source: str, source_id: str) -> str:
        return f"{_KEY_PREFIX}:{source}:{source_id}"

    def mark_processed(self, source: str, source_id: str) -> None:
        key = self._make_key(source, source_id)
        try:
            self._client.set(key, 1, ex=_TTL_SECONDS)
        except Exception as e:
            self._logger.warning(f"Failed to mark article in processed cache: {e}")

def get_processed_cache() -> Optional[ProcessedCache]:
    try:
        config = get_config_service()
        host = config.get("redis.host")
        port = int(config.get("redis.port"))
        return RedisProcessedCache(host=host, port=port)
    except Exception as e:
        Logger().warning(f"Processed cache not available, falling back to MongoDB-only: {e}")
        return None
