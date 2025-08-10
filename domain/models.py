from dataclasses import dataclass
from typing import Optional, Dict, Any

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
