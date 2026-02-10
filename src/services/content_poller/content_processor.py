"""Content Ingester - deduplicates, wraps, and publishes raw articles to the processing pipeline."""
import uuid
from typing import Optional

from src.shared.interfaces.repositories.article_repository import ArticleRepository
from src.shared.interfaces.messaging.message_publisher import MessagePublisher
from src.shared.interfaces.dedup_cache import DedupCache
from src.shared.objects.content.raw_article import RawArticle
from src.shared.objects.messages.content_message import ContentMessage
from src.shared.observability.logs.logger import Logger
from src.shared.observability.traces.spans.span_context_factory import SpanContextFactory
from src.shared.observability.traces.spans.spanner import Spanner


class ContentProcessor:
    """Validates incoming articles (dedup), builds messages, and publishes to Kafka."""

    def __init__(
        self,
        content_repository: ArticleRepository,
        message_publisher: MessagePublisher,
        content_topic: str,
        dedup_cache: Optional[DedupCache] = None,
    ):
        self._logger = Logger()
        self._spanner = Spanner()
        self._content_repository = content_repository
        self._message_publisher = message_publisher
        self._content_topic = content_topic
        self._dedup_cache = dedup_cache

    def process(self, item: RawArticle) -> None:
        """Dedup-check, build message, publish, and mark as seen."""
        if self._is_duplicate(item.source, item.source_id):
            return

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

    def _is_duplicate(self, source: str, source_id: str) -> bool:
        """Check dedup cache first (Redis, sub-ms), fall back to MongoDB."""
        if self._dedup_cache:
            with SpanContextFactory.client("REDIS", self._dedup_cache, "content_ingester", "dedup_check"):
                if self._dedup_cache.exists(source, source_id):
                    return True
        with SpanContextFactory.client("MONGODB", self._content_repository, "content_ingester", "article_exists"):
            return self._content_repository.article_exists(source, source_id)
