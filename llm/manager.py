from __future__ import annotations
import asyncio
import logging
import json
import time
import hashlib
from typing import AsyncGenerator, Set

import yaml

from domain.interfaces.llm import AbstractConversationManager
from domain.interfaces.cache import AbstractCache
from domain.models import LLMStreamChunk, ConversationMessage
from llm.connection import LLMConnectionManagerImpl
from llm.client import OpenAILLMClient, LLMStructuredResponse
from llm.context import LLMContext
from llm.dual_context import DualContextController

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.manager")

def jlog(data: dict):
    logger.info(json.dumps(data))

class ConversationManager(AbstractConversationManager):
    def __init__(self, config: dict, prompts: dict, cache: AbstractCache, session_id: str):
        self._config = config['llm']
        self._prompts = prompts
        self._cache = cache
        self._session_id_hash = hashlib.sha256(session_id.encode()).hexdigest()
        
        self.connection_manager = LLMConnectionManagerImpl(
            api_key=self._config['api_key'],
            timeout=self._config['http_timeout_sec'],
            keep_alive_interval=self._config['keep_alive_interval_sec']
        )
        self.llm_client = OpenAILLMClient()
        
        active_context = LLMContext(
            prompt_config=self._prompts,
            max_tokens=self._config['context_window_size'],
            model_name=self._config['models']['main']
        )
        
        self.dual_ctx = DualContextController(
            active_context=active_context,
            warmup_threshold=self._config['dual_context']['warmup_threshold_ratio'],
            handover_threshold=self._config['dual_context']['handover_threshold_ratio']
        )
        
        self._background_tasks: Set[asyncio.Task] = set()
        self._is_initialized = False

    async def initialize(self):
        await self.connection_manager.get_client()
        self._is_initialized = True
        jlog({"event": "manager_initialized"})

    async def _get_stream_iterator(self, model_name: str, prompt: str, low_latency: bool):
        """Helper to get an async iterator from the LLM client."""
        http_client = await self.connection_manager.get_client()
        stream = self.llm_client.stream_structured_generate(
            http_client,
            prompt,
            model_name,
            LLMStructuredResponse,
            low_latency_mode=low_latency
        )
        return stream.__aiter__()

    async def process_user_turn(
        self,
        final_user_text: str,
        low_latency_mode: bool = False
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        if not self._is_initialized:
            raise RuntimeError("ConversationManager must be initialized before processing a turn.")

        t_start_turn = time.monotonic()
        jlog({"event": "user_turn_start", "session_hash": self._session_id_hash})
        
        user_message: ConversationMessage = {"role": "user", "content": final_user_text}
        usage_ratio = self.dual_ctx.on_user_message(user_message)
        jlog({"event": "context_ratio_before", "ratio": usage_ratio})

        if self.dual_ctx.should_warmup(usage_ratio):
            task = asyncio.create_task(self._build_standby_context())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        full_prompt = self.dual_ctx.active_context.build_prompt()

        main_model = self._config['models']['main']
        draft_model = self._config['models'].get('draft', 'gpt-3.5-turbo')

        # Create iterators for both streams
        main_iterator = await self._get_stream_iterator(main_model, full_prompt, low_latency_mode)
        draft_iterator = await self._get_stream_iterator(draft_model, full_prompt, True)

        t_first_chunk = None
        full_response = ""
        draft_buffer = ""
        main_stream_finished = False
        first_chunk_metrics = {}

        try:
            while not main_stream_finished:
                # 1. Get a chunk from the draft model first
                try:
                    draft_chunk = await asyncio.wait_for(draft_iterator.__anext__(), timeout=0.05)
                    draft_token = draft_chunk.answer
                    
                    if t_first_chunk is None:
                        t_first_chunk = time.monotonic()
                        first_chunk_metrics = {
                            "network_latency_ms": draft_chunk.network_latency_ms,
                            "inference_ttft_ms": draft_chunk.inference_ttft_ms
                        }
                        jlog({
                            "event": "time_to_first_token_ms", 
                            "ms": (t_first_chunk - t_start_turn) * 1000, 
                            "source": "draft",
                            **first_chunk_metrics
                        })
                        yield LLMStreamChunk(
                            text_chunk=draft_token, 
                            network_latency_ms=draft_chunk.network_latency_ms, 
                            inference_ttft_ms=draft_chunk.inference_ttft_ms
                        )
                    else:
                        draft_buffer += draft_token
                        
                except (StopAsyncIteration, asyncio.TimeoutError):
                    pass

                # 2. Get a chunk from the main model and verify against the draft
                try:
                    main_chunk = await main_iterator.__anext__()
                    main_token = main_chunk.answer

                    if t_first_chunk is None:
                        t_first_chunk = time.monotonic()
                        first_chunk_metrics = {
                            "network_latency_ms": main_chunk.network_latency_ms,
                            "inference_ttft_ms": main_chunk.inference_ttft_ms
                        }
                        jlog({
                            "event": "time_to_first_token_ms", 
                            "ms": (t_first_chunk - t_start_turn) * 1000, 
                            "source": "main",
                            **first_chunk_metrics
                        })

                    if draft_buffer and main_token.startswith(draft_buffer):
                        yield LLMStreamChunk(text_chunk=draft_buffer)
                        full_response += draft_buffer
                        main_token = main_token[len(draft_buffer):]
                        draft_buffer = ""

                    elif draft_buffer:
                        jlog({"event": "speculative_correction", "draft": draft_buffer, "main": main_token})
                        draft_buffer = ""

                    yield LLMStreamChunk(text_chunk=main_token)
                    full_response += main_token

                except StopAsyncIteration:
                    main_stream_finished = True
                    if draft_buffer:
                        yield LLMStreamChunk(text_chunk=draft_buffer)
                        full_response += draft_buffer
                    break

        except Exception as e:
            jlog({"event": "speculative_generation_error", "error": str(e)})

        # Finalize
        assistant_message: ConversationMessage = {"role": "assistant", "content": full_response}
        self.dual_ctx.active_context.add_message(assistant_message)
        
        t_end_turn = time.monotonic()
        jlog({
            "event": "user_turn_finish",
            "total_ms": (t_end_turn - t_start_turn) * 1000,
            "context_ratio_after": self.dual_ctx.active_context.estimate_usage_ratio()
        })
        
        yield LLMStreamChunk(text_chunk="", is_final_chunk=True)


    async def _build_standby_context(self):
        history_to_summarize = self.dual_ctx.active_context.get_history_for_summary()
        if not history_to_summarize:
            return

        # Check cache for summary
        summary = await self._cache.get(self._session_id_hash)
        
        if not summary:
            summary_prompt = self.dual_ctx.active_context.build_summary_prompt(history_to_summarize)
            http_client = await self.connection_manager.get_client()
            
            summary_stream = self.llm_client.stream_structured_generate(
                http_client, summary_prompt, self._config['models']['summarization'], LLMStructuredResponse
            )
            
            summary_parts = [chunk.answer async for chunk in summary_stream]
            summary = "".join(summary_parts)
            await self._cache.set(self._session_id_hash, summary, ttl=3600)

        new_context = LLMContext(
            prompt_config=self._prompts,
            max_tokens=self._config['context_window_size'],
            model_name=self._config['models']['main']
        )
        new_context.add_message({"role": "system", "content": f"Previous conversation summary: {summary}"})
        self.dual_ctx.set_standby(new_context)


    async def shutdown(self):
        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        await self.connection_manager.shutdown()
        jlog({"event": "manager_shutdown"})

if __name__ == "__main__":
    class MockCache(AbstractCache):
        _data = {}
        async def get(self, key: str): return self._data.get(key)
        async def set(self, key: str, value: str, ttl: int): self._data[key] = value
        async def delete(self, key: str): self._data.pop(key, None)
        async def disconnect(self): pass

    async def main():
        with open("configs/config.yml", 'r') as f:
            config = yaml.safe_load(f)
        with open("configs/prompts.yml", 'r') as f:
            prompts = yaml.safe_load(f)
            
        cache = MockCache()
        manager = ConversationManager(config, prompts, cache, "test-session")
        
        text = "Tell me a short story."
        print(f"User: {text}")
        print("Assistant: ", end="")
        async for chunk in manager.process_user_turn(text):
            if not chunk.is_final_chunk:
                print(chunk.text_chunk, end="", flush=True)
        print()
        
        await manager.shutdown()

    asyncio.run(main())
