from __future__ import annotations

import asyncio
import io
import logging
from typing import ClassVar, List, Optional

import redis.asyncio as redis
from pydub import AudioSegment

from domain.interfaces.cache import AbstractCache
from infra.redis_config import RedisConfig

logger = logging.getLogger(__name__)


class RedisCacheManager(AbstractCache):
    _instance: ClassVar[Optional[RedisCacheManager]] = None
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, config: RedisConfig | None = None):
        if not hasattr(self, "_initialized"):
            self.config: RedisConfig = config or RedisConfig()
            self.redis_client: redis.Redis | None = None
            self._initialized: bool = True
            logger.info("RedisCacheManager initialized.")

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        if self.redis_client:
            logger.warning("Redis client already connected.")
            return

        async with self._lock:
            if not self.redis_client:
                try:
                    logger.info(f"Connecting to Redis at {self.config.host}:{self.config.port}...")
                    client = self.config.build()
                    await client.ping()
                    self.redis_client = client
                    logger.info("Successfully connected to Redis.")
                except redis.RedisError as e:
                    logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
                    self.redis_client = None
                    raise

    async def close(self) -> None:
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Redis connection pool closed.")
            except redis.RedisError as e:
                logger.error(f"Error closing Redis connection: {e}", exc_info=True)
            finally:
                self.redis_client = None

    @staticmethod
    def _read_and_chunk_wav(wav_filepath: str, chunk_size_ms: int) -> list[bytes]:
        try:
            audio = AudioSegment.from_wav(wav_filepath)
            chunks = []
            for i in range(0, len(audio), chunk_size_ms):
                chunk_segment = audio[i:i + chunk_size_ms]
                buffer = io.BytesIO()
                chunk_segment.export(buffer, format="wav")
                chunks.append(buffer.getvalue())
            return chunks
        except FileNotFoundError:
            logger.error(f"WAV file not found at path: {wav_filepath}")
            return []
        except Exception as e:
            logger.error(f"Failed to read and chunk WAV file {wav_filepath}: {e}", exc_info=True)
            return []

    async def load_and_set_audio(self, key: str, wav_filepath: str, chunk_size_ms: int = 20) -> bool:
        logger.info(f"Loading audio from '{wav_filepath}' for key '{key}'.")
        try:
            audio_chunks = await asyncio.to_thread(
                self._read_and_chunk_wav, wav_filepath, chunk_size_ms
            )
            if not audio_chunks:
                return False
            return await self.set_audio_chunks(key, audio_chunks)
        except Exception as e:
            logger.error(f"Error in load_and_set_audio for key '{key}': {e}", exc_info=True)
            return False

    async def set_audio_chunks(self, key: str, audio_chunks: list[bytes]) -> bool:
        if not self.redis_client:
            logger.error("Cannot set audio chunks: Redis client is not connected.")
            return False
        try:
            async with self.redis_client.pipeline(transaction=True) as pipe:
                await pipe.delete(key).rpush(key, *audio_chunks).execute()
            logger.info(f"Successfully set {len(audio_chunks)} audio chunks for key '{key}'.")
            return True
        except redis.RedisError as e:
            logger.error(f"Redis error setting audio chunks for key '{key}': {e}", exc_info=True)
            return False

    async def get_audio_chunks(self, key: str) -> list[bytes] | None:
        if not self.redis_client:
            logger.error("Cannot get audio chunks: Redis client is not connected.")
            return None
        try:
            chunks = await self.redis_client.lrange(key, 0, -1)
            if not chunks:
                logger.debug(f"Cache miss for audio chunks with key '{key}'.")
                return None
            logger.info(f"Cache hit for audio chunks with key '{key}'. Found {len(chunks)} chunks.")
            return chunks
        except redis.RedisError as e:
            logger.error(f"Redis error getting audio chunks for key '{key}': {e}", exc_info=True)
            return None

    async def set_text(self, key: str, text: str, ttl_seconds: int) -> bool:
        if not self.redis_client:
            logger.error("Cannot set text: Redis client is not connected.")
            return False
        try:
            await self.redis_client.set(key, text, ex=ttl_seconds)
            logger.info(f"Successfully set text for key '{key}' with TTL {ttl_seconds}s.")
            return True
        except redis.RedisError as e:
            logger.error(f"Redis error setting text for key '{key}': {e}", exc_info=True)
            return False

    async def get_text(self, key: str) -> str | None:
        if not self.redis_client:
            logger.error("Cannot get text: Redis client is not connected.")
            return None
        try:
            value: bytes | None = await self.redis_client.get(key)
            if value is None:
                logger.debug(f"Cache miss for text with key '{key}'.")
                return None
            logger.info(f"Cache hit for text with key '{key}'.")
            return value.decode("utf-8")
        except redis.RedisError as e:
            logger.error(f"Redis error getting text for key '{key}': {e}", exc_info=True)
            return None
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode text from Redis for key '{key}': {e}", exc_info=True)
            return None
