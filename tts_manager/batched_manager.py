#!/usr/bin/env python3
"""
TTS Manager с Continuous Batching для минимальной задержки
Интегрирует батчинг с реальными TTS запросами
"""

import asyncio
import time
import json
import logging
from typing import AsyncGenerator, Optional
from dataclasses import dataclass

try:
    from .config import TTSConfig
    from .connection_pool import TTSConnectionPool, ConnectionType
    from .continuous_batcher import ContinuousBatcher, BatchConfig, TTSRequest
except ImportError:
    from config import TTSConfig
    from connection_pool import TTSConnectionPool, ConnectionType
    from continuous_batcher import ContinuousBatcher, BatchConfig, TTSRequest

log = logging.getLogger("tts_batched")

@dataclass
class BatchedTTSConfig:
    """Конфигурация батчированного TTS"""
    batch_size: int = 4
    max_wait_time: float = 0.05  # 50ms для минимальной задержки
    enable_priority: bool = True
    enable_dynamic_batching: bool = True
    pre_warm_batches: int = 2  # Количество предварительно разогретых батчей


class BatchedTTSManager:
    """TTS Manager с continuous batching"""
    
    def __init__(self, config: TTSConfig, connection_pool: TTSConnectionPool, 
                 batch_config: Optional[BatchedTTSConfig] = None):
        self.config = config
        self.connection_pool = connection_pool
        self.batch_config = batch_config or BatchedTTSConfig()
        
        # Создаем батчер
        batch_cfg = BatchConfig(
            max_batch_size=self.batch_config.batch_size,
            max_wait_time=self.batch_config.max_wait_time,
            enable_priority=self.batch_config.enable_priority,
            enable_dynamic_batching=self.batch_config.enable_dynamic_batching
        )
        
        self.batcher = ContinuousBatcher(batch_cfg)
        self.running = False
        
        # Создаем процессор для реальных TTS запросов
        self.processor = BatchedTTSProcessor(config, connection_pool)
        self.batcher.set_processor(self.processor)
        
    async def start(self):
        """Запускает батчированный TTS manager"""
        self.running = True
        await self.batcher.start()
        
        # Pre-warming батчей
        if self.batch_config.pre_warm_batches > 0:
            await self._pre_warm_batches()
        
        log.info("Batched TTS Manager started")
    
    async def stop(self):
        """Останавливает батчированный TTS manager"""
        self.running = False
        await self.batcher.stop()
        log.info("Batched TTS Manager stopped")
    
    async def stream_text_batched(self, text: str, priority: int = 0) -> AsyncGenerator[bytes, None]:
        """Стримит текст через батчированный TTS"""
        if not self.running:
            raise RuntimeError("Batched TTS Manager not started")
        
        # Отправляем запрос в батчер
        request_id = await self.batcher.submit_request(
            text=text,
            voice_id=self.config.voice_id,
            model_id=self.config.model_id,
            priority=priority
        )
        
        # Получаем результат
        try:
            result = await self.batcher.get_result(request_id, timeout=10.0)
            if result:
                yield result
        except Exception as e:
            log.error(f"Batched TTS request failed: {e}")
            raise
    
    async def _pre_warm_batches(self):
        """Предварительно разогревает батчи"""
        log.info(f"Pre-warming {self.batch_config.pre_warm_batches} batches")
        
        # Отправляем dummy запросы для разогрева
        warm_requests = []
        for i in range(self.batch_config.pre_warm_batches * self.batch_config.batch_size):
            request_id = await self.batcher.submit_request(
                text=f"warm_{i}",
                voice_id=self.config.voice_id,
                model_id=self.config.model_id,
                priority=0
            )
            warm_requests.append(request_id)
        
        # Ждем завершения разогрева
        await asyncio.sleep(0.1)
        log.info("Pre-warming completed")


class BatchedTTSProcessor:
    """Процессор для обработки TTS запросов в батче"""
    
    def __init__(self, config: TTSConfig, connection_pool: TTSConnectionPool):
        self.config = config
        self.connection_pool = connection_pool
    
    async def process_batch(self, requests: list[TTSRequest]) -> dict[str, bytes]:
        """Обрабатывает батч TTS запросов"""
        results = {}
        
        # Обрабатываем все запросы в батче параллельно
        tasks = []
        for request in requests:
            task = asyncio.create_task(self._process_single_request(request))
            tasks.append((request.id, task))
        
        # Ждем завершения всех задач
        for request_id, task in tasks:
            try:
                result = await task
                results[request_id] = result
            except Exception as e:
                log.error(f"Request {request_id} failed: {e}")
                # Возвращаем пустой результат для failed запросов
                results[request_id] = b""
        
        return results
    
    async def _process_single_request(self, request: TTSRequest) -> bytes:
        """Обрабатывает один TTS запрос"""
        try:
            # Получаем HTTP соединение
            http_client = await self.connection_pool.get_http_connection(request.id)
            
            # Строим URL
            url = f"{self.config.http_base_url}/v1/text-to-speech/{request.voice_id}/stream"
            params = {
                "output_format": self.config.http_output_format,
            }
            
            if self.config.optimize_streaming_latency is not None:
                params["optimize_streaming_latency"] = self.config.optimize_streaming_latency
            
            # Подготавливаем данные
            data = {
                "text": request.text,
                "model_id": request.model_id,
                "voice_settings": {
                    "stability": self.config.voice_stability,
                    "similarity_boost": self.config.voice_similarity_boost,
                    "style": 0,
                    "use_speaker_boost": False,
                    "speed": self.config.voice_speed
                }
            }
            
            if self.config.language_code:
                data["language_code"] = self.config.language_code
            
            headers = {"Content-Type": "application/json"}
            
            # Выполняем запрос
            async with http_client.stream("POST", url, params=params, json=data, headers=headers) as response:
                response.raise_for_status()
                
                # Собираем все аудио данные
                audio_data = b""
                async for chunk in response.aiter_bytes():
                    if chunk:
                        audio_data += chunk
                
                return audio_data
                
        finally:
            # Освобождаем соединение
            await self.connection_pool.release_connection(request.id, ConnectionType.HTTP)


# Функция для тестирования батчированного TTS
async def test_batched_tts():
    """Тестирует батчированный TTS"""
    from .config import load_tts_config
    
    # Загружаем конфигурацию
    try:
        config = load_tts_config("configs/tts_config.yml")
    except ImportError:
        from config import load_tts_config
        config = load_tts_config("configs/tts_config.yml")
    
    # Создаем пул соединений
    connection_pool = TTSConnectionPool(
        config,
        max_connections=10,
        enable_connection_pooling=True,
        enable_warming=True,
        proxy_url="http://127.0.0.1:7890"
    )
    
    await connection_pool.start()
    
    try:
        # Создаем батчированный TTS manager
        batch_config = BatchedTTSConfig(
            batch_size=4,
            max_wait_time=0.05,
            enable_priority=True
        )
        
        manager = BatchedTTSManager(config, connection_pool, batch_config)
        await manager.start()
        
        # Тестируем несколько запросов
        texts = [
            "Привет, как дела?",
            "Сегодня хорошая погода.",
            "Стоимость 12000 рублей.",
            "Это тестовое сообщение."
        ]
        
        start_time = time.perf_counter()
        
        # Отправляем запросы с разными приоритетами
        tasks = []
        for i, text in enumerate(texts):
            task = asyncio.create_task(
                _test_single_request(manager, text, priority=i % 3)
            )
            tasks.append(task)
        
        # Ждем завершения всех запросов
        results = await asyncio.gather(*tasks)
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        print(f"Processed {len(texts)} requests in {total_time:.1f}ms")
        print(f"Average time per request: {total_time/len(texts):.1f}ms")
        
        for i, (text, result) in enumerate(zip(texts, results)):
            print(f"Request {i+1}: {len(result)} bytes for '{text[:20]}...'")
        
        await manager.stop()
        
    finally:
        await connection_pool.close()


async def _test_single_request(manager: BatchedTTSManager, text: str, priority: int) -> bytes:
    """Тестирует один запрос"""
    start_time = time.perf_counter()
    
    result = b""
    async for chunk in manager.stream_text_batched(text, priority):
        result += chunk
    
    request_time = (time.perf_counter() - start_time) * 1000
    print(f"Request completed in {request_time:.1f}ms (priority: {priority})")
    
    return result


if __name__ == "__main__":
    asyncio.run(test_batched_tts())
