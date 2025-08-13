#!/usr/bin/env python3
"""
Простой тест батчированного TTS
"""

import asyncio
import time
import sys
import os

# Добавляем родительскую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_manager.config import load_tts_config
from tts_manager.connection_pool import TTSConnectionPool, ConnectionType
from tts_manager.continuous_batcher import ContinuousBatcher, BatchConfig, TTSRequest, BatchStatus


class RealTTSProcessor:
    """Реальный процессор для TTS запросов"""
    
    def __init__(self, config, connection_pool):
        self.config = config
        self.connection_pool = connection_pool
    
    async def process_batch(self, requests):
        """Обрабатывает батч TTS запросов с реальными вызовами ElevenLabs"""
        results = {}
        
        print(f"Processing {len(requests)} requests in batch with real TTS")
        
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
                print(f"Processed request {request_id}: {len(result)} bytes")
            except Exception as e:
                print(f"Request {request_id} failed: {e}")
                results[request_id] = b""
        
        return results
    
    async def _process_single_request(self, request):
        """Обрабатывает один TTS запрос через ElevenLabs API"""
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


async def test_batched_tts():
    """Тестирует батчированный TTS"""
    print("Starting Batched TTS Test")
    
    # Загружаем конфигурацию
    config = load_tts_config("configs/tts_config.yml")
    print(f"Loaded config: {config.model_id}")
    
    # Создаем пул соединений
    connection_pool = TTSConnectionPool(
        config,
        max_connections=10,
        enable_connection_pooling=True,
        enable_warming=True,
        proxy_url="http://127.0.0.1:7890"
    )
    
    await connection_pool.start()
    print("Connection pool started")
    
    try:
        # Создаем батчер
        batch_cfg = BatchConfig(
            max_batch_size=4,
            max_wait_time=0.05,
            enable_priority=True
        )
        
        batcher = ContinuousBatcher(batch_cfg)
        
        # Создаем процессор
        processor = RealTTSProcessor(config, connection_pool)
        batcher.set_processor(processor)
        
        await batcher.start()
        print("Batcher started")
        
        # Тестируем несколько запросов
        texts = [
            "Привет, как дела?",
            "Сегодня хорошая погода.",
            "Стоимость 12000 рублей.",
            "Это тестовое сообщение.",
            "Еще один запрос для тестирования.",
            "Последний запрос в батче."
        ]
        
        start_time = time.perf_counter()
        
        # Отправляем запросы
        request_ids = []
        for i, text in enumerate(texts):
            request_id = await batcher.submit_request(
                text=text,
                voice_id=config.voice_id,
                model_id=config.model_id,
                priority=i % 3
            )
            request_ids.append(request_id)
            print(f"Submitted request {i+1}: {request_id}")
        
        # Получаем результаты
        results = []
        for i, request_id in enumerate(request_ids):
            try:
                result = await batcher.get_result(request_id, timeout=10.0)
                results.append(result)
                print(f"Got result {i+1}: {len(result)} bytes")
            except Exception as e:
                print(f"Failed to get result {i+1}: {e}")
                results.append(b"")
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        print(f"\n=== RESULTS ===")
        print(f"Processed {len(texts)} requests in {total_time:.1f}ms")
        print(f"Average time per request: {total_time/len(texts):.1f}ms")
        print(f"Throughput: {len(texts)/(total_time/1000):.1f} req/sec")
        
        for i, (text, result) in enumerate(zip(texts, results)):
            print(f"Request {i+1}: {len(result)} bytes for '{text[:20]}...'")
        
        await batcher.stop()
        print("Batcher stopped")
        
    finally:
        await connection_pool.close()
        print("Connection pool closed")


if __name__ == "__main__":
    asyncio.run(test_batched_tts())
