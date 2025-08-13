import asyncio
import json
import logging
import time
import urllib.parse
import ssl
from typing import Optional, Dict, Set
from dataclasses import dataclass
from enum import Enum

import httpx
import websockets
from websockets.legacy.client import WebSocketClientProtocol
from websockets_proxy import Proxy, proxy_connect

from .config import TTSConfig

log = logging.getLogger("tts_pool")


class TTSConnectionError(RuntimeError):
    """Ошибка соединения с TTS сервисом"""
    pass


class TTSProtocolError(RuntimeError):
    """Ошибка протокола TTS"""
    pass


class ConnectionType(Enum):
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class PooledConnection:
    """Представляет соединение в пуле"""
    connection_type: ConnectionType
    connection_id: str
    created_at: float
    last_used: float
    connection: any  # httpx.AsyncClient или WebSocketClientProtocol
    task: Optional[asyncio.Task] = None


def _jlog(event: str, **fields):
    """Логирование в JSON формате"""
    log.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


class TTSConnectionPool:
    """Пул соединений для TTS с поддержкой HTTP и WebSocket"""
    
    def __init__(
        self, 
        cfg: TTSConfig, 
        max_connections: int = 10,
        max_idle_time: float = 300.0,  # 5 minutes
        cleanup_interval: float = 60.0,  # 1 minute
        keep_alive_interval: Optional[float] = None,  # None = use config default
        connection_timeout: Optional[float] = None,   # None = use config default
        enable_retry: bool = True,
        retry_attempts: int = 3,
        retry_backoff_factor: float = 2.0,
        enable_connection_pooling: bool = True,
        enable_keep_alive: bool = True,
        enable_warming: bool = True,
        warming_threshold: float = 30.0,  # seconds without usage for warming
        proxy_url: Optional[str] = "http://127.0.0.1:7890",  # None = no proxy
    ):
        self.config = cfg
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.cleanup_interval = cleanup_interval
        self.keep_alive_interval = keep_alive_interval or cfg.ws_keep_alive_sec
        self.connection_timeout = connection_timeout or cfg.ws_connect_timeout_sec
        self.enable_retry = enable_retry
        self.retry_attempts = retry_attempts
        self.retry_backoff_factor = retry_backoff_factor
        self.enable_connection_pooling = enable_connection_pooling
        self.enable_keep_alive = enable_keep_alive
        self.enable_warming = enable_warming
        self.warming_threshold = warming_threshold
        self.proxy_url = proxy_url
        
        self.connections: Dict[str, PooledConnection] = {}
        self.active_connection_ids: Set[str] = set()
        self.cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Log configuration
        _jlog("pool_config", 
              max_connections=max_connections,
              max_idle_time=max_idle_time,
              cleanup_interval=cleanup_interval,
              keep_alive_interval=self.keep_alive_interval,
              connection_timeout=self.connection_timeout,
              enable_retry=enable_retry,
              enable_connection_pooling=enable_connection_pooling,
              enable_keep_alive=enable_keep_alive,
              enable_warming=enable_warming,
              warming_threshold=warming_threshold,
              proxy_url=proxy_url)
        
    async def start(self):
        """Запускает пул соединений"""
        if self.enable_connection_pooling:
            self.cleanup_task = asyncio.create_task(self._cleanup_task())
            
            # Pre-warming соединений для минимальной задержки
            if self.enable_warming:
                asyncio.create_task(self._pre_warm_connections())
            
            _jlog("pool_started", max_connections=self.max_connections)
        else:
            _jlog("pool_started_disabled", note="Connection pooling disabled")
    
    async def _pre_warm_connections(self):
        """Предварительно разогревает соединения"""
        try:
            # Создаем несколько HTTP соединений заранее
            for i in range(min(3, self.max_connections)):
                conn_id = f"warm_http_{i}"
                client = await self._create_http_connection()
                
                pooled_conn = PooledConnection(
                    connection_type=ConnectionType.HTTP,
                    connection_id=conn_id,
                    created_at=time.perf_counter(),
                    last_used=time.perf_counter(),
                    connection=client
                )
                
                self.connections[conn_id] = pooled_conn
                _jlog("connection_pre_warmed", conn_id=conn_id, type="http")
            
            # Создаем WebSocket соединение заранее
            if self.max_connections > 3:
                conn_id = "warm_ws_1"
                websocket = await self._create_websocket_connection()
                
                pooled_conn = PooledConnection(
                    connection_type=ConnectionType.WEBSOCKET,
                    connection_id=conn_id,
                    created_at=time.perf_counter(),
                    last_used=time.perf_counter(),
                    connection=websocket
                )
                
                self.connections[conn_id] = pooled_conn
                _jlog("connection_pre_warmed", conn_id=conn_id, type="websocket")
                
        except Exception as e:
            _jlog("pre_warm_error", error=str(e))
    
    async def _create_http_connection(self) -> httpx.AsyncClient:
        """Создает оптимизированное HTTP соединение"""
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        timeout = httpx.Timeout(
            connect=2.0, read=5.0, write=2.0, pool=10.0
        )
        
        client_kwargs = {
            "timeout": timeout,
            "limits": limits,
            "headers": {
                "xi-api-key": self.config.api_key,
                "Connection": "keep-alive",
                "Keep-Alive": "timeout=30, max=1000"
            }
        }
        
        if self.proxy_url:
            client_kwargs["proxy"] = self.proxy_url
            client_kwargs["http2"] = True
            
        return httpx.AsyncClient(**client_kwargs)
    
    async def close(self):
        """Останавливает пул соединений"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Закрываем все соединения
        async with self._lock:
            for conn_id, pooled_conn in self.connections.items():
                await self._close_connection(pooled_conn)
            self.connections.clear()
            self.active_connection_ids.clear()
        
        _jlog("pool_stopped")
    
    async def get_http_connection(self, call_id: str) -> httpx.AsyncClient:
        """Получает HTTP соединение для звонка"""
        if not self.enable_connection_pooling:
            # Создаем новое соединение без пула с оптимизированными настройками
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            timeout = httpx.Timeout(
                connect=2.0,  # Быстрое соединение
                read=5.0,     # Быстрое чтение
                write=2.0,    # Быстрая запись
                pool=10.0     # Пул соединений
            )
            
            client_kwargs = {
                "timeout": timeout,
                "limits": limits,
                "headers": {
                    "xi-api-key": self.config.api_key,
                    "Connection": "keep-alive",
                    "Keep-Alive": "timeout=30, max=1000"
                }
            }
            if self.proxy_url:
                client_kwargs["proxy"] = self.proxy_url
                client_kwargs["http2"] = True
                
            client = httpx.AsyncClient(**client_kwargs)
            _jlog("http_connection_direct", call_id=call_id, proxy=self.proxy_url)
            return client
        
        conn_id = f"http_{call_id}"
        
        async with self._lock:
            if conn_id in self.connections:
                # Возвращаем существующее соединение
                pooled_conn = self.connections[conn_id]
                pooled_conn.last_used = time.perf_counter()
                self.active_connection_ids.add(conn_id)
                _jlog("http_connection_reused", conn_id=conn_id)
                return pooled_conn.connection
            
            # Создаем новое соединение
            if len(self.connections) >= self.max_connections:
                await self._evict_oldest_connection()
            
            # Оптимизированные настройки для минимальной задержки
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            timeout = httpx.Timeout(
                connect=2.0,  # Быстрое соединение
                read=5.0,     # Быстрое чтение
                write=2.0,    # Быстрая запись
                pool=10.0     # Пул соединений
            )
            
            client_kwargs = {
                "timeout": timeout,
                "limits": limits,
                "headers": {
                    "xi-api-key": self.config.api_key,
                    "Connection": "keep-alive",
                    "Keep-Alive": "timeout=30, max=1000"
                }
            }
            
            if self.proxy_url:
                client_kwargs["proxy"] = self.proxy_url
                client_kwargs["http2"] = True
                
            client = httpx.AsyncClient(**client_kwargs)
            
            pooled_conn = PooledConnection(
                connection_type=ConnectionType.HTTP,
                connection_id=conn_id,
                created_at=time.perf_counter(),
                last_used=time.perf_counter(),
                connection=client
            )
            
            self.connections[conn_id] = pooled_conn
            self.active_connection_ids.add(conn_id)
            
            _jlog("http_connection_created", conn_id=conn_id)
            return client
    
    async def get_websocket_connection(self, call_id: str) -> WebSocketClientProtocol:
        """Получает WebSocket соединение для звонка"""
        if not self.enable_connection_pooling:
            # Создаем новое соединение без пула
            websocket = await self._create_websocket_connection()
            if self.enable_keep_alive:
                asyncio.create_task(self._websocket_keep_alive(f"direct_{call_id}", websocket))
            _jlog("ws_connection_direct", call_id=call_id)
            return websocket
        
        conn_id = f"ws_{call_id}"
        
        async with self._lock:
            if conn_id in self.connections:
                # Возвращаем существующее соединение
                pooled_conn = self.connections[conn_id]
                pooled_conn.last_used = time.perf_counter()
                self.active_connection_ids.add(conn_id)
                _jlog("ws_connection_reused", conn_id=conn_id)
                return pooled_conn.connection
            
            # Создаем новое соединение
            if len(self.connections) >= self.max_connections:
                await self._evict_oldest_connection()
            
            # Устанавливаем WebSocket соединение
            websocket = await self._create_websocket_connection()
            
            # Запускаем keep-alive для этого соединения
            keep_alive_task = None
            if self.enable_keep_alive:
                keep_alive_task = asyncio.create_task(
                    self._websocket_keep_alive(conn_id, websocket)
                )
            
            pooled_conn = PooledConnection(
                connection_type=ConnectionType.WEBSOCKET,
                connection_id=conn_id,
                created_at=time.perf_counter(),
                last_used=time.perf_counter(),
                connection=websocket,
                task=keep_alive_task
            )
            
            self.connections[conn_id] = pooled_conn
            self.active_connection_ids.add(conn_id)
            
            _jlog("ws_connection_created", conn_id=conn_id)
            return websocket
    
    async def release_connection(self, call_id: str, connection_type: ConnectionType):
        """Освобождает соединение для звонка"""
        if not self.enable_connection_pooling:
            _jlog("connection_released_direct", call_id=call_id, type=connection_type.value)
            return
            
        conn_id = f"{connection_type.value}_{call_id}"
        
        async with self._lock:
            if conn_id in self.active_connection_ids:
                self.active_connection_ids.remove(conn_id)
                _jlog("connection_released", conn_id=conn_id)
    
    async def _create_websocket_connection(self) -> WebSocketClientProtocol:
        """Создает новое WebSocket соединение"""
        url = self._build_websocket_url()
        headers = {"xi-api-key": self.config.api_key}
        
        _jlog("ws_connection_attempt", url=url, api_key_length=len(self.config.api_key), proxy=self.proxy_url or "none")
        
        # Создаем SSL контекст с отключенной верификацией
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Retry logic
        last_exception = None
        for attempt in range(self.retry_attempts if self.enable_retry else 1):
            try:
                if self.proxy_url:
                    # Используем websockets_proxy для прокси соединений
                    proxy = Proxy.from_url(self.proxy_url)
                    websocket = await asyncio.wait_for(
                        proxy_connect(url, proxy=proxy, extra_headers=headers, ssl=ssl_context),
                        timeout=self.connection_timeout
                    )
                else:
                    # Обычное соединение без прокси
                    websocket = await asyncio.wait_for(
                        websockets.connect(url, additional_headers=headers, ssl=ssl_context),
                        timeout=self.connection_timeout
                    )
                
                # Отправляем инициализацию
                await self._send_websocket_initialize(websocket)
                
                _jlog("ws_connection_established", attempt=attempt + 1)
                return websocket
                
            except Exception as e:
                last_exception = e
                if self.enable_retry and attempt < self.retry_attempts - 1:
                    wait_time = self.retry_backoff_factor ** attempt
                    _jlog("ws_connection_retry", attempt=attempt + 1, wait_time=wait_time, error=str(e))
                    await asyncio.sleep(wait_time)
                else:
                    break
        
        _jlog("ws_connection_failed", attempts=self.retry_attempts, error=str(last_exception))
        raise TTSConnectionError(f"Failed to establish WebSocket connection after {self.retry_attempts} attempts: {last_exception}")
    
    def _build_websocket_url(self) -> str:
        """Строит URL для WebSocket соединения"""
        base_url = f"{self.config.ws_base_url}/v1/text-to-speech/{self.config.voice_id}/stream-input"
        
        # Упрощаем параметры, оставляем только основные
        params = {
            "model_id": self.config.model_id,
            "output_format": self.config.ws_output_format,
        }
        
        # Добавляем chunk_length_schedule для минимальной задержки
        if hasattr(self.config, 'ws_chunk_length_schedule') and self.config.ws_chunk_length_schedule:
            params["chunk_length_schedule"] = self.config.ws_chunk_length_schedule
        
        # Добавляем language_code только если он не ru (может вызывать проблемы)
        if self.config.language_code and self.config.language_code != "ru":
            params["language_code"] = self.config.language_code
            
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"
    
    async def _send_websocket_initialize(self, websocket: WebSocketClientProtocol):
        """Отправляет инициализацию WebSocket соединения"""
        init_message = {
            "text": " ",
            "voice_settings": {
                "stability": self.config.voice_stability,
                "similarity_boost": self.config.voice_similarity_boost,
                "style": 0,
                "use_speaker_boost": False,
                "speed": self.config.voice_speed
            }
        }
        
        await websocket.send(json.dumps(init_message))
        _jlog("ws_initialization_sent", voice_settings=init_message["voice_settings"])
    
    async def _websocket_keep_alive(self, conn_id: str, websocket: WebSocketClientProtocol):
        """Keep-alive для WebSocket соединения"""
        if not self.enable_keep_alive:
            return
            
        while True:
            try:
                await asyncio.sleep(self.keep_alive_interval)
                
                if websocket and not websocket.closed:
                    ping_message = {"text": " "}
                    await websocket.send(json.dumps(ping_message))
                    _jlog("ws_keepalive_ping", conn_id=conn_id)
                else:
                    break
                    
            except Exception as e:
                _jlog("ws_keepalive_error", conn_id=conn_id, error=str(e))
                break
    
    async def _evict_oldest_connection(self):
        """Удаляет самое старое неактивное соединение"""
        oldest_conn = None
        oldest_time = float('inf')
        
        for conn_id, pooled_conn in self.connections.items():
            if conn_id not in self.active_connection_ids:
                if pooled_conn.last_used < oldest_time:
                    oldest_time = pooled_conn.last_used
                    oldest_conn = (conn_id, pooled_conn)
        
        if oldest_conn:
            conn_id, pooled_conn = oldest_conn
            await self._close_connection(pooled_conn)
            del self.connections[conn_id]
            _jlog("connection_evicted", conn_id=conn_id)
    
    async def _close_connection(self, pooled_conn: PooledConnection):
        """Закрывает соединение"""
        try:
            if pooled_conn.task:
                pooled_conn.task.cancel()
                try:
                    await pooled_conn.task
                except asyncio.CancelledError:
                    pass
            
            if pooled_conn.connection_type == ConnectionType.WEBSOCKET:
                if not pooled_conn.connection.closed:
                    close_message = {"text": ""}
                    await pooled_conn.connection.send(json.dumps(close_message))
                    await pooled_conn.connection.close()
            else:  # HTTP
                await pooled_conn.connection.aclose()
                
            _jlog("connection_closed", conn_id=pooled_conn.connection_id)
            
        except Exception as e:
            _jlog("connection_close_error", conn_id=pooled_conn.connection_id, error=str(e))
    
    async def _cleanup_task(self):
        """Фоновая задача очистки неактивных соединений"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                current_time = time.perf_counter()
                to_remove = []
                
                async with self._lock:
                    for conn_id, pooled_conn in self.connections.items():
                        # Удаляем соединения, неактивные более max_idle_time
                        if (current_time - pooled_conn.last_used) > self.max_idle_time:
                            to_remove.append(conn_id)
                    
                    for conn_id in to_remove:
                        await self._close_connection(self.connections[conn_id])
                        del self.connections[conn_id]
                        _jlog("connection_cleanup", conn_id=conn_id)
                        
            except Exception as e:
                _jlog("cleanup_error", error=str(e))


if __name__ == "__main__":
    import logging
    import sys
    from pathlib import Path
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    try:
        from .config import load_tts_config
        cfg = load_tts_config("configs/tts_config.yml")
        
        async def test_pool():
            # Тестируем с разными настройками
            pool = TTSConnectionPool(
                cfg, 
                max_connections=3,
                max_idle_time=120.0,  # 2 minutes
                cleanup_interval=30.0,  # 30 seconds
                enable_retry=True,
                retry_attempts=2,
                enable_connection_pooling=True,
                enable_keep_alive=True,
                enable_warming=True,
                warming_threshold=15.0,  # 15 seconds
                proxy_url="http://127.0.0.1:7890"  # Используем прокси
            )
            await pool.start()
            
            try:
                # Тестируем создание HTTP соединений
                print("🧪 Тестируем HTTP пул...")
                http_conn1 = await pool.get_http_connection("call_1")
                http_conn2 = await pool.get_http_connection("call_2")
                print(f"✅ HTTP соединения созданы: {len(pool.connections)}")
                
                # Тестируем создание WebSocket соединений
                print("🧪 Тестируем WebSocket пул...")
                ws_conn1 = await pool.get_websocket_connection("call_1")
                print(f"✅ WebSocket соединение создано: {len(pool.connections)}")
                
                # Тестируем повторное использование
                http_conn1_reused = await pool.get_http_connection("call_1")
                print("✅ HTTP соединение переиспользовано")
                
                # Освобождаем соединения
                await pool.release_connection("call_1", ConnectionType.HTTP)
                await pool.release_connection("call_2", ConnectionType.HTTP)
                await pool.release_connection("call_1", ConnectionType.WEBSOCKET)
                
                print("✅ Соединения освобождены")
                
            finally:
                await pool.close()
                print("✅ Пул остановлен")
        
        asyncio.run(test_pool())
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
