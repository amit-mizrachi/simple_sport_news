"""Content Poller Service - background polling with health server."""
import asyncio
import signal

from src.services.content_poller.content_sources.content_source_factory import build_content_sources
from src.services.content_poller.content_processor import ContentProcessor
from src.services.content_poller.redis_processed_cache import get_processed_cache
from src.services.content_poller.content_poller import ContentPoller
from src.shared.observability.logs.logger import Logger
from src.shared.observability.traces.tracer import Tracer
from src.shared.messaging.messaging_factory import get_message_publisher
from src.shared.appconfig_client import get_config_service
from src.shared.repositories.mongodb_article_repository import get_content_repository
from src.shared.health import start_health_server_background

logger = Logger()
tracer = Tracer()


def create_content_poller() -> ContentPoller:
    config = get_config_service()
    ingester = ContentProcessor(
        content_repository=get_content_repository(),
        message_publisher=get_message_publisher(),
        content_topic=config.get("topics.content_raw", "content-raw"),
        processed_cache=get_processed_cache(),
    )
    return ContentPoller(
        sources=build_content_sources(config),
        processor=ingester,
        poll_interval=int(config.get("poller.interval_seconds", 300)),
    )


async def main():
    logger.info("Starting Content Poller Service")

    poller = create_content_poller()

    port = int(get_config_service().get("services.content_poller.port"))
    logger.info(f"Starting health server on port {port}")
    health_task = start_health_server_background(
        service_name="Content Poller Service",
        port=port
    )

    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        tracer.shutdown()
        logger.flush()
        poller.stop()
        health_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    await poller.run()


if __name__ == "__main__":
    asyncio.run(main())
