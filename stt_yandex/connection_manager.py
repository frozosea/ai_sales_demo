from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from domain.stt_models import STTConfig
from .stt_connection_pool import STTConnectionPool, WarmConnection

def jlog(level, event, **kwargs):
    logging.log(level, json.dumps({"event": event, **kwargs}))

@dataclass
class ConnectionManagerConfig:
    warmup_interval_sec: float = 1.5  # How often to warm up connections
    warmup_chunk_ms: int = 200        # Size of warmup audio chunk
    max_idle_time_sec: float = 8.0  # Max time to keep unused connections
    max_connections: int = 10         # Max number of connections in pool

class ConnectionManager:
    _instance: Optional[ConnectionManager] = None
    
    @classmethod
    def initialize(
        cls,
        config: STTConfig,
        iam_token: str,
        folder_id: str,
        manager_config: Optional[ConnectionManagerConfig] = None
    ) -> ConnectionManager:
        """Initialize the singleton connection manager."""
        if cls._instance is None:
            cls._instance = cls(config, iam_token, folder_id, manager_config or ConnectionManagerConfig())
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> ConnectionManager:
        """Get the singleton instance."""
        if cls._instance is None:
            raise RuntimeError("ConnectionManager not initialized. Call initialize() first.")
        return cls._instance
    
    def __init__(
        self,
        config: STTConfig,
        iam_token: str,
        folder_id: str,
        manager_config: ConnectionManagerConfig
    ):
        self.config = config
        self._iam_token = iam_token
        self._folder_id = folder_id
        self.manager_config = manager_config
        
        # Create connection pool
        self._pool = STTConnectionPool(
            config=config,
            iam_token=iam_token,
            folder_id=folder_id,
            max_connections=manager_config.max_connections,
            max_idle_time=manager_config.max_idle_time_sec
        )
        
        # Start warmup task
        self._warmup_task = asyncio.create_task(self._warmup_loop())
        self._is_running = True
    
    async def _warmup_loop(self):
        """Periodically warm up all connections in the pool."""
        while self._is_running:
            try:
                # Get all idle connections
                async with self._pool._lock:
                    idle_connections = [
                        (conn_id, conn) 
                        for conn_id, conn in self._pool._connections.items()
                        if not conn.in_use
                    ]
                
                # Warm up each idle connection
                for conn_id, conn in idle_connections:
                    try:
                        t_start = time.monotonic()
                        jlog(logging.DEBUG, "connection_warmup_start", connection_id=conn_id)
                        
                        # Mark as in use temporarily
                        conn.in_use = True
                        
                        # Warm up connection
                        await self._pool._warm_up_connection(conn_id, conn)
                        
                        # Mark as available again
                        conn.in_use = False
                        conn.last_used = time.monotonic()
                        
                        t_finish = time.monotonic()
                        jlog(
                            logging.DEBUG,
                            "connection_warmup_complete",
                            connection_id=conn_id,
                            duration_ms=round((t_finish - t_start) * 1000, 2)
                        )
                        
                    except Exception as e:
                        jlog(
                            logging.ERROR,
                            "connection_warmup_error",
                            connection_id=conn_id,
                            error=str(e)
                        )
                        # Remove failed connection
                        async with self._pool._lock:
                            if conn_id in self._pool._connections:
                                conn = self._pool._connections.pop(conn_id)
                                await conn.channel.close()
                
            except Exception as e:
                jlog(logging.ERROR, "warmup_loop_error", error=str(e))
            
            # Wait for next warmup interval
            await asyncio.sleep(self.manager_config.warmup_interval_sec)
    
    async def acquire_connection(self) -> tuple[str, WarmConnection]:
        """Get a warmed-up connection from the pool."""
        return await self._pool.acquire()
    
    async def release_connection(self, connection_id: str):
        """Release a connection back to the pool."""
        await self._pool.release(connection_id)
    
    async def close(self):
        """Close the connection manager and all connections."""
        self._is_running = False
        if self._warmup_task:
            self._warmup_task.cancel()
            try:
                await self._warmup_task
            except asyncio.CancelledError:
                pass
        
        await self._pool.close()