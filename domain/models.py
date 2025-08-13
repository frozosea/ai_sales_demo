from dataclasses import dataclass, field
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
    # First-chunk metadata
    is_safe: Optional[bool] = None
    aggression_score: Optional[int] = None
    network_latency_ms: Optional[float] = None  # Time from request sent to first byte received
    inference_ttft_ms: Optional[float] = None   # Time from first byte to first usable content chunk

# Для client.stream_structured_generate(...) — разрешён любой Pydantic BaseModel
# Пример целевой структуры для стрима:
class LLMStructuredResponse(BaseModel):
    internal_thought: Optional[str] = None
    is_safe: Optional[bool] = True
    answer: str
    network_latency_ms: Optional[float] = None
    inference_ttft_ms: Optional[float] = None

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

@dataclass
class Task:
    """Описывает одну активную задачу (основную цель или отвлечение)."""
    goal_id: str
    status: Literal['IN_PROGRESS', 'PAUSED']
    mode: Literal['NORMAL', 'FORCED'] = 'NORMAL'  # Режим выполнения
    return_state_id: Optional[str] = None # Куда вернуться после прерывания

class SessionState(BaseModel):
    """
    Полное состояние одного звонка.
    Этот объект — "единый источник правды" для Оркестратора.
    """
    call_id: str
    current_state_id: str = "start"
    variables: Dict[str, Any] = {}
    state_history: List[str] = []
    previous_intent_leader: Optional[str] = None
    turn_state: Literal['BOT_TURN', 'USER_TURN'] = 'BOT_TURN'
    task_stack: List[Task] = []


@dataclass
class FlowResult:
    """Результат работы FlowEngine."""
    next_state: str
    should_guide_back: bool = False
    task_stack: List[Task] = field(default_factory=lambda: [])
