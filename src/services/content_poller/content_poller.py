"""Content Poller - periodically fetches content from configured content_sources."""
import asyncio
from datetime import datetime, timezone
from typing import List

from src.shared.interfaces.content_source import ContentSource
from src.services.content_poller.content_processor import ContentProcessor
from src.shared.observability.logs.logger import Logger
from src.shared.observability.traces.spans.span_context_factory import SpanContextFactory
from src.shared.messaging.context_preserving_thread_pool import ContextPreservingThreadPool


class ContentPoller:
    def __init__(
        self,
        sources: List[ContentSource],
        processor: ContentProcessor,
        poll_interval: int = 300,
    ):
        self._logger = Logger()
        self._sources = sources
        self._processor = processor
        self._poll_interval = poll_interval
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

            # Phase 2: Ingest items sequentially (dedup -> build -> publish -> mark)
            for source, result in zip(self._sources, results):
                if isinstance(result, Exception):
                    self._logger.error(f"Error fetching from {source.get_source_name()}: {result}")
                    continue

                self._logger.info(f"Fetched {len(result)} items from {source.get_source_name()}")

                for item in result:
                    try:
                        self._processor.process(item)
                    except Exception as e:
                        self._logger.error(f"Error ingesting item from {source.get_source_name()}: {e}")

            self._last_poll = datetime.now(tz=timezone.utc)

    def _fetch_source(self, source: ContentSource):
        """Fetch latest items from a single source. Runs in a worker thread."""
        with SpanContextFactory.client("HTTP", source, "content_poller", "fetch_latest"):
            return source.fetch_latest(since=self._last_poll)

    def stop(self):
        self._running = False
        self._thread_pool.shutdown(wait=False)
