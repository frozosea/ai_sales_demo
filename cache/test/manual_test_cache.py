from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import pathlib
import shutil
import time
import wave
from typing import Any, List, Optional


from cache.cache import RedisCacheManager
from infra.redis_config import RedisConfig

# 1. Configure JSON logging
def jlog(level: int, event: str, **kwargs: Any) -> None:
    log_data = {"event": event, "level": logging.getLevelName(level)}
    log_data.update(kwargs)
    logging.log(level, json.dumps(log_data))

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

# 2. Ensure test data exists
def ensure_test_data(source_wav: pathlib.Path, dest_wav: pathlib.Path) -> bool:
    if dest_wav.exists():
        return True
    if not source_wav.exists():
        jlog(logging.ERROR, "test_data_missing", source_file=str(source_wav))
        return False
    
    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_wav, dest_wav)
    jlog(logging.INFO, "test_data_copied", source=str(source_wav), dest=str(dest_wav))
    return True

# 3. Benchmark coroutine
async def bench_stream_read(
    cache: RedisCacheManager, key: str, task_id: int
) -> dict | None:
    t0 = time.monotonic()
    
    chunks = await cache.get_audio_chunks(key)
    
    t_first_chunk = time.monotonic()
    
    if not chunks:
        jlog(logging.WARNING, "bench_read_miss", key=key, task_id=task_id)
        return None

    total_bytes = sum(len(c) for c in chunks)
    
    t_end_stream = time.monotonic()

    first_chunk_ms = (t_first_chunk - t0) * 1000
    total_ms = (t_end_stream - t0) * 1000
    stream_ms = (t_end_stream - t_first_chunk) * 1000

    metrics = {
        "first_chunk_ms": round(first_chunk_ms, 3),
        "stream_ms": round(stream_ms, 3),
        "total_ms": round(total_ms, 3),
        "bytes": total_bytes,
        "chunks": len(chunks),
    }
    jlog(logging.INFO, "bench_read_ok", task_id=task_id, **metrics)
    return metrics

# 4. Main test orchestrator
async def main():
    setup_logging()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default="static:test_example")
    parser.add_argument("--wav", default="cache/test/test_data/example.wav")
    parser.add_argument("--chunk-ms", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    # Ensure test file exists
    source_wav_path = pathlib.Path("test_data/example.wav")
    dest_wav_path = pathlib.Path(args.wav)
    if not ensure_test_data(source_wav_path, dest_wav_path):
        return

    # Connect to cache
    cfg = RedisConfig()
    cache = RedisCacheManager(cfg)
    try:
        await cache.connect()
    except Exception as e:
        jlog(logging.CRITICAL, "redis_connection_failed", error=str(e))
        return

    # === Test 1: Load and Set Audio (Cache Warmup) ===
    jlog(logging.INFO, "test_run_started", test="load_and_set_audio")
    
    try:
        with wave.open(str(dest_wav_path), "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            duration_ms = (nframes / framerate) * 1000
    except Exception as e:
        jlog(logging.ERROR, "wav_read_error", file=args.wav, error=str(e))
        await cache.close()
        return

    ok = await cache.load_and_set_audio(args.key, str(dest_wav_path), args.chunk_ms)
    chunks_loaded = await cache.get_audio_chunks(args.key)
    
    jlog(
        logging.INFO,
        "warmup_done",
        key=args.key,
        ok=ok,
        chunks=len(chunks_loaded or []),
        sample_rate=framerate,
        nchannels=nchannels,
        sampwidth=sampwidth,
        duration_ms=round(duration_ms),
        total_bytes=sum(len(c) for c in (chunks_loaded or [])),
    )

    # === Test 2: Get Audio Chunks (Hit & Miss) ===
    jlog(logging.INFO, "test_run_started", test="get_audio_chunks")
    
    # Hit
    t_start = time.monotonic()
    hit_chunks = await cache.get_audio_chunks(args.key)
    latency_ms = (time.monotonic() - t_start) * 1000
    jlog(logging.INFO, "get_audio_chunks_hit", latency_ms=round(latency_ms, 3), chunks=len(hit_chunks or []))
    
    # Miss
    miss_key = "static:non_existent_key"
    t_start = time.monotonic()
    miss_chunks = await cache.get_audio_chunks(miss_key)
    latency_ms = (time.monotonic() - t_start) * 1000
    jlog(logging.INFO, "get_audio_chunks_miss", latency_ms=round(latency_ms, 3), chunks=len(miss_chunks or []), result=miss_chunks)

    # === Test 3: Set/Get Text with TTL ===
    jlog(logging.INFO, "test_run_started", test="set_get_text_ttl")
    text_key = "summary:session:test_session"
    await cache.set_text(text_key, "Hello, this is a test.", ttl_seconds=2)
    text_val = await cache.get_text(text_key)
    jlog(logging.INFO, "get_text_before_ttl_expiry", key=text_key, value=text_val)
    
    await asyncio.sleep(2.2)
    
    text_val_after_ttl = await cache.get_text(text_key)
    jlog(logging.INFO, "get_text_after_ttl_expiry", key=text_key, value=text_val_after_ttl)
    
    # === Test 4: Parallel Benchmark ===
    jlog(logging.INFO, "test_run_started", test="parallel_benchmark", concurrency=args.concurrency)
    
    tasks = [bench_stream_read(cache, args.key, i) for i in range(args.concurrency)]
    results: List[Optional[dict]] = await asyncio.gather(*tasks)
    
    valid_results = [r for r in results if r]
    if valid_results:
        total_ms_times = [r["total_ms"] for r in valid_results]
        p50 = sorted(total_ms_times)[len(total_ms_times) // 2]
        p95 = sorted(total_ms_times)[int(len(total_ms_times) * 0.95)]
        jlog(logging.INFO, "benchmark_summary", p50_total_ms=p50, p95_total_ms=p95, successful_reads=len(valid_results))

    # Cleanup
    await cache.close()
    jlog(logging.INFO, "test_run_finished")


if __name__ == "__main__":
    asyncio.run(main())
