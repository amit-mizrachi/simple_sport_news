"""Content Poller - periodically fetches content from configured content_sources."""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from src.shared.interfaces.repositories.article_repository import ArticleRepository
from src.shared.interfaces.content_source import ContentSource
from src.shared.interfaces.messaging.message_publisher import MessagePublisher
from src.shared.objects.messages.content_message import ContentMessage
from src.services.content_poller.dedup_cache import DeduplicationCache
from src.shared.observability.logs.logger import Logger
from src.shared.observability.traces.spans.span_context_factory import SpanContextFactory
from src.shared.observability.traces.spans.spanner import Spanner
from src.shared.messaging.context_preserving_thread_pool import ContextPreservingThreadPool


class ContentPoller:
    def __init__(
        self,
        sources: List[ContentSource],
        content_repository: ArticleRepository,
        message_publisher: MessagePublisher,
        content_topic: str = "content-raw",
        poll_interval: int = 300,
        dedup_cache: Optional[DeduplicationCache] = None,
    ):
        self._logger = Logger()
        self._spanner = Spanner()
        self._sources = sources
        self._content_repository = content_repository
        self._message_publisher = message_publisher
        self._content_topic = content_topic
        self._poll_interval = poll_interval
        self._dedup_cache = dedup_cache
        self._thread_pool = ContextPreservingThreadPool(max_workers=len(sources))
        self._running = True
        self._last_poll: datetime = datetime.now(tz=timezone.utc)

    async def run(self):
        self._logger.info("Content poller started")
        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                self._logger.error(f"Poll cycle error: {e}")

            await asyncio.sleep(self._poll_interval)

    async def _poll_cycle(self):
        with SpanContextFactory.internal("content_poller", "poll_cycle"):
            loop = asyncio.get_running_loop()

            # Phase 1: Fetch all sources in parallel via thread pool
            fetch_futures = [
                loop.run_in_executor(self._thread_pool, self._fetch_source, source)
                for source in self._sources
            ]
            results = await asyncio.gather(*fetch_futures, return_exceptions=True)

            # Phase 2: Process items sequentially (dedup -> build -> publish -> mark)
            for source, result in zip(self._sources, results):
                if isinstance(result, Exception):
                    self._logger.error(f"Error fetching from {source.get_source_name()}: {result}")
                    continue

                self._logger.info(f"Fetched {len(result)} items from {source.get_source_name()}")

                for item in result:
                    try:
                        if self._is_duplicate(item.source, item.source_id):
                            continue

                        telemetry_headers = self._spanner.inject_telemetry_context({})

                        message = ContentMessage(
                            request_id=str(uuid.uuid4()),
                            raw_content=item,
                            telemetry_headers=telemetry_headers,
                        )
                        with SpanContextFactory.producer(self._content_topic):
                            self._message_publisher.publish(
                                self._content_topic, message.model_dump_json()
                            )

                        if self._dedup_cache:
                            self._dedup_cache.mark_seen(item.source, item.source_id)
                    except Exception as e:
                        self._logger.error(f"Error processing item from {source.get_source_name()}: {e}")

            self._last_poll = datetime.now(tz=timezone.utc)

    def _fetch_source(self, source: ContentSource):
        """Fetch latest items from a single source. Runs in a worker thread."""
        with SpanContextFactory.client("HTTP", source, "content_poller", "fetch_latest"):
            return source.fetch_latest(since=self._last_poll)

    def _is_duplicate(self, source: str, source_id: str) -> bool:
        """Check dedup cache first (Redis Set, sub-ms), fall back to MongoDB."""
        if self._dedup_cache:
            with SpanContextFactory.client("REDIS", self._dedup_cache, "content_poller", "dedup_check"):
                if self._dedup_cache.exists(source, source_id):
                    return True
        with SpanContextFactory.client("MONGODB", self._content_repository, "content_poller", "article_exists"):
            return self._content_repository.article_exists(source, source_id)

    def stop(self):
        self._running = False
        self._thread_pool.shutdown(wait=False)
