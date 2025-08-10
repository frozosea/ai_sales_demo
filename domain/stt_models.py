from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class STTResponse:
    text: str
    is_final: bool
    stability_level: float
    utterance_index: int

@dataclass(slots=True)
class STTConfig:
    endpoint: str
    language_code: str
    model: str
    sample_rate_hertz: int
    audio_encoding: str
    container_audio: bool = False  # Whether to use container_audio instead of raw_audio
    partial_results: bool = True
    single_utterance: bool = False
    profanity_filter: bool = False
    raw_results: bool = False
    eou_sensitivity: float = 0.5
    normalize_partials: bool = True

class STTConnectionError(RuntimeError):
    pass 