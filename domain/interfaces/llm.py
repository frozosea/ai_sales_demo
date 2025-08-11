import abc
import httpx
from typing import AsyncGenerator, Type, List, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from domain.models import ConversationMessage, ConversationHistory, LLMStreamChunk

class LLMConnectionManager(abc.ABC):
    @abc.abstractmethod
    async def get_client(self) -> httpx.AsyncClient: ...
    @abc.abstractmethod
    async def shutdown(self) -> None: ...

class AbstractLLMClient(abc.ABC):
    @abc.abstractmethod
    async def stream_structured_generate(
        self,
        http_client: httpx.AsyncClient,
        full_prompt: str,
        model: str,
        response_model: Type[BaseModel]
    ) -> AsyncGenerator[BaseModel, None]: ...

class AbstractLLMContext(abc.ABC):
    @abc.abstractmethod
    def add_message(self, message: "ConversationMessage") -> None: ...
    @abc.abstractmethod
    def build_prompt(self) -> str: ...
    @abc.abstractmethod
    def build_summary_prompt(self, history: "ConversationHistory") -> str: ...
    @abc.abstractmethod
    def get_history_for_summary(self) -> "ConversationHistory": ...
    @abc.abstractmethod
    def estimate_usage_ratio(self) -> float: ...

class AbstractConversationManager(abc.ABC):
    @abc.abstractmethod
    async def process_user_turn(self, final_user_text: str) -> AsyncGenerator["LLMStreamChunk", None]: ...
    @abc.abstractmethod
    async def shutdown(self) -> None: ...
