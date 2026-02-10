"""Content Processor - checks processed cache, wraps, and publishes raw articles to the processing pipeline."""
import uuid
from typing import Optional

from src.shared.interfaces.repositories.article_repository import ArticleRepository
from src.shared.interfaces.messaging.message_publisher import MessagePublisher
from src.shared.interfaces.processed_cache import ProcessedCache
from src.shared.objects.content.raw_article import RawArticle
from src.shared.objects.messages.content_message import ContentMessage
from src.shared.observability.logs.logger import Logger
from src.shared.observability.traces.spans.span_context_factory import SpanContextFactory
from src.shared.observability.traces.spans.spanner import Spanner


class ContentProcessor:
    def __init__(
        self,
        content_repository: ArticleRepository,
        message_publisher: MessagePublisher,
        content_topic: str,
        processed_cache: Optional[ProcessedCache] = None,
    ):
        self._logger = Logger()
        self._spanner = Spanner()
        self._content_repository = content_repository
        self._message_publisher = message_publisher
        self._content_topic = content_topic
        self._processed_cache = processed_cache

    def process(self, item: RawArticle) -> None:
        if self._article_processed(item.source, item.source_id):
            return

        self._publish_message(item)

        if self._processed_cache:
            self._processed_cache.mark_processed(item.source, item.source_id)

    def _article_processed(self, source: str, source_id: str) -> bool:
        if self._processed_cache:
            with SpanContextFactory.client("REDIS", self._processed_cache, "content_processor", "processed_check"):
                if self._processed_cache.exists(source, source_id):
                    return True

        with SpanContextFactory.client("MONGODB", self._content_repository, "content_processor", "article_exists"):
            return self._content_repository.article_exists(source, source_id)

    def _publish_message(self, item):
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
