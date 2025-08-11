from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Type, Optional, List
import httpx
from pydantic import BaseModel, ValidationError

from domain.interfaces.llm import AbstractLLMClient
from domain.models import LLMStructuredResponse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.client")

def jlog(data: dict):
    logger.info(json.dumps(data))

class SmartChunkBuffer:
    """Groups tokens into words and short phrases for smoother streaming."""
    def __init__(self, separators: List[str] = [' ', '\n', ',', '.', '!', '?'], min_chunk_size: int = 5):
        self.buffer = ""
        self.separators = set(separators)
        self.min_chunk_size = min_chunk_size

    def add(self, content: str) -> Optional[str]:
        """Adds content and returns a completed chunk if a separator is found and size is sufficient."""
        self.buffer += content
        
        # If buffer is large enough, look for a separator
        if len(self.buffer) >= self.min_chunk_size:
            last_sep_index = -1
            for sep in self.separators:
                idx = self.buffer.rfind(sep)
                if idx > last_sep_index:
                    last_sep_index = idx

            if last_sep_index != -1:
                chunk_to_yield = self.buffer[:last_sep_index + 1]
                self.buffer = self.buffer[last_sep_index + 1:]
                return chunk_to_yield
        return None

    def flush(self) -> str:
        """Returns any remaining content in the buffer."""
        result = self.buffer
        self.buffer = ""
        return result

class OpenAILLMClient(AbstractLLMClient):
    def __init__(self, endpoint: str = "https://api.openai.com/v1"):
        self._endpoint = endpoint
        self._chunk_buffer = SmartChunkBuffer()
        self._parallel_warmup_task: Optional[asyncio.Task] = None

    async def _prepare_next_request(self, http_client: httpx.AsyncClient, model: str):
        """Параллельный прогрев для следующего запроса."""
        try:
            async with http_client.stream(
                "POST",
                f"{self._endpoint}/chat/completions",
                json={"model": model, "messages": [{"role": "system", "content": "warmup"}], "stream": True}
            ) as response:
                async for _ in response.aiter_bytes():
                    break  # Читаем только первый чанк
        except Exception as e:
            jlog({"event": "parallel_warmup_error", "error": str(e)})

    async def stream_structured_generate(
        self,
        http_client: httpx.AsyncClient,
        full_prompt: str,
        model: str,
        response_model: Type[BaseModel],
        low_latency_mode: bool = False
    ) -> AsyncGenerator[BaseModel, None]:
        
        # Оптимизированное тело запроса
        request_body = {
            "model": model,
            "messages": [{"role": "system", "content": full_prompt}],
            "stream": True,
            "temperature": 0.7,
            "presence_penalty": 0,
            "frequency_penalty": 0,
            # Запрашиваем больший первый чанк
            "max_tokens": 150,
            "top_p": 1
        }
        
        # Use more aggressive timeouts in low latency mode
        request_timeout = 10.0 if low_latency_mode else 30.0
        
        t_start_request = time.monotonic()
        jlog({"event": "request_send", "model": model, "low_latency_mode": low_latency_mode, "ts": time.time()})
        
        seq_counter = 0  # Initialize counter here
        network_latency_ms = None
        inference_ttft_ms = None
        try:
            async with http_client.stream(
                "POST",
                f"{self._endpoint}/chat/completions",
                json=request_body,
                timeout=request_timeout
            ) as response:
                response.raise_for_status()
                
                t_first_byte = None
                t_first_content = None
                buffer = ""
                
                # Запускаем параллельный прогрев для следующего запроса
                self._parallel_warmup_task = asyncio.create_task(
                    self._prepare_next_request(http_client, model)
                )
                
                async for chunk in response.aiter_bytes():
                    if t_first_byte is None:
                        t_first_byte = time.monotonic()
                        network_latency_ms = (t_first_byte - t_start_request) * 1000
                        jlog({"event": "first_byte_received", "network_latency_ms": network_latency_ms})

                    buffer += chunk.decode('utf-8')
                    
                    # Обработка server-sent events
                    while 'data:' in buffer and '\n\n' in buffer:
                        line_end_pos = buffer.find('\n\n')
                        line = buffer[:line_end_pos]
                        buffer = buffer[line_end_pos + 2:]

                        if line.startswith("data:"):
                            data_str = line[len("data:"):].strip()
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    if t_first_content is None:
                                        t_first_content = time.monotonic()
                                        inference_ttft_ms = (t_first_content - t_first_byte) * 1000
                                        jlog({"event": "first_content_parsed", "inference_ttft_ms": inference_ttft_ms})

                                    # Send the very first content chunk immediately
                                    if seq_counter == 0:
                                        jlog({"event": "chunk", "size": len(content), "seq": seq_counter})
                                        seq_counter += 1
                                        yield response_model(
                                            answer=content,
                                            network_latency_ms=network_latency_ms,
                                            inference_ttft_ms=inference_ttft_ms
                                        )
                                    else:
                                        # Buffer subsequent chunks into meaningful parts
                                        buffered_chunk = self._chunk_buffer.add(content)
                                        if buffered_chunk:
                                            jlog({"event": "chunk", "size": len(buffered_chunk), "seq": seq_counter})
                                            seq_counter += 1
                                            yield response_model(answer=buffered_chunk)

                            except (json.JSONDecodeError, ValidationError) as e:
                                jlog({"event": "parsing_error", "error": str(e), "data": data_str})
                
                # Flush any remaining content in the buffer
                remaining_content = self._chunk_buffer.flush()
                if remaining_content:
                    jlog({"event": "chunk", "size": len(remaining_content), "seq": seq_counter})
                    seq_counter += 1
                    yield response_model(answer=remaining_content)

        except httpx.HTTPStatusError as e:
            jlog({"event": "http_error", "status_code": e.response.status_code, "error": str(e)})
        except Exception as e:
            jlog({"event": "stream_error", "error": str(e)})
        finally:
            t_end_stream = time.monotonic()
            jlog({"event": "stream_end", "total_ms": (t_end_stream - t_start_request) * 1000, "chunks": seq_counter})
            
            # Отменяем параллельный прогрев, если он еще выполняется
            if self._parallel_warmup_task:
                self._parallel_warmup_task.cancel()
                try:
                    await self._parallel_warmup_task
                except asyncio.CancelledError:
                    pass
                self._parallel_warmup_task = None


if __name__ == "__main__":
    async def mock_stream_test():
        class MockAsyncClient:
            async def stream(self, method, url, json):
                class MockResponse:
                    async def aiter_bytes(self):
                        chunks = [
                            'data: {"choices": [{"delta": {"content": "This is "}}]}\n\n',
                            'data: {"choices": [{"delta": {"content": "a test of "}}]}\n\n',
                            'data: {"choices": [{"delta": {"content": "the smart "}}]}\n\n',
                            'data: {"choices": [{"delta": {"content": "chunking."}}]}\n\n',
                            'data: [DONE]\n\n'
                        ]
                        for chunk in chunks:
                            yield chunk.encode('utf-8')
                            await asyncio.sleep(0.1)
                    
                    def raise_for_status(self):
                        pass

                return MockResponse()

        client = OpenAILLMClient()
        print("\nTesting optimized chunking:")
        async for response_part in client.stream_structured_generate(
            http_client=MockAsyncClient(),
            full_prompt="test prompt",
            model="test-model",
            response_model=LLMStructuredResponse
        ):
            print(f"Received chunk: {response_part.answer}")

    asyncio.run(mock_stream_test())
