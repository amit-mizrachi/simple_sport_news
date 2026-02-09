from abc import ABC, abstractmethod


class AsyncMessageConsumer(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass
