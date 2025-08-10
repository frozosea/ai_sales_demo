from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, List
import numpy as np

from intent_classifier.model_wrapper import OnnxModelWrapper

logger = logging.getLogger("intent.model_manager")

@dataclass
class ModelManagerConfig:
    warmup_interval_sec: float = 10.0  # Интервал между прогревами
    warmup_text: str = "прогрев"  # Текст для прогрева
    max_idle_time_sec: float = 30.0  # Максимальное время простоя

class ModelManager:
    _instance: Optional[ModelManager] = None
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        self._model: Optional[OnnxModelWrapper] = None
        self._is_running = False
        self._warmup_task: Optional[asyncio.Task] = None
        self._last_used = 0.0
        self._config: Optional[ModelManagerConfig] = None

    @classmethod
    def get_instance(cls) -> ModelManager:
        if not cls._instance:
            cls._instance = ModelManager()
        return cls._instance

    @classmethod
    def initialize(cls, model_path: str, device: str = "cpu", config: Optional[ModelManagerConfig] = None) -> None:
        instance = cls.get_instance()
        if instance._is_running:
            logger.debug("ModelManager is already initialized. Skipping.")
            return
        instance._model = OnnxModelWrapper(model_path, device)
        instance._config = config or ModelManagerConfig()
        instance._is_running = True
        instance._warmup_task = asyncio.create_task(instance._warmup_loop())
        logger.info("ModelManager initialized")

    async def embed(self, texts: List[str]) -> np.ndarray:
        """Враппер для model.embed с обновлением времени последнего использования"""
        if not self._model:
            raise RuntimeError("ModelManager not initialized")
        
        self._last_used = time.monotonic()
        return await self._model.embed(texts)

    async def _warmup_loop(self) -> None:
        """Периодически прогревает модель, если она не использовалась"""
        while self._is_running:
            try:
                current_time = time.monotonic()
                idle_time = current_time - self._last_used

                # Прогреваем только если модель простаивала
                if idle_time >= self._config.warmup_interval_sec:
                    logger.debug(f"Warming up model after {idle_time:.1f}s idle")
                    t_start = time.monotonic()
                    await self._model.embed([self._config.warmup_text])
                    t_end = time.monotonic()
                    logger.debug(f"Warmup took {(t_end - t_start) * 1000:.1f}ms")

                # Спим меньше, если модель давно не использовалась
                sleep_time = min(
                    self._config.warmup_interval_sec,
                    max(1.0, self._config.warmup_interval_sec - idle_time)
                )
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in warmup loop: {str(e)}")
                await asyncio.sleep(1.0)  # Короткая пауза перед повторной попыткой

    @classmethod
    async def close(cls) -> None:
        """Останавливает менеджер и освобождает ресурсы"""
        instance = cls.get_instance()
        instance._is_running = False
        if instance._warmup_task:
            instance._warmup_task.cancel()
            try:
                await instance._warmup_task
            except asyncio.CancelledError:
                pass
        logger.info("ModelManager closed") 