1) SPEC-A-Cache-Interface.md

✅ Контекст

Этот документ описывает единый контракт кэша для всего проекта. Модуль кэша — это высокопроизводительное KV-хранилище на Redis, обслуживающее:
	1.	Статические аудио-фрагменты (static:*) — список bytes (Redis List).
	2.	Кэш TTS (tts:<text_hash|plain>) — список bytes (Redis List).
	3.	Суммаризации LLM (summary:session:<hash>) — строка (Redis String) с TTL.

Цель: дать стабильный интерфейс, который будет реализован RedisCacheManager и использоваться другими модулями (LLM/Orchestrator/TTS).

📦 Файл

domain/interfaces/cache.py

🔗 Зависимости (импорты)

Только стандартная библиотека:
	•	abc, typing

🧾 Требования к интерфейсу
	•	Асинхронные методы.
	•	Возвраты «мягкие»: bool/Optional, без исключений наружу.

✍️ Спецификация (сигнатуры зафиксированы)

from __future__ import annotations
import abc
from typing import List, Optional

class AbstractCache(abc.ABC):
    @abc.abstractmethod
    async def connect(self) -> None: ...
    @abc.abstractmethod
    async def close(self) -> None: ...

    @abc.abstractmethod
    async def load_and_set_audio(self, key: str, wav_filepath: str, chunk_size_ms: int = 20) -> bool: ...
    @abc.abstractmethod
    async def set_audio_chunks(self, key: str, audio_chunks: List[bytes]) -> bool: ...
    @abc.abstractmethod
    async def get_audio_chunks(self, key: str) -> Optional[List[bytes]]: ...

    @abc.abstractmethod
    async def set_text(self, key: str, text: str, ttl_seconds: int) -> bool: ...
    @abc.abstractmethod
    async def get_text(self, key: str) -> Optional[str]: ...

✅ Критерии приёмки
	•	Импортируется без внешних пакетов.
	•	Сигнатуры 1:1 совпадают с реализацией RedisCacheManager.

⸻

2) SPEC-B-RedisConfig.md

✅ Контекст

Этот документ описывает конфигурацию Redis и фабрику клиента. Все модули кэша подключаются к Redis только через этот конфиг. По умолчанию параметры берутся из env-переменных.

Ключевые кейсы хранения:
	•	static:* и tts:* — Redis List из bytes.
	•	summary:session:* — Redis String с TTL.

📦 Файл

infra/redis_config.py

🔗 Зависимости (импорты)
	•	redis>=5.0 (импорт: import redis.asyncio as redis)
	•	stdlib: dataclasses, os

✍️ Спецификация

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

✅ Критерии приёмки
	•	build() возвращает валидный redis.asyncio.Redis.
	•	Поддержка bytes (decode_responses=False).

⸻

3) SPEC-C-RedisCacheManager-and-ManualTest.md

✅ Контекст

Это финальная спецификация реализации кэша и ручного e2e-теста с реальным Redis.
Мы обеспечиваем:
	•	низкую задержку за счёт Redis List + LRANGE,
	•	атомарные перезаписи аудио ключей (DEL → RPUSH в pipeline),
	•	неблокирующее чтение WAV через asyncio.to_thread,
	•	«мягкие» ошибки: логируем и возвращаем False/None.

Кейсы хранения:
	1.	static:* — предзаписанные аудио-фрагменты (List[bytes])
	2.	tts:* — кэш TTS-синтеза (List[bytes])
	3.	summary:session:* — кэш суммаризаций (String с TTL)

📦 Файлы
	•	Реализация: cache/cache.py
	•	Ручной тест: cache/test/manual_test_cache.py
	•	Тест-данные: cache/test/test_data/example.wav
(копируем из project_root/test_data/example.wav автоматически — если нет, логируем и выходим)

🔗 Зависимости (импорты)

Runtime:
redis>=5.0 (redis.asyncio), asyncio, dataclasses, typing, pathlib, logging, time, argparse, wave, math, os, json
Внутренние:
from infra.redis_config import RedisConfig
from domain.interfaces.cache import AbstractCache

⸻

✍️ Спецификация реализации RedisCacheManager (Singleton)

Файл: cache/cache.py

Общее
	•	Наследуемся от AbstractCache.
	•	Singleton (__new__ или .instance() — любой вариант, но 1 объект на процесс).
	•	Держим self._redis: redis.asyncio.Redis | None.
	•	Каждая операция с Redis: try/except redis.RedisError → лог redis_error и «мягкий» False/None.

Ключи
	•	статик: static:<name>
	•	tts: tts:<text_or_hash>
	•	summary: summary:session:<hash>

Методы

class RedisCacheManager(AbstractCache):
    def __new__(cls, *args, **kwargs): ...
    def __init__(self, config: RedisConfig): ...

    async def connect(self) -> None: ...
    async def close(self) -> None: ...

    async def load_and_set_audio(self, key: str, wav_filepath: str, chunk_size_ms: int = 20) -> bool: ...
    async def set_audio_chunks(self, key: str, audio_chunks: list[bytes]) -> bool: ...
    async def get_audio_chunks(self, key: str) -> Optional[list[bytes]]: ...

    async def set_text(self, key: str, text: str, ttl_seconds: int) -> bool: ...
    async def get_text(self, key: str) -> Optional[str]: ...

Детали реализации
	•	connect() — создаём клиента: self._redis = config.build(); await self._redis.ping() внутри try/except.
	•	close() — await self._redis.aclose() и обнулить ссылку.
	•	set_audio_chunks() — pipeline (transaction=True):
	•	DEL key
	•	RPUSH key *audio_chunks (bytes элементы)
	•	(опц.) PEXPIRE key <ms> для TTS, но не для static:*
	•	get_audio_chunks() — LRANGE key 0 -1 → list[bytes] | None (если ключа нет — None).
	•	set_text() — SETEX key ttl_seconds text (строка).
	•	get_text() — GET key:
	•	при decode_responses=False придут bytes → декодировать utf-8.
	•	load_and_set_audio():
	•	Чтение WAV через asyncio.to_thread (не блокируем loop).
	•	Логируем nchannels, sampwidth, framerate, nframes, duration_ms.
	•	Резка строго по фреймам:

frames_per_chunk = max(1, int(framerate * chunk_ms / 1000))
frame_size = nchannels * sampwidth
bytes_per_chunk = frames_per_chunk * frame_size


	•	Формируем List[bytes] и шлём в set_audio_chunks(key, chunks).

Ограничения/защита
	•	MAX_CHUNKS = 20000 — логировать и отбрасывать хвост, если превышено.
	•	JSON-лог на ключевых событиях: warmup_done, set_audio_chunks_ok, get_audio_chunks_hit/miss, redis_error.

⸻

✍️ Спецификация ручного e2e-теста

Файл: cache/test/manual_test_cache.py

Цели
	•	Подключиться к Redis (через RedisConfig).
	•	Прогреть кэш аудио load_and_set_audio на example.wav.
	•	Проверить get_audio_chunks (hit/miss) с таймингами.
	•	Проверить set_text/get_text с TTL и истечением.
	•	Параллельный бенч чтения одного ключа (N=3–5): метрики p50/p95 по первому чанку и total.
	•	Все логи — строго JSON одной строкой.

Скрипт — структура
	•	JSON-логгер (logging.basicConfig(format="%(message)s") + helper jlog()).
	•	Автокопия project_root/test_data/example.wav → cache/test/test_data/example.wav если нет.
	•	CLI-аргументы: --key, --wav, --chunk-ms, --concurrency (дефолты: "static:test_example", 20, 5).
	•	Корутинка bench_stream_read():
	•	get_audio_chunks(key); метки времени: t0, t_first, t_start_stream, t_end_stream.
	•	Сумма байт и кол-во чанков; лог bench_read_ok или bench_read_miss.
	•	Основной main():
	1.	cfg = RedisConfig(); cache = RedisCacheManager(cfg); await cache.connect().
	2.	await cache.load_and_set_audio(key, wav, chunk_ms).
	3.	get_audio_chunks (hit) + лог с latency.
	4.	get_audio_chunks (miss) по фиктивному ключу.
	5.	set_text/get_text + TTL=2с → ждать 2.2с → проверить None.
	6.	Параллельный бенч: asyncio.gather по bench_stream_read * N.
	7.	await cache.close().

Что логируем (минимум)
	•	warmup_done: {key, ok, chunks, sample_rate, nchannels, sampwidth, duration_ms, total_bytes}
	•	get_audio_chunks_hit/miss: {latency_ms, chunks}
	•	bench_read_ok: {first_chunk_ms, stream_ms, total_ms, bytes, chunks}
	•	redis_error: {op, key, error}

Пороговые ориентиры (не фейлим тест)
	•	get_audio_chunks (hit) < 10–20 ms на ключ до ~1000 чанков.
	•	«Первый чанк» логически < 5 ms (чтение уже в памяти).
	•	Полный проход по чанкам — целимся в > 300 MB/s (локально, без sleep).

Быстрый запуск

# 0) Поднять Redis (локально/compose)
export REDIS_HOST=127.0.0.1 REDIS_PORT=6379 REDIS_DB=0

# 1) Подложить WAV
cp test_data/example.wav cache/test/test_data/example.wav

# 2) Запуск
python cache/test/manual_test_cache.py


⸻

Готово. Если хочешь — next шаг: накину «каркас» кода под каждый из трёх файлов (с пустыми методами и логгером), чтобы генерация заняла секунды.