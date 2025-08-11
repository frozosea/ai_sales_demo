from dataclasses import dataclass
from typing import Optional, Literal, TypedDict, List, Dict, Any 
from pydantic import BaseModel

Role = Literal["user", "assistant", "system"]

class ConversationMessage(TypedDict):
    role: Role
    content: str

ConversationHistory = List[ConversationMessage]

@dataclass(slots=True)
class LLMStreamChunk:
    text_chunk: str
    is_final_chunk: bool = False
    # first-chunk metadata
    is_safe: Optional[bool] = None
    aggression_score: Optional[int] = None

# Для client.stream_structured_generate(...) — разрешён любой Pydantic BaseModel
# Пример целевой структуры для стрима:
class LLMStructuredResponse(BaseModel):
    internal_thought: Optional[str] = None
    is_safe: Optional[bool] = True
    answer: str

@dataclass(slots=True)
class IntentResult:
    intent_id: str
    score: float
    entities: Optional[Dict[str, Any]]
    current_leader: str



@dataclass(slots=True)
class FaqResult:
    question_id: str
    answer_text: str
    score: float
