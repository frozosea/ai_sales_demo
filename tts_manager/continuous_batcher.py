#!/usr/bin/env python3
"""
Continuous Batching для параллельной обработки TTS запросов
Оптимизирует throughput и latency
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import heapq

class BatchStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TTSRequest:
    """TTS запрос для батчинга"""
    id: str
    text: str
    voice_id: str
    model_id: str
    priority: int = 0  # Приоритет (меньше = выше)
    created_at: float = field(default_factory=time.perf_counter)
    status: BatchStatus = BatchStatus.PENDING
    result: Optional[bytes] = None
    error: Optional[str] = None

@dataclass
class BatchConfig:
    """Конфигурация батчера"""
    max_batch_size: int = 8
    max_wait_time: float = 0.1  # 100ms максимальное ожидание
    min_batch_size: int = 1
    enable_priority: bool = True
    enable_dynamic_batching: bool = True


class ContinuousBatcher:
    """Continuous Batcher для TTS запросов"""
    
    def __init__(self, config: BatchConfig):
        self.config = config
        self.pending_requests: List[TTSRequest] = []
        self.processing_batches: Dict[str, List[TTSRequest]] = {}
        self.completed_requests: Dict[str, TTSRequest] = {}
        self.batch_counter = 0
        self.running = False
        self.batch_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Запускает батчер"""
        self.running = True
        self.batch_task = asyncio.create_task(self._batch_processor())
        print("Continuous Batcher started")
    
    async def stop(self):
        """Останавливает батчер"""
        self.running = False
        if self.batch_task:
            self.batch_task.cancel()
            try:
                await self.batch_task
            except asyncio.CancelledError:
                pass
        print("Continuous Batcher stopped")
    
    async def submit_request(self, text: str, voice_id: str, model_id: str, 
                           priority: int = 0) -> str:
        """Отправляет запрос в батчер"""
        request = TTSRequest(
            id=f"req_{int(time.perf_counter() * 1000)}",
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            priority=priority
        )
        
        # Добавляем в очередь с приоритетом
        if self.config.enable_priority:
            heapq.heappush(self.pending_requests, (priority, request.created_at, request))
        else:
            self.pending_requests.append(request)
        
        print(f"Request submitted: {request.id} (priority: {priority})")
        return request.id
    
    async def get_result(self, request_id: str, timeout: float = 10.0) -> Optional[bytes]:
        """Получает результат запроса"""
        start_time = time.perf_counter()
        
        while time.perf_counter() - start_time < timeout:
            if request_id in self.completed_requests:
                request = self.completed_requests[request_id]
                if request.status == BatchStatus.COMPLETED:
                    return request.result
                elif request.status == BatchStatus.FAILED:
                    raise Exception(f"Request failed: {request.error}")
            
            await asyncio.sleep(0.001)  # 1ms polling
        
        raise TimeoutError(f"Request {request_id} timed out")
    
    async def _batch_processor(self):
        """Основной процессор батчей"""
        while self.running:
            try:
                # Формируем батч из pending запросов
                batch = await self._form_batch()
                
                if batch:
                    # Обрабатываем батч
                    await self._process_batch(batch)
                else:
                    # Нет запросов, ждем немного
                    await asyncio.sleep(0.001)
                    
            except Exception as e:
                print(f"Batch processor error: {e}")
                await asyncio.sleep(0.01)
    
    async def _form_batch(self) -> Optional[List[TTSRequest]]:
        """Формирует батч из pending запросов"""
        if not self.pending_requests:
            return None
        
        batch = []
        current_time = time.perf_counter()
        
        # Берем запросы с учетом приоритета
        while self.pending_requests and len(batch) < self.config.max_batch_size:
            if self.config.enable_priority:
                priority, created_at, request = heapq.heappop(self.pending_requests)
            else:
                request = self.pending_requests.pop(0)
            
            # Проверяем, не слишком ли долго ждет запрос
            if current_time - request.created_at > self.config.max_wait_time:
                batch.append(request)
                continue
            
            # Если батч пустой, добавляем первый запрос
            if not batch:
                batch.append(request)
                continue
            
            # Проверяем совместимость с текущим батчем
            if self._is_compatible(request, batch[0]):
                batch.append(request)
            else:
                # Возвращаем обратно в очередь
                if self.config.enable_priority:
                    heapq.heappush(self.pending_requests, (request.priority, request.created_at, request))
                else:
                    self.pending_requests.insert(0, request)
                break
        
        return batch if batch else None
    
    def _is_compatible(self, request: TTSRequest, batch_leader: TTSRequest) -> bool:
        """Проверяет совместимость запроса с батчем"""
        return (request.voice_id == batch_leader.voice_id and 
                request.model_id == batch_leader.model_id)
    
    async def _process_batch(self, batch: List[TTSRequest]):
        """Обрабатывает батч запросов"""
        batch_id = f"batch_{self.batch_counter}"
        self.batch_counter += 1
        
        print(f"Processing batch {batch_id} with {len(batch)} requests")
        
        # Помечаем запросы как обрабатываемые
        for request in batch:
            request.status = BatchStatus.PROCESSING
        
        self.processing_batches[batch_id] = batch
        
        try:
            start_time = time.perf_counter()
            
            # Используем реальный процессор если доступен
            if hasattr(self, 'processor'):
                results = await self.processor.process_batch(batch)
                
                # Обновляем результаты запросов
                for request in batch:
                    if request.id in results:
                        request.result = results[request.id]
                        request.status = BatchStatus.COMPLETED
                    else:
                        request.status = BatchStatus.FAILED
                        request.error = "No result from processor"
            else:
                # Fallback к симуляции
                tasks = []
                for request in batch:
                    task = asyncio.create_task(self._process_single_request(request))
                    tasks.append(task)
                
                await asyncio.gather(*tasks)
            
            processing_time = (time.perf_counter() - start_time) * 1000
            print(f"Batch {batch_id} completed in {processing_time:.1f}ms")
            
        except Exception as e:
            print(f"Batch {batch_id} failed: {e}")
            for request in batch:
                request.status = BatchStatus.FAILED
                request.error = str(e)
        
        finally:
            # Перемещаем запросы в completed
            for request in batch:
                self.completed_requests[request.id] = request
            
            # Удаляем из processing
            del self.processing_batches[batch_id]
    
    async def _process_single_request(self, request: TTSRequest):
        """Обрабатывает один запрос в батче"""
        try:
            # Симуляция TTS обработки
            # В реальности здесь будет вызов ElevenLabs API
            await asyncio.sleep(0.05)  # 50ms симуляция
            
            # Генерируем фиктивный аудио результат
            audio_data = f"audio_for_{request.text[:10]}".encode()
            request.result = audio_data
            request.status = BatchStatus.COMPLETED
            
            print(f"Request {request.id} completed")
            
        except Exception as e:
            request.status = BatchStatus.FAILED
            request.error = str(e)
            print(f"Request {request.id} failed: {e}")
    
    def set_processor(self, processor):
        """Устанавливает процессор для обработки запросов"""
        self.processor = processor


# Функция для тестирования continuous batching
async def test_continuous_batching():
    """Тестирует continuous batching"""
    config = BatchConfig(
        max_batch_size=4,
        max_wait_time=0.05,  # 50ms
        enable_priority=True
    )
    
    batcher = ContinuousBatcher(config)
    await batcher.start()
    
    try:
        # Отправляем несколько запросов
        request_ids = []
        for i in range(8):
            request_id = await batcher.submit_request(
                f"Текст {i+1}",
                "voice_123",
                "eleven_flash_v2_5",
                priority=i % 3
            )
            request_ids.append(request_id)
        
        # Получаем результаты
        results = []
        for request_id in request_ids:
            result = await batcher.get_result(request_id)
            results.append(result)
            print(f"Got result for {request_id}: {len(result)} bytes")
        
        print(f"Processed {len(results)} requests")
        
    finally:
        await batcher.stop()


if __name__ == "__main__":
    asyncio.run(test_continuous_batching())
