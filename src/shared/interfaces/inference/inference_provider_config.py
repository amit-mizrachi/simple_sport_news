"""Inference Provider Config interface."""
from abc import ABC, abstractmethod

from src.shared.interfaces.llm_provider import LLMProvider
from src.shared.objects.enums.inference_mode import InferenceMode


class LLMProviderConfig(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        pass

    @property
    @abstractmethod
    def endpoint(self) -> str:
        pass

    @property
    @abstractmethod
    def inference_mode(self) -> InferenceMode:
        pass

    @abstractmethod
    def create_provider(self) -> LLMProvider:
        pass
