from __future__ import annotations
import asyncio
import httpx
import logging
import time
import os
import yaml
from typing import Optional
from dotenv import load_dotenv

from domain.interfaces.llm import LLMConnectionManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.conn")

def jlog(data: dict):
    logger.info(data)

class LLMConnectionManagerImpl(LLMConnectionManager):
    def __init__(self, api_key: str, timeout: int, keep_alive_interval: int):
        self._api_key = api_key
        self._timeout = timeout
        self._keep_alive_interval = keep_alive_interval
        self._client: Optional[httpx.AsyncClient] = None
        self._keep_alive_task: Optional[asyncio.Task] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            t_start = time.monotonic()
            jlog({"event": "conn_handshake_start"})
            
            headers = {"Authorization": f"Bearer {self._api_key}"}
            self._client = httpx.AsyncClient(headers=headers, timeout=self._timeout, http2=True)
            
            # Perform a warmup request
            try:
                await self._client.get("https://api.openai.com/v1/models")
            except httpx.RequestError as e:
                jlog({"event": "conn_warmup_failed", "error": str(e)})
                # Decide if we should raise or just warn
            
            t_end = time.monotonic()
            jlog({"event": "conn_handshake_finish", "duration_ms": (t_end - t_start) * 1000})

            if self._keep_alive_interval > 0:
                self._keep_alive_task = asyncio.create_task(self._keep_alive_ping())
        return self._client

    async def _keep_alive_ping(self):
        while True:
            await asyncio.sleep(self._keep_alive_interval)
            if self._client and not self._client.is_closed:
                try:
                    t_start = time.monotonic()
                    jlog({"event": "keep_alive_ping_start"})
                    await self._client.get("https://api.openai.com/v1/models") # Light request
                    t_end = time.monotonic()
                    jlog({"event": "keep_alive_ping_finish", "duration_ms": (t_end - t_start) * 1000})
                except httpx.RequestError as e:
                    jlog({"event": "keep_alive_ping_failed", "error": str(e)})

    async def shutdown(self):
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            try:
                await self._keep_alive_task
            except asyncio.CancelledError:
                pass
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        jlog({"event": "connection_shutdown"})

if __name__ == "__main__":
    async def main():
        load_dotenv()
        
        # Load configs
        # Assuming script is run from project root
        with open("configs/config.yml", 'r') as f:
            config = yaml.safe_load(f)

        api_key = os.getenv("OPENAI_API_KEY") or config['llm']['api_key']
        timeout = config['llm']['http_timeout_sec']
        keep_alive = config['llm']['keep_alive_interval_sec']
        
        manager = LLMConnectionManagerImpl(api_key, timeout, keep_alive)
        
        # Get client (triggers handshake and warmup)
        client = await manager.get_client()
        print(f"Client received: {client}")

        # Shutdown
        await manager.shutdown()

    asyncio.run(main()) 