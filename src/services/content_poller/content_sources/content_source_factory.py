"""Factory for building content sources from configuration."""
from typing import List

from src.services.content_poller.content_sources.reddit_content_source import (
    RedditContentSource,
    DEFAULT_SUBREDDITS,
)
from src.services.content_poller.content_sources.rss_content_source import RSSContentSource
from src.shared.appconfig_client import AppConfigClient
from src.shared.interfaces.content_source import ContentSource
from src.shared.observability.logs.logger import Logger


def build_content_sources(config: AppConfigClient) -> List[ContentSource]:
    logger = Logger()
    sources: List[ContentSource] = []

    try:
        client_id = config.get("reddit.client_id", "")
        client_secret = config.get("reddit.client_secret", "")
        if client_id and client_secret:
            user_agent = config.get("reddit.user_agent", "simple_sport_news/1.0")
            default_csv = ",".join(DEFAULT_SUBREDDITS)
            subreddits_raw = config.get("reddit.subreddits", default_csv)
            subreddits = [s.strip() for s in subreddits_raw.split(",")]
            sources.append(RedditContentSource(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                subreddits=subreddits,
            ))
    except Exception as e:
        logger.warning(f"Reddit source not configured: {e}")

    rss_feeds = {
        "espn": config.get("rss.espn_feeds", "").split(","),
        "bbc_sport": config.get("rss.bbc_feeds", "").split(","),
        "the_athletic": config.get("rss.athletic_feeds", "").split(","),
    }
    for source_name, feeds in rss_feeds.items():
        valid_feeds = [f.strip() for f in feeds if f.strip()]
        if valid_feeds:
            sources.append(RSSContentSource(source_name=source_name, feed_urls=valid_feeds))

    return sources
