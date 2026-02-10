"""Tests for ContentPoller and ContentSourceFactory."""
import asyncio
from concurrent.futures import Future
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.objects.content.raw_article import RawArticle
from src.services.content_poller.content_poller import ContentPoller
from src.services.content_poller.content_sources.content_source_factory import build_content_sources
from src.services.content_poller.content_sources.rss_content_source import RSSContentSource


def _make_article(source: str = "reddit", source_id: str = "abc123") -> RawArticle:
    return RawArticle(
        source=source,
        source_id=source_id,
        source_url=f"https://example.com/{source_id}",
        title="Test article",
        content="Test content",
        published_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        metadata={},
    )


def _make_thread_pool():
    """Create a mock thread pool whose submit() returns real Futures."""
    pool = MagicMock()

    def submit_fn(fn, *args):
        f = Future()
        try:
            f.set_result(fn(*args))
        except Exception as exc:
            f.set_exception(exc)
        return f

    pool.submit.side_effect = submit_fn
    return pool


def _make_span_context_factory():
    mock_scf = MagicMock()
    for method in ("internal", "producer", "client"):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock()
        ctx.__exit__ = MagicMock(return_value=False)
        getattr(mock_scf, method).return_value = ctx
    return mock_scf


@pytest.fixture
def poller(mock_content_source, mock_content_repository, mock_message_publisher, mock_dedup_cache):
    with patch("src.services.content_poller.poller.Spanner") as mock_spanner_cls, \
         patch("src.services.content_poller.poller.SpanContextFactory", _make_span_context_factory()), \
         patch("src.services.content_poller.poller.ContextPreservingThreadPool", return_value=_make_thread_pool()):
        mock_spanner_cls.return_value.inject_telemetry_context.return_value = {}

        yield ContentPoller(
            sources=[mock_content_source],
            content_repository=mock_content_repository,
            message_publisher=mock_message_publisher,
            dedup_cache=mock_dedup_cache,
        )


class TestContentPoller:
    def test_poll_cycle_fetches_and_publishes(
        self, poller, mock_content_source, mock_message_publisher, mock_dedup_cache
    ):
        items = [_make_article(source_id="a1"), _make_article(source_id="a2")]
        mock_content_source.fetch_latest.return_value = items
        mock_dedup_cache.exists.return_value = False

        asyncio.get_event_loop().run_until_complete(poller._poll_cycle())

        assert mock_message_publisher.publish.call_count == 2
        assert mock_dedup_cache.mark_seen.call_count == 2

    def test_poll_cycle_skips_duplicates(
        self, poller, mock_content_source, mock_message_publisher, mock_dedup_cache
    ):
        items = [_make_article(source_id="dup1")]
        mock_content_source.fetch_latest.return_value = items
        mock_dedup_cache.exists.return_value = True

        asyncio.get_event_loop().run_until_complete(poller._poll_cycle())

        mock_message_publisher.publish.assert_not_called()

    def test_poll_cycle_falls_back_to_mongo_dedup(
        self, poller, mock_content_source, mock_content_repository, mock_message_publisher, mock_dedup_cache
    ):
        items = [_make_article(source_id="mongo_dup")]
        mock_content_source.fetch_latest.return_value = items
        mock_dedup_cache.exists.return_value = False
        mock_content_repository.article_exists.return_value = True

        asyncio.get_event_loop().run_until_complete(poller._poll_cycle())

        mock_message_publisher.publish.assert_not_called()

    def test_poll_cycle_handles_source_fetch_error(
        self, mock_content_repository, mock_message_publisher, mock_dedup_cache
    ):
        source_ok = MagicMock()
        source_ok.get_source_name.return_value = "ok_source"
        source_ok.fetch_latest.return_value = [_make_article(source_id="ok1")]

        source_bad = MagicMock()
        source_bad.get_source_name.return_value = "bad_source"
        source_bad.fetch_latest.side_effect = ConnectionError("network down")

        with patch("src.services.content_poller.poller.Spanner") as mock_spanner_cls, \
             patch("src.services.content_poller.poller.SpanContextFactory", _make_span_context_factory()), \
             patch("src.services.content_poller.poller.ContextPreservingThreadPool", return_value=_make_thread_pool()):
            mock_spanner_cls.return_value.inject_telemetry_context.return_value = {}

            p = ContentPoller(
                sources=[source_bad, source_ok],
                content_repository=mock_content_repository,
                message_publisher=mock_message_publisher,
                dedup_cache=mock_dedup_cache,
            )

            asyncio.get_event_loop().run_until_complete(p._poll_cycle())

        mock_message_publisher.publish.assert_called_once()

    def test_poll_cycle_handles_item_processing_error(
        self, poller, mock_content_source, mock_message_publisher, mock_dedup_cache
    ):
        items = [_make_article(source_id="err1"), _make_article(source_id="ok1")]
        mock_content_source.fetch_latest.return_value = items
        mock_dedup_cache.exists.return_value = False

        call_count = 0

        def publish_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("publish failed")

        mock_message_publisher.publish.side_effect = publish_side_effect

        asyncio.get_event_loop().run_until_complete(poller._poll_cycle())

        # Second item should still be processed (publish called twice total)
        assert mock_message_publisher.publish.call_count == 2

    def test_stop_sets_running_false(self, poller):
        assert poller._running is True
        poller.stop()
        assert poller._running is False


class TestContentSourceFactory:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.get.return_value = ""
        return config

    def test_builds_reddit_source_when_configured(self, mock_config):
        mock_config.get.side_effect = lambda key, default="": {
            "reddit.client_id": "id123",
            "reddit.client_secret": "secret456",
            "reddit.user_agent": "test/1.0",
            "reddit.subreddits": "soccer,nba",
            "rss.espn_feeds": "",
            "rss.bbc_feeds": "",
            "rss.athletic_feeds": "",
        }.get(key, default)

        with patch("src.services.content_poller.content_sources.content_source_factory.RedditContentSource") as mock_cls:
            sources = build_content_sources(mock_config)
            mock_cls.assert_called_once_with(
                client_id="id123",
                client_secret="secret456",
                user_agent="test/1.0",
                subreddits=["soccer", "nba"],
            )

    def test_builds_rss_sources_when_configured(self, mock_config):
        mock_config.get.side_effect = lambda key, default="": {
            "reddit.client_id": "",
            "reddit.client_secret": "",
            "rss.espn_feeds": "http://espn.com/feed1,http://espn.com/feed2",
            "rss.bbc_feeds": "http://bbc.com/feed",
            "rss.athletic_feeds": "",
        }.get(key, default)

        sources = build_content_sources(mock_config)
        rss_sources = [s for s in sources if isinstance(s, RSSContentSource)]
        assert len(rss_sources) == 2
        assert rss_sources[0].get_source_name() == "espn"
        assert rss_sources[1].get_source_name() == "bbc_sport"

    def test_skips_reddit_when_not_configured(self, mock_config):
        mock_config.get.side_effect = lambda key, default="": {
            "reddit.client_id": "",
            "reddit.client_secret": "",
            "rss.espn_feeds": "",
            "rss.bbc_feeds": "",
            "rss.athletic_feeds": "",
        }.get(key, default)

        with patch("src.services.content_poller.content_sources.content_source_factory.RedditContentSource") as mock_cls:
            sources = build_content_sources(mock_config)
            mock_cls.assert_not_called()
        assert len(sources) == 0
