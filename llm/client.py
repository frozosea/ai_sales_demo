from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Type, Optional
import httpx
from pydantic import BaseModel, ValidationError

from domain.interfaces.llm import AbstractLLMClient
from domain.models import LLMStructuredResponse # Using a concrete model for parsing

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.client")

def jlog(data: dict):
    logger.info(json.dumps(data))

class OpenAILLMClient(AbstractLLMClient):
    async def stream_structured_generate(
        self,
        http_client: httpx.AsyncClient,
        full_prompt: str,
        model: str,
        response_model: Type[BaseModel]
    ) -> AsyncGenerator[BaseModel, None]:
        
        request_body = {
            "model": model,
            "messages": [{"role": "system", "content": full_prompt}],
            "stream": True,
        }
        
        t_start_request = time.monotonic()
        jlog({"event": "request_send", "model": model, "ts": time.time()})
        
        try:
            async with http_client.stream("POST", "https://api.openai.com/v1/chat/completions", json=request_body) as response:
                response.raise_for_status()
                
                t_first_token = None
                seq_counter = 0
                buffer = ""
                
                async for chunk in response.aiter_bytes():
                    if t_first_token is None:
                        t_first_token = time.monotonic()
                        jlog({"event": "first_token", "ms": (t_first_token - t_start_request) * 1000})

                    buffer += chunk.decode('utf-8')
                    
                    # Process server-sent events
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
                                    jlog({"event": "chunk", "size": len(content), "seq": seq_counter})
                                    seq_counter += 1
                                    # This is a simplified parser. A real implementation
                                    # would need to handle partial JSON objects.
                                    # For this example, we yield a partial response.
                                    yield response_model(answer=content)

                            except (json.JSONDecodeError, ValidationError) as e:
                                jlog({"event": "parsing_error", "error": str(e), "data": data_str})

        except httpx.HTTPStatusError as e:
            jlog({"event": "http_error", "status_code": e.response.status_code, "error": str(e)})
        except Exception as e:
            jlog({"event": "stream_error", "error": str(e)})
        finally:
            t_end_stream = time.monotonic()
            jlog({"event": "stream_end", "total_ms": (t_end_stream - t_start_request) * 1000, "chunks": seq_counter})


if __name__ == "__main__":
    async def mock_stream_test():
        class MockAsyncClient:
            async def stream(self, method, url, json):
                class MockResponse:
                    async def aiter_bytes(self):
                        chunks = [
                            'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
                            'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
                            'data: {"choices": [{"delta": {"content": "!"}}]}\n\n',
                            'data: [DONE]\n\n'
                        ]
                        for chunk in chunks:
                            yield chunk.encode('utf-8')
                            await asyncio.sleep(0.1)
                    
                    def raise_for_status(self):
                        pass

                return MockResponse()

        client = OpenAILLMClient()
        async for response_part in client.stream_structured_generate(
            http_client=MockAsyncClient(),
            full_prompt="test prompt",
            model="test-model",
            response_model=LLMStructuredResponse
        ):
            print(f"Received: {response_part.answer}")

    asyncio.run(mock_stream_test())
