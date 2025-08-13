import asyncio
import base64
import json
import logging
import time
from typing import AsyncGenerator, Tuple

import httpx
from websockets.legacy.client import WebSocketClientProtocol

from .config import TTSConfig
from .connection_pool import TTSConnectionPool, ConnectionType, TTSConnectionError, TTSProtocolError

log = logging.getLogger("tts_manager")


def _jlog(event: str, **fields):
    """Логирование в JSON формате"""
    log.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


class TTSManager:
    """Менеджер TTS с гибридной логикой (HTTP + WebSocket)"""
    
    def __init__(self, cfg: TTSConfig, connection_pool: TTSConnectionPool, call_id: str):
        self.config = cfg
        self.connection_pool = connection_pool
        self.call_id = call_id
        
    async def stream_static_text(self, text: str) -> AsyncGenerator[bytes, None]:
        """HTTP streaming для статических фраз"""
        _jlog("http_request_start", text_length=len(text), call_id=self.call_id)
        request_start = time.perf_counter()
        
        # Получаем HTTP соединение из пула
        client = await self.connection_pool.get_http_connection(self.call_id)
        
        url = f"{self.config.http_base_url}/v1/text-to-speech/{self.config.voice_id}/stream"
        
        # Query параметры
        params = {
            "output_format": self.config.http_output_format,
            "optimize_streaming_latency": self.config.optimize_streaming_latency
        }
        
        # JSON body
        body = {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": self.config.voice_stability,
                "similarity_boost": self.config.voice_similarity_boost,
                "style": 0,
                "use_speaker_boost": False,
                "speed": self.config.voice_speed
            }
        }
        
        if self.config.language_code:
            body["language_code"] = self.config.language_code
        
        try:
            async with client.stream(
                "POST", url, params=params, json=body
            ) as response:
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        _jlog("http_error", status=response.status_code, text=error_text.decode())
                        raise TTSProtocolError(f"HTTP error {response.status_code}: {error_text.decode()}")
                    
                    first_byte_received = False
                    total_bytes = 0
                    chunks_count = 0
                    
                    async for chunk in response.aiter_bytes():
                        if not first_byte_received:
                            first_byte_ms = (time.perf_counter() - request_start) * 1000
                            _jlog("http_first_byte", ms=round(first_byte_ms, 2))
                            first_byte_received = True
                        
                        total_bytes += len(chunk)
                        chunks_count += 1
                        yield chunk
                    
                    total_ms = (time.perf_counter() - request_start) * 1000
                    _jlog("http_stream_end", 
                          total_ms=round(total_ms, 2), 
                          chunks=chunks_count, 
                          bytes=total_bytes,
                          call_id=self.call_id)
                    
        except httpx.TimeoutException:
            _jlog("http_timeout", timeout_sec=self.config.http_timeout_sec, call_id=self.call_id)
            raise TTSConnectionError(f"HTTP request timeout after {self.config.http_timeout_sec}s")
        except Exception as e:
            _jlog("http_error", error=str(e), call_id=self.call_id)
            raise TTSConnectionError(f"HTTP request failed: {e}")
        finally:
            # Освобождаем соединение
            await self.connection_pool.release_connection(self.call_id, ConnectionType.HTTP)
    
    async def start_llm_stream(self) -> Tuple[asyncio.Queue[str], asyncio.Queue[bytes]]:
        """WebSocket streaming для LLM ответов"""
        # Получаем активное соединение из пула
        websocket = await self.connection_pool.get_websocket_connection(self.call_id)
        
        # Создаем очереди
        text_input_queue = asyncio.Queue()
        audio_output_queue = asyncio.Queue()
        
        # Запускаем фоновые задачи
        send_task = asyncio.create_task(self._ws_send_task(websocket, text_input_queue))
        receive_task = asyncio.create_task(self._ws_receive_task(websocket, audio_output_queue))
        
        _jlog("ws_stream_started", call_id=self.call_id)
        
        return text_input_queue, audio_output_queue
    
    async def _ws_send_task(self, websocket: WebSocketClientProtocol, text_queue: asyncio.Queue[str]):
        """Фоновая задача для отправки текста через WebSocket"""
        first_chunk = True
        
        try:
            while True:
                text_data = await text_queue.get()
                
                if text_data is None:  # Сигнал завершения
                    break
                
                # Формируем сообщение согласно документации
                if first_chunk:
                    message = {
                        "text": text_data,
                        "try_trigger_generation": True
                    }
                    first_chunk = False
                else:
                    message = {
                        "text": text_data
                    }
                
                await websocket.send(json.dumps(message))
                _jlog("ws_send_text", text_length=len(text_data), first_chunk=first_chunk, call_id=self.call_id)
                
        except Exception as e:
            _jlog("ws_send_error", error=str(e), call_id=self.call_id)
            raise TTSProtocolError(f"WebSocket send error: {e}")
    
    async def _ws_receive_task(self, websocket: WebSocketClientProtocol, audio_queue: asyncio.Queue[bytes]):
        """Фоновая задача для получения аудио через WebSocket"""
        first_audio_received = False
        first_audio_time = None
        total_bytes = 0
        chunks_count = 0
        
        try:
            async for message in websocket:
                data = json.loads(message)
                
                if "audio" in data:
                    # Декодируем base64 аудио
                    audio_bytes = base64.b64decode(data["audio"])
                    
                    if not first_audio_received:
                        first_audio_time = time.perf_counter()
                        _jlog("ws_first_audio", bytes=len(audio_bytes), call_id=self.call_id)
                        first_audio_received = True
                    
                    total_bytes += len(audio_bytes)
                    chunks_count += 1
                    
                    await audio_queue.put(audio_bytes)
                    _jlog("ws_recv_audio", bytes=len(audio_bytes), is_final=data.get("isFinal", False), call_id=self.call_id)
                    
                elif "finalOutput" in data:
                    _jlog("ws_final_received", call_id=self.call_id)
                    break
                    
        except Exception as e:
            _jlog("ws_recv_error", error=str(e), call_id=self.call_id)
            raise TTSProtocolError(f"WebSocket receive error: {e}")
        finally:
            # Отправляем None в очередь как сигнал завершения
            await audio_queue.put(None)
            
            # Освобождаем соединение
            await self.connection_pool.release_connection(self.call_id, ConnectionType.WEBSOCKET)
            
            if first_audio_time:
                ttft_ms = (first_audio_time - time.perf_counter()) * 1000
                _jlog("ws_ttft", ms=round(ttft_ms, 2), total_bytes=total_bytes, chunks=chunks_count, call_id=self.call_id)


if __name__ == "__main__":
    import logging
    import sys
    from pathlib import Path
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    try:
        # Загружаем конфигурацию
        config_path = Path("configs/tts_config.yml")
        from .config import load_tts_config
        cfg = load_tts_config(config_path)
        
        async def test_tts():
            # Создаем пул соединений с настройками
            connection_pool = TTSConnectionPool(
                cfg, 
                max_connections=5,
                enable_retry=True,
                retry_attempts=3,
                enable_connection_pooling=True,
                enable_keep_alive=True
            )
            await connection_pool.start()
            
            try:
                # Тестируем HTTP streaming
                print("🧪 Тестируем HTTP streaming...")
                test_text = "Привет, это тестовая фраза для проверки TTS."
                
                tts_mgr = TTSManager(cfg, connection_pool, "test_call_1")
                async for chunk in tts_mgr.stream_static_text(test_text):
                    print(f"📦 Получен HTTP чанк: {len(chunk)} байт")
                    break  # Получаем только первый чанк для теста
                
                print("✅ HTTP streaming работает")
                
                # Тестируем WebSocket
                print("🧪 Тестируем WebSocket...")
                tts_mgr_ws = TTSManager(cfg, connection_pool, "test_call_2")
                text_q, audio_q = await tts_mgr_ws.start_llm_stream()
                
                # Отправляем тестовый текст
                await text_q.put("Тест WebSocket TTS")
                
                # Получаем первый аудио чанк
                audio_chunk = await audio_q.get()
                if audio_chunk:
                    print(f"📦 Получен WebSocket чанк: {len(audio_chunk)} байт")
                    print("✅ WebSocket streaming работает")
                
                # Останавливаем пул
                await connection_pool.close()
                
            except Exception as e:
                print(f"❌ Ошибка: {e}")
        
        asyncio.run(test_tts())
        
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        sys.exit(1)
