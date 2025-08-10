from __future__ import annotations
from dataclasses import dataclass
import os
import redis.asyncio as redis

@dataclass(slots=True)
class RedisConfig:
    """
    Единая точка конфигурации Redis-клиента.
    Значения по умолчанию берутся из env-переменных:
      REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
    """
    host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    db: int = int(os.getenv("REDIS_DB", "0"))
    password: str | None = os.getenv("REDIS_PASSWORD")
    decode_responses: bool = False  # работаем в bytes для аудио
    socket_timeout: int = 5
    socket_connect_timeout: int = 3

    def build(self) -> redis.Redis:
        """
        Возвращает redis.asyncio.Redis с пулом соединений.
        decode_responses=False — важно для хранения bytes в списках.
        """
        return redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=self.decode_responses,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
        )
