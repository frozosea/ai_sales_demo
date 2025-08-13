#!/usr/bin/env python3
"""
Сравнение обычного и батчированного подходов к TTS
"""

import asyncio
import time
import sys
import os
import statistics
from typing import List, Dict

# Добавляем родительскую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_manager.config import load_tts_config
from tts_manager.connection_pool import TTSConnectionPool, ConnectionType
from tts_manager.manager import TTSManager
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
        """Обрабатывает один TTS запрос через ElevenLabs API с замером TTFA"""
        try:
            # Получаем HTTP соединение
            connection_start = time.perf_counter()
            http_client = await self.connection_pool.get_http_connection(request.id)
            connection_time = (time.perf_counter() - connection_start) * 1000
            
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
            
            # Измеряем время отправки запроса
            request_start = time.perf_counter()
            
            # Выполняем запрос
            async with http_client.stream("POST", url, params=params, json=data, headers=headers) as response:
                response.raise_for_status()
                
                # Измеряем время до первого байта (TTFA)
                first_byte_received = False
                first_byte_time = None
                audio_data = b""
                
                async for chunk in response.aiter_bytes():
                    if chunk:
                        if not first_byte_received:
                            first_byte_time = (time.perf_counter() - request_start) * 1000
                            first_byte_received = True
                        audio_data += chunk
                
                # Сохраняем метрики в request
                request.connection_time = connection_time
                request.ttfa_time = first_byte_time
                request.total_time = (time.perf_counter() - request_start) * 1000
                
                return audio_data
                
        finally:
            # Освобождаем соединение
            await self.connection_pool.release_connection(request.id, ConnectionType.HTTP)


async def test_sequential_approach(config, connection_pool, texts: List[str]) -> Dict:
    """Тестирует последовательный подход с замером TTFA"""
    print("\n=== SEQUENTIAL APPROACH ===")
    
    results = {
        "total_time": 0,
        "individual_times": [],
        "ttfa_times": [],
        "connection_times": [],
        "total_bytes": 0,
        "success_count": 0
    }
    
    start_time = time.perf_counter()
    
    for i, text in enumerate(texts):
        try:
            request_start = time.perf_counter()
            
            # Создаем менеджер для каждого запроса
            call_id = f"seq_{i+1}"
            tts_mgr = TTSManager(config, connection_pool, call_id)
            
            # Измеряем время получения соединения
            connection_start = time.perf_counter()
            http_client = await connection_pool.get_http_connection(call_id)
            connection_time = (time.perf_counter() - connection_start) * 1000
            
            # Выполняем TTS запрос с замером TTFA
            audio_data = b""
            first_byte_received = False
            first_byte_time = None
            
            async for chunk in tts_mgr.stream_static_text(text):
                if not first_byte_received:
                    first_byte_time = (time.perf_counter() - request_start) * 1000
                    first_byte_received = True
                audio_data += chunk
            
            request_time = (time.perf_counter() - request_start) * 1000
            
            results["individual_times"].append(request_time)
            results["ttfa_times"].append(first_byte_time or request_time)
            results["connection_times"].append(connection_time)
            results["total_bytes"] += len(audio_data)
            results["success_count"] += 1
            
            print(f"Sequential request {i+1}: {request_time:.1f}ms, TTFA: {first_byte_time or request_time:.1f}ms, {len(audio_data)} bytes")
            
        except Exception as e:
            print(f"Sequential request {i+1} failed: {e}")
            results["individual_times"].append(0)
            results["ttfa_times"].append(0)
            results["connection_times"].append(0)
    
    results["total_time"] = (time.perf_counter() - start_time) * 1000
    
    return results


async def test_batched_approach(config, connection_pool, texts: List[str]) -> Dict:
    """Тестирует батчированный подход с замером TTFA"""
    print("\n=== BATCHED APPROACH ===")
    
    results = {
        "total_time": 0,
        "individual_times": [],
        "ttfa_times": [],
        "connection_times": [],
        "total_bytes": 0,
        "success_count": 0,
        "batch_times": []
    }
    
    # Создаем батчер
    batch_cfg = BatchConfig(
        max_batch_size=4,
        max_wait_time=0.05,
        enable_priority=True
    )
    
    batcher = ContinuousBatcher(batch_cfg)
    processor = RealTTSProcessor(config, connection_pool)
    batcher.set_processor(processor)
    
    await batcher.start()
    
    try:
        start_time = time.perf_counter()
        
        # Отправляем все запросы
        request_ids = []
        for i, text in enumerate(texts):
            request_id = await batcher.submit_request(
                text=text,
                voice_id=config.voice_id,
                model_id=config.model_id,
                priority=i % 3
            )
            request_ids.append(request_id)
        
        # Получаем результаты
        for i, request_id in enumerate(request_ids):
            try:
                request_start = time.perf_counter()
                result = await batcher.get_result(request_id, timeout=10.0)
                request_time = (time.perf_counter() - request_start) * 1000
                
                # Получаем метрики из request (если доступны)
                ttfa_time = getattr(batcher.completed_requests.get(request_id), 'ttfa_time', request_time)
                connection_time = getattr(batcher.completed_requests.get(request_id), 'connection_time', 0)
                
                results["individual_times"].append(request_time)
                results["ttfa_times"].append(ttfa_time)
                results["connection_times"].append(connection_time)
                results["total_bytes"] += len(result)
                results["success_count"] += 1
                
                print(f"Batched request {i+1}: {request_time:.1f}ms, TTFA: {ttfa_time:.1f}ms, {len(result)} bytes")
                
            except Exception as e:
                print(f"Batched request {i+1} failed: {e}")
                results["individual_times"].append(0)
                results["ttfa_times"].append(0)
                results["connection_times"].append(0)
        
        results["total_time"] = (time.perf_counter() - start_time) * 1000
        
    finally:
        await batcher.stop()
    
    return results


def print_comparison(sequential_results: Dict, batched_results: Dict):
    """Выводит сравнение результатов"""
    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    
    # Общие метрики
    print(f"Total Requests: {len(sequential_results['individual_times'])}")
    print(f"Sequential Success: {sequential_results['success_count']}/{len(sequential_results['individual_times'])}")
    print(f"Batched Success: {batched_results['success_count']}/{len(batched_results['individual_times'])}")
    
    # Время выполнения
    print(f"\nTotal Time:")
    print(f"  Sequential: {sequential_results['total_time']:.1f}ms")
    print(f"  Batched:    {batched_results['total_time']:.1f}ms")
    print(f"  Speedup:    {sequential_results['total_time']/batched_results['total_time']:.1f}x")
    
    # TTFA метрики (если доступны)
    if 'ttfa_times' in sequential_results and 'ttfa_times' in batched_results:
        seq_ttfa_avg = statistics.mean([t for t in sequential_results['ttfa_times'] if t > 0])
        batched_ttfa_avg = statistics.mean([t for t in batched_results['ttfa_times'] if t > 0])
        
        print(f"\nTTFA (Time To First Audio):")
        print(f"  Sequential: {seq_ttfa_avg:.1f}ms")
        print(f"  Batched:    {batched_ttfa_avg:.1f}ms")
        print(f"  Improvement: {seq_ttfa_avg/batched_ttfa_avg:.1f}x")
        
        # Connection time метрики
        if 'connection_times' in sequential_results and 'connection_times' in batched_results:
            seq_conn_avg = statistics.mean([t for t in sequential_results['connection_times'] if t > 0])
            batched_conn_avg = statistics.mean([t for t in batched_results['connection_times'] if t > 0])
            
            print(f"\nConnection Time:")
            print(f"  Sequential: {seq_conn_avg:.1f}ms")
            print(f"  Batched:    {batched_conn_avg:.1f}ms")
            print(f"  Improvement: {seq_conn_avg/batched_conn_avg:.1f}x")
    
    # Среднее время на запрос
    seq_avg = statistics.mean([t for t in sequential_results['individual_times'] if t > 0])
    batched_avg = statistics.mean([t for t in batched_results['individual_times'] if t > 0])
    
    print(f"\nAverage Time per Request:")
    print(f"  Sequential: {seq_avg:.1f}ms")
    print(f"  Batched:    {batched_avg:.1f}ms")
    print(f"  Improvement: {seq_avg/batched_avg:.1f}x")
    
    # Throughput
    seq_throughput = len(sequential_results['individual_times']) / (sequential_results['total_time'] / 1000)
    batched_throughput = len(batched_results['individual_times']) / (batched_results['total_time'] / 1000)
    
    print(f"\nThroughput:")
    print(f"  Sequential: {seq_throughput:.1f} req/sec")
    print(f"  Batched:    {batched_throughput:.1f} req/sec")
    print(f"  Improvement: {batched_throughput/seq_throughput:.1f}x")
    
    # Общий объем данных
    print(f"\nTotal Data:")
    print(f"  Sequential: {sequential_results['total_bytes']} bytes")
    print(f"  Batched:    {batched_results['total_bytes']} bytes")
    
    # Детальная статистика
    print(f"\nDetailed Statistics:")
    print(f"  Sequential - Min: {min([t for t in sequential_results['individual_times'] if t > 0]):.1f}ms, "
          f"Max: {max([t for t in sequential_results['individual_times'] if t > 0]):.1f}ms")
    print(f"  Batched    - Min: {min([t for t in batched_results['individual_times'] if t > 0]):.1f}ms, "
          f"Max: {max([t for t in batched_results['individual_times'] if t > 0]):.1f}ms")


async def main():
    """Главная функция"""
    print("Starting TTS Approach Comparison")
    
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
        # Тестовые тексты
        texts = [
            "Привет, как дела?",
            "Сегодня хорошая погода.",
            "Стоимость 12000 рублей.",
            "Это тестовое сообщение.",
            "Еще один запрос для тестирования.",
            "Последний запрос в батче."
        ]
        
        # Тестируем последовательный подход
        sequential_results = await test_sequential_approach(config, connection_pool, texts)
        
        # Тестируем батчированный подход
        batched_results = await test_batched_approach(config, connection_pool, texts)
        
        # Выводим сравнение
        print_comparison(sequential_results, batched_results)
        
    finally:
        await connection_pool.close()
        print("Connection pool closed")


if __name__ == "__main__":
    asyncio.run(main())
