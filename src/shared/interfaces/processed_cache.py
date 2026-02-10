"""Processed Cache Interface - defines the contract for article processed checks."""
from abc import ABC, abstractmethod


class ProcessedCache(ABC):
    @abstractmethod
    def exists(self, source: str, source_id: str) -> bool:
        pass

    @abstractmethod
    def mark_processed(self, source: str, source_id: str) -> None:
        pass
