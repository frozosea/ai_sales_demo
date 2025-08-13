import asyncio
import argparse
import time
import json
import sys
from typing import List, Dict, Any, Optional, AsyncGenerator
from pathlib import Path
import yaml

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from orchestrator.orchestrator import Orchestrator
from flow_engine.engine import FlowEngine
from domain.models import SessionState, LLMStreamChunk
from domain.stt_models import STTResponse

# --- Mock Objects for Dependencies ---

class MockSTTStreamer:
    def __init__(self, scenario: List[STTResponse], should_fail: bool = False):
        self._scenario = scenario
        self._should_fail = should_fail
        self._queue = asyncio.Queue()

    async def start_recognition(self, audio_chunk_queue: asyncio.Queue) -> asyncio.Queue:
        if self._should_fail:
            # Simulate immediate failure
            response_queue = asyncio.Queue()
            await response_queue.put((None, "Simulated STT Connection Error"))
            return response_queue
        
        asyncio.create_task(self._run_scenario())
        return self._queue

    async def _run_scenario(self):
        for item in self._scenario:
            await asyncio.sleep(0.5) # Simulate network/processing delay
            await self._queue.put((item, None))
        await self._queue.put((None, None)) # End of stream

    async def stop_recognition(self):
        print("LOG: STT Streamer stopped.")

class MockIntentClassifier:
    def __init__(self, should_fail: bool = False):
        self._should_fail = should_fail

    async def classify_intent(self, text: str, expected_intents: List[str], previous_leader: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if self._should_fail:
            raise RuntimeError("Simulated Intent Classifier Error")
        
        # Simple rule-based mock
        for intent in expected_intents:
            if intent.split('_')[-1] in text.lower():
                return {"intent_id": intent, "score": 0.9, "entities": {}, "current_leader": intent}
        return None

    async def find_faq_answer(self, text: str) -> Optional[Dict[str, Any]]:
        if "небезопасно" in text:
            # To test the unsafe LLM content scenario
            return None
        if "компания" in text:
            return {"question_id": "faq_company", "answer_text": "Мы - лучшая компания в мире!", "score": 0.95}
        return None

class MockLLMManager:
    def __init__(self, should_fail: bool = False, simulate_unsafe: bool = False):
        self._should_fail = should_fail
        self._simulate_unsafe = simulate_unsafe

    async def process_user_turn(self, final_user_text: str) -> AsyncGenerator[LLMStreamChunk, None]:
        if self._should_fail:
            raise RuntimeError("Simulated LLM Manager Error")
        
        if self._simulate_unsafe:
            # is_safe is a part of the LLMStreamChunk dataclass
            yield LLMStreamChunk(text_chunk="Это небезопасный ответ.", is_final_chunk=False, is_safe=False)
            return

        response = f"Ответ на '{final_user_text}'"
        for chunk in response.split():
            await asyncio.sleep(0.1)
            yield LLMStreamChunk(text_chunk=chunk + " ", is_final_chunk=False, is_safe=True)
        yield LLMStreamChunk(text_chunk="", is_final_chunk=True, is_safe=True)

    async def shutdown(self):
        print("LOG: LLM Manager shut down.")

class MockTTSManager:
    def __init__(self, should_fail: bool = False):
        self._should_fail = should_fail

    async def stream_static_text(self, text: str) -> AsyncGenerator[bytes, None]:
        if self._should_fail:
            raise ConnectionError("Simulated TTS Failure")
        print(f"LOG: TTS streaming text: '{text}'")
        yield b"audio_chunk_1"
        await asyncio.sleep(0.1)
        yield b"audio_chunk_2"

    async def start_llm_stream(self) -> (asyncio.Queue, asyncio.Queue):
        if self._should_fail:
            raise ConnectionError("Simulated TTS Failure on LLM stream")
        return asyncio.Queue(), asyncio.Queue()

class MockCache:
    def __init__(self):
        self._data = {}

    async def get(self, key: str) -> Optional[List[bytes]]:
        print(f"LOG: Cache GET for key: {key}")
        return self._data.get(key)

    async def set(self, key: str, value: List[bytes]):
        print(f"LOG: Cache SET for key: {key}")
        self._data[key] = value

class MockStream:
    def __init__(self):
        self.written_data = []

    async def write(self, data: bytes):
        self.written_data.append(data)
        print(f"LOG: Outbound stream received {len(data)} bytes.")

    async def __aiter__(self):
        # This makes the stream awaitable for the orchestrator's input loop
        yield b"dummy_audio_chunk"

class MetricsLogger:
    def __init__(self):
        self.logs = []
        self.start_time = time.perf_counter()

    def log(self, event: str, **kwargs):
        log_entry = {
            "timestamp": time.perf_counter() - self.start_time,
            "event": event,
            **kwargs
        }
        self.logs.append(log_entry)
        print(f"METRIC: {json.dumps(log_entry)}")

    def print_summary(self):
        print("\n--- METRICS SUMMARY ---")
        for log in self.logs:
            print(f"- {log['event']} at {log['timestamp']:.2f}s with data: {log}")
        print("-----------------------\n")


async def run_test_scenario(args):
    """Initializes and runs the full test scenario."""
    
    # --- 1. Load Configs ---
    print("--- Loading configurations ---")
    with open("configs/dialogue_flow_with_playlists.json", "r") as f:
        dialogue_map = json.load(f)
    
    # --- 2. Define Test Scenario ---
    # This scenario is based on the testing_spec.md
    stt_scenario = [
        # Each item is a mock STTResponse tuple: (response, error)
        STTResponse(text="Да это я", is_final=True, stability_level=0.9, utterance_index=0),
        STTResponse(text="А что за компания", is_final=True, stability_level=0.9, utterance_index=1),
        # Simulate barge-in text
        STTResponse(text="Стой хватит какая цена", is_final=True, stability_level=0.9, utterance_index=2),
        STTResponse(text="Какая цена говорю", is_final=True, stability_level=0.9, utterance_index=3),
        STTResponse(text="Пять миллионов", is_final=True, stability_level=0.9, utterance_index=4),
        STTResponse(text="Что-то у вас всё сломалось", is_final=True, stability_level=0.9, utterance_index=5),
        STTResponse(text="Это небезопасно", is_final=True, stability_level=0.9, utterance_index=6),
        STTResponse(text="Всё мне не интересно до свидания", is_final=True, stability_level=0.9, utterance_index=7),
    ]

    # --- 3. Initialize Mocks & Dependencies ---
    print("--- Initializing mocks and dependencies ---")
    stt_streamer = MockSTTStreamer(stt_scenario, should_fail=args.simulate_stt_failure)
    intent_classifier = MockIntentClassifier(should_fail=args.simulate_intent_failure)
    llm_manager = MockLLMManager(should_fail=args.simulate_llm_failure, simulate_unsafe=args.simulate_llm_unsafe)
    tts_manager = MockTTSManager(should_fail=args.simulate_tts_failure)
    cache = MockCache()
    # Pre-populate cache for fallback response
    await cache.set("non_secure_response", [b"fallback_audio"])
    
    flow_engine = FlowEngine(goals_config_path="configs/goals.json", dialogue_map_path="configs/dialogue_flow_with_playlists.json")
    
    # --- 4. Create Orchestrator ---
    orchestrator = Orchestrator(
        call_id="test_call_001",
        flow_engine=flow_engine,
        intent_classifier=intent_classifier,
        llm_manager=llm_manager,
        tts_manager=tts_manager,
        stt_streamer=stt_streamer,
        cache=cache,
        neutral_fillers_keys=["filler:still_working"],
        non_secure_response="non_secure_response",
        dialogue_map=dialogue_map,
    )
    orchestrator.session_state.current_state_id = "start_greeting"
    
    # --- 5. Run Orchestrator ---
    print("\n--- STARTING ORCHESTRATOR RUN ---")
    inbound_stream = MockStream()
    outbound_stream = MockStream()
    
    # This is a simplified run. A real test would feed the stt_scenario into the inbound stream as audio
    # and verify the outbound_stream content. For this manual test, we feed STT responses directly.
    await orchestrator.run(inbound_stream, outbound_stream)
    
    print("\n--- ORCHESTRATOR RUN COMPLETED ---\n")
    

def main():
    parser = argparse.ArgumentParser(description="Manual E2E test for Orchestrator")
    parser.add_argument("--simulate-stt-failure", action="store_true", help="Simulate a failure in the STT service.")
    parser.add_argument("--simulate-intent-failure", action="store_true", help="Simulate a failure in the Intent Classifier.")
    parser.add_argument("--simulate-llm-failure", action="store_true", help="Simulate a failure in the LLM service.")
    parser.add_argument("--simulate-tts-failure", action="store_true", help="Simulate a failure in the TTS service.")
    parser.add_argument("--simulate-llm-unsafe", action="store_true", help="Simulate the LLM returning unsafe content.")
    
    args = parser.parse_args()
    
    print("Test script initialized with the following flags:")
    print(json.dumps(vars(args), indent=2))
    
    asyncio.run(run_test_scenario(args))


if __name__ == "__main__":
    main()
