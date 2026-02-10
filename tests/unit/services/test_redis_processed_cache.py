"""Tests for RedisProcessedCache."""
from unittest.mock import MagicMock, patch

import pytest

from src.services.content_poller.redis_processed_cache import RedisProcessedCache, get_processed_cache, _KEY_PREFIX, _TTL_SECONDS


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def cache(mock_redis):
    with patch("src.services.content_poller.redis_processed_cache.Logger"), \
         patch("src.services.content_poller.redis_processed_cache.redis.Redis", return_value=mock_redis):
        yield RedisProcessedCache(host="localhost", port=6379)


class TestRedisProcessedCacheExists:
    def test_returns_true_when_key_exists(self, cache, mock_redis):
        mock_redis.exists.return_value = 1

        assert cache.exists("reddit", "abc123") is True
        mock_redis.exists.assert_called_once_with(f"{_KEY_PREFIX}:reddit:abc123")

    def test_returns_false_when_key_missing(self, cache, mock_redis):
        mock_redis.exists.return_value = 0

        assert cache.exists("espn", "xyz789") is False
        mock_redis.exists.assert_called_once_with(f"{_KEY_PREFIX}:espn:xyz789")

    def test_returns_false_on_redis_error(self, cache, mock_redis):
        mock_redis.exists.side_effect = Exception("Connection refused")

        assert cache.exists("reddit", "abc123") is False


class TestRedisProcessedCacheMarkProcessed:
    def test_sets_key_with_ttl(self, cache, mock_redis):
        cache.mark_processed("reddit", "abc123")

        mock_redis.set.assert_called_once_with(f"{_KEY_PREFIX}:reddit:abc123", 1, ex=_TTL_SECONDS)

    def test_ttl_is_one_hour(self):
        assert _TTL_SECONDS == 3600

    def test_does_not_raise_on_redis_error(self, cache, mock_redis):
        mock_redis.set.side_effect = Exception("Connection refused")

        cache.mark_processed("reddit", "abc123")  # should not raise


class TestRedisProcessedCacheKeyFormat:
    def test_key_includes_source_and_id(self, cache, mock_redis):
        mock_redis.exists.return_value = 0
        cache.exists("bbc_sport", "0a1b2c3d4e5f6789")

        mock_redis.exists.assert_called_once_with(f"{_KEY_PREFIX}:bbc_sport:0a1b2c3d4e5f6789")

    def test_mark_and_check_use_same_key(self, cache, mock_redis):
        cache.mark_processed("espn", "article42")
        cache.exists("espn", "article42")

        expected_key = f"{_KEY_PREFIX}:espn:article42"
        mock_redis.set.assert_called_once_with(expected_key, 1, ex=_TTL_SECONDS)
        mock_redis.exists.assert_called_once_with(expected_key)


class TestGetProcessedCache:
    def test_returns_cache_on_success(self):
        with patch("src.services.content_poller.redis_processed_cache.Logger"), \
             patch("src.services.content_poller.redis_processed_cache.get_config_service") as mock_config, \
             patch("src.services.content_poller.redis_processed_cache.redis.Redis"):
            mock_config.return_value.get.side_effect = lambda key: {"redis.host": "localhost", "redis.port": "6379"}[key]

            result = get_processed_cache()
            assert isinstance(result, RedisProcessedCache)

    def test_returns_none_on_failure(self):
        with patch("src.services.content_poller.redis_processed_cache.Logger"), \
             patch("src.services.content_poller.redis_processed_cache.get_config_service", side_effect=Exception("no config")):

            result = get_processed_cache()
            assert result is None
