"""Deduplication Cache Interface - defines the contract for article dedup checks."""
from abc import ABC, abstractmethod


class DedupCache(ABC):
    @abstractmethod
    def exists(self, source: str, source_id: str) -> bool:
        pass

    @abstractmethod
    def mark_seen(self, source: str, source_id: str) -> None:
        pass
