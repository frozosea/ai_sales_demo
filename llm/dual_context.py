from __future__ import annotations
import asyncio
import logging
import json
import time
from typing import Optional

from llm.context import LLMContext
from domain.models import ConversationMessage

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.dual")

def jlog(data: dict):
    logger.info(json.dumps(data))

class DualContextController:
    def __init__(self, active_context: LLMContext, warmup_threshold: float, handover_threshold: float):
        self.active_context = active_context
        self.standby_context: Optional[LLMContext] = None
        self.warmup_task: Optional[asyncio.Task] = None
        
        self._warmup_threshold = warmup_threshold
        self._handover_threshold = handover_threshold
        self._warmup_ready_time: Optional[float] = None

    def on_user_message(self, message: ConversationMessage) -> float:
        self.active_context.add_message(message)
        return self.active_context.estimate_usage_ratio()

    def should_warmup(self, usage_ratio: float) -> bool:
        return usage_ratio >= self._warmup_threshold and self.warmup_task is None and self.standby_context is None

    def should_handover(self, usage_ratio: float) -> bool:
        return usage_ratio >= self._handover_threshold and self.standby_context is not None

    def set_standby(self, context: LLMContext):
        jlog({"event": "warmup_ready"})
        self._warmup_ready_time = time.monotonic()
        self.standby_context = context
        if self.warmup_task:
            self.warmup_task = None

    def perform_handover(self):
        if self.standby_context:
            t_handover = time.monotonic()
            if self._warmup_ready_time:
                ms_since_ready = (t_handover - self._warmup_ready_time) * 1000
                jlog({"event": "handover_perform", "ms_from_warmup_ready": ms_since_ready})
            
            self.active_context = self.standby_context
            self.standby_context = None
            self._warmup_ready_time = None
            # The new active context now reflects the summarized history
            jlog({"event": "handover_complete", "new_active_context_ratio": self.active_context.estimate_usage_ratio()})

    def cancel_warmup_if_running(self):
        if self.warmup_task and not self.warmup_task.done():
            self.warmup_task.cancel()
            self.warmup_task = None
            jlog({"event": "warmup_cancelled"})

if __name__ == "__main__":
    async def main():
        # Dummy context for testing
        class MockLLMContext(LLMContext):
            _usage = 0.0
            def estimate_usage_ratio(self) -> float:
                return self._usage
            def add_message(self, message: ConversationMessage):
                self._usage += 0.2 # Increment usage
        
        active_ctx = MockLLMContext({}, 1000, "gpt-4")
        controller = DualContextController(active_ctx, warmup_threshold=0.5, handover_threshold=0.9)

        async def warmup_simulation():
            jlog({"event": "warmup_start"})
            await asyncio.sleep(1) # Simulate work
            new_context = MockLLMContext({}, 1000, "gpt-4")
            new_context._usage = 0.1 # Summarized context is smaller
            controller.set_standby(new_context)

        # Simulate conversation
        for i in range(5):
            print(f"\n--- Turn {i+1} ---")
            usage = controller.on_user_message({"role": "user", "content": f"Message {i}"})
            print(f"Usage ratio: {usage:.2f}")

            if controller.should_warmup(usage):
                print("Warmup threshold reached. Starting warmup task.")
                controller.warmup_task = asyncio.create_task(warmup_simulation())
            
            if controller.should_handover(usage):
                print("Handover threshold reached. Performing handover.")
                controller.perform_handover()
            
            await asyncio.sleep(0.5)

        # Wait for any pending warmup task to finish
        if controller.warmup_task:
            await controller.warmup_task

    asyncio.run(main())
