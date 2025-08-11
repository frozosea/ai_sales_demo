from __future__ import annotations
import asyncio
import httpx
import logging
import time
import os
import yaml
from typing import Optional, Dict
from dotenv import load_dotenv
import backoff

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.conn")

def jlog(data: dict):
    logger.info(data)

class RetryTransport(httpx.AsyncHTTPTransport):
    BACKOFF_MAX = 60  # Maximum backoff time in seconds
    BACKOFF_FACTOR = 2  # Exponential backoff multiplier

    def __init__(
        self,
        http2: bool = False,
        verify: bool = True,
        retries: int = 3,
        **kwargs
    ):
        self.retries = retries
        super().__init__(http2=http2, verify=verify, **kwargs)

    @backoff.on_exception(
        backoff.expo,
        (httpx.TimeoutException, httpx.NetworkError),
        max_time=BACKOFF_MAX,
        factor=BACKOFF_FACTOR
    )
    async def handle_async_request(self, request):
        return await super().handle_async_request(request)

class LLMConnectionManagerImpl:
    def __init__(self, api_key: str, timeout: int, keep_alive_interval: int, endpoint: str = "https://api.openai.com/v1"):
        if not api_key or not api_key.startswith("sk-"):
            raise ValueError("Invalid API key format")
        
        self._api_key = api_key.strip()  # Ensure no whitespace
        self._timeout = timeout
        self._keep_alive_interval = keep_alive_interval
        self._endpoint = endpoint
        self._client: Optional[httpx.AsyncClient] = None
        self._keep_alive_task: Optional[asyncio.Task] = None
        self._warmup_lock = asyncio.Lock()
        self._last_used: Dict[str, float] = {}  # Track last usage per endpoint
        self._is_warmed_up = False

        # Pre-bind models to endpoints for easier management
        self._model_endpoints = {
            'main': f'{endpoint}/chat/completions',
            'draft': f'{endpoint}/chat/completions', # Assuming same endpoint for draft model
            'summarization': f'{endpoint}/chat/completions'
        }

        # Log initialization (safely)
        masked_key = f"{self._api_key[:8]}...{self._api_key[-4:]}" if len(self._api_key) > 12 else "***"
        jlog({
            "event": "connection_manager_init",
            "api_key_length": len(self._api_key),
            "api_key_prefix": self._api_key[:8],
            "api_key_suffix": self._api_key[-4:],
            "timeout": timeout,
            "keep_alive": keep_alive_interval
        })

    async def _create_client(self) -> httpx.AsyncClient:
        """Create a new client with optimized settings."""
        # Debug log for API key (mask it for security)
        masked_key = f"{self._api_key[:8]}...{self._api_key[-4:]}" if len(self._api_key) > 12 else "***"
        jlog({
            "event": "client_create",
            "api_key_length": len(self._api_key),
            "api_key_prefix": self._api_key[:8],
            "api_key_suffix": self._api_key[-4:]
        })

        limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=20,
            keepalive_expiry=self._keep_alive_interval
        )
        
        timeouts = httpx.Timeout(
            connect=5.0,  # Shorter connect timeout
            read=self._timeout,
            write=self._timeout,
            pool=self._timeout
        )

        transport = RetryTransport(
            http2=True,
            verify=True,
            retries=3,
            local_address="0.0.0.0"  # Explicitly set local address
        )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "Keep-Alive": f"timeout={self._keep_alive_interval}",
            "OpenAI-Beta": "assistants=v1"  # Add OpenAI beta header
        }

        # Debug log for headers (mask sensitive data)
        debug_headers = headers.copy()
        debug_headers["Authorization"] = f"Bearer {masked_key}"
        jlog({"event": "client_headers", "headers": debug_headers})

        client = httpx.AsyncClient(
            headers=headers,
            timeout=timeouts,
            limits=limits,
            transport=transport,
            http2=True,
            verify=True
        )

        # Test connection with a simple request
        try:
            response = await client.get("https://api.openai.com/v1/models")
            response_json = response.json()
            jlog({
                "event": "client_test",
                "status": response.status_code,
                "error": response_json.get("error", {}).get("message") if response.status_code != 200 else None,
                "headers": dict(response.headers)
            })
            if response.status_code == 403:
                raise ValueError(f"API key authentication failed: {response_json.get('error', {}).get('message')}")
        except Exception as e:
            jlog({
                "event": "client_test_error",
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

        return client

    async def _pre_warm_connection(self) -> None:
        """Pre-warm the connection with parallel requests."""
        if self._is_warmed_up:
            jlog({"event": "warmup_skip", "reason": "already_warmed"})
            return

        async with self._warmup_lock:
            if self._is_warmed_up:  # Double check
                jlog({"event": "warmup_skip", "reason": "already_warmed_locked"})
                return

            t_start = time.monotonic()
            jlog({"event": "conn_warmup_start", "client_status": "initializing"})

            # Parallel warmup requests
            async def warmup_endpoint(url: str) -> None:
                try:
                    jlog({"event": "warmup_request_start", "url": url})
                    async with self._client.stream('GET', url) as response:
                        await response.aread()
                        self._last_used[url] = time.monotonic()
                        jlog({"event": "warmup_request_success", "url": url})
                except Exception as e:
                    jlog({
                        "event": "warmup_error",
                        "url": url,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })

            warmup_tasks = [
                asyncio.create_task(warmup_endpoint(url)) for url in self._model_endpoints.values()
            ]
            
            try:
                await asyncio.gather(*warmup_tasks)
                t_end = time.monotonic()
                self._is_warmed_up = True
                jlog({
                    "event": "conn_warmup_finish",
                    "duration_ms": (t_end - t_start) * 1000,
                    "client_status": "ready"
                })
            except Exception as e:
                jlog({
                    "event": "conn_warmup_failed",
                    "error": str(e),
                    "error_type": type(e).__name__
                })

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create a warmed-up client."""
        if self._client is None or self._client.is_closed:
            t_start = time.monotonic()
            jlog({"event": "conn_handshake_start"})
            
            self._client = await self._create_client()
            await self._pre_warm_connection()
            
            t_end = time.monotonic()
            jlog({"event": "conn_handshake_finish", "duration_ms": (t_end - t_start) * 1000})

            if self._keep_alive_interval > 0:
                self._keep_alive_task = asyncio.create_task(self._keep_alive_ping())

        return self._client

    async def _keep_alive_ping(self) -> None:
        """Maintain connection freshness with intelligent keep-alive."""
        while True:
            await asyncio.sleep(self._keep_alive_interval)
            if self._client and not self._client.is_closed:
                current_time = time.monotonic()
                
                # Check each endpoint
                for url, last_used in self._last_used.items():
                    # Only ping if endpoint hasn't been used recently
                    if current_time - last_used > self._keep_alive_interval:
                        try:
                            t_start = time.monotonic()
                            jlog({"event": "keep_alive_ping_start", "url": url})
                            
                            async with self._client.stream('GET', url) as response:
                                await response.aread()
                            
                            t_end = time.monotonic()
                            self._last_used[url] = t_end
                            jlog({
                                "event": "keep_alive_ping_finish",
                                "url": url,
                                "duration_ms": (t_end - t_start) * 1000
                            })
                        except Exception as e:
                            jlog({
                                "event": "keep_alive_ping_failed",
                                "url": url,
                                "error": str(e)
                            })
                            # If ping fails, mark connection for refresh
                            self._is_warmed_up = False

    async def shutdown(self) -> None:
        """Clean shutdown of all connections."""
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            try:
                await self._keep_alive_task
            except asyncio.CancelledError:
                pass
        
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            
        self._is_warmed_up = False
        jlog({"event": "connection_shutdown"})

if __name__ == "__main__":
    async def main():
        load_dotenv()
        
        with open("configs/config.yml", 'r') as f:
            config = yaml.safe_load(f)

        api_key = os.getenv("OPENAI_API_KEY") or config['llm']['api_key']
        timeout = config['llm']['http_timeout_sec']
        keep_alive = config['llm']['keep_alive_interval_sec']
        
        manager = LLMConnectionManagerImpl(api_key, timeout, keep_alive)
        
        # Test connection and warmup
        client = await manager.get_client()
        print(f"Client warmed up: {client}")
        
        # Test keep-alive
        await asyncio.sleep(2)
        
        # Shutdown
        await manager.shutdown()

    asyncio.run(main()) 