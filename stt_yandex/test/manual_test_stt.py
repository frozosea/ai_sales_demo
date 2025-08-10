
import sys
import os

# Add project root to path for absolute imports from 'domain'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
# Add third_party to path for gRPC imports
sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), 'third_party'))


import argparse
import asyncio
import json
import logging
import statistics
import time
import wave
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, List, Tuple
import io

import yaml
from dotenv import load_dotenv

# Explicitly unset proxy environment variables to avoid gRPC warnings/errors
for proxy_var in ["http_proxy", "https_proxy", "all_proxy", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"]:
    if proxy_var in os.environ:
        del os.environ[proxy_var]
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "false"
os.environ["GRPC_SOCKS_PROXY_ADDRESS"] = ""

from domain.stt_models import STTConfig
from stt_yandex.stt_yandex import YandexSTTStreamer


# --- Data Structures for Metrics ---
@dataclass
class RunMetrics:
    # Connection metrics
    handshake_ms: float = 0
    
    # Recognition timing
    first_chunk_sent_ts: float | None = None  # Monotonic timestamp when first chunk was sent
    first_partial_ts: float | None = None     # Monotonic timestamp when first partial was received
    first_final_ts: float | None = None       # Monotonic timestamp when first final was received
    
    # Derived timing metrics
    ttfp_ms: float | None = None  # Time to first partial from first chunk
    ttff_ms: float | None = None  # Time to first final from first chunk
    total_ms: float = 0
    
    # Buffering metrics
    buffer_ms: int = 0
    buffer_size: int = 0
    
    # Performance metrics
    bytes_sent: int = 0
    chunks_sent: int = 0
    partials_count: int = 0
    finals_count: int = 0
    queue_max_depth: int = 0


# --- Logging Setup ---
def jlog(level: int, event: str, **kwargs: Any) -> None:
    log_data = {"event": event, "ts": time.time()}
    log_data.update(kwargs)
    logging.log(level, json.dumps(log_data, ensure_ascii=False))


class LogRecordHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        if isinstance(record.msg, dict):
            self.records.append(record.msg)

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log_handler = LogRecordHandler()
    log_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(log_handler)
    return log_handler


# --- WAV Producer with buffering ---
async def produce_wav_chunks(
    audio_queue: asyncio.Queue[bytes | None], first_chunk_ts_queue: asyncio.Queue[float], wav_path: str, chunk_ms: int, buffer_ms: int = 200
) -> dict:
    try:
        with wave.open(wav_path, "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            
            wav_info = {
                "sr": framerate,
                "nch": nchannels,
                "sampwidth": sampwidth,
                "duration_ms": (nframes / framerate) * 1000,
            }
            
            # Calculate frames for initial buffer
            frames_per_chunk = int(framerate * chunk_ms / 1000)
            frames_per_buffer = int(framerate * buffer_ms / 1000)
            
            # Read initial buffer
            buffer = []
            buffer_size = 0
            while buffer_size < frames_per_buffer:
                frames = wf.readframes(frames_per_chunk)
                if not frames:
                    break
                buffer.append(frames)
                buffer_size += len(frames) // (sampwidth * nchannels)
            
            # Send initial buffer as one chunk
            if buffer:
                initial_chunk = b''.join(buffer)
                ts_mono = time.monotonic()
                jlog(logging.INFO, "PRODUCER_FIRST_CHUNK_READ", 
                     ts_mono=ts_mono,
                     is_buffered=True,
                     buffer_ms=buffer_ms,
                     chunk_size=len(initial_chunk))
                await first_chunk_ts_queue.put((ts_mono, buffer_ms, len(initial_chunk)))
                await audio_queue.put(initial_chunk)
            
            # Stream remaining chunks
            total_bytes = len(initial_chunk) if buffer else 0
            chunk_count = 1 if buffer else 0
            
            while True:
                frames = wf.readframes(frames_per_chunk)
                if not frames:
                    break
                if chunk_count == 0:  # Should not happen with buffering
                    ts_mono = time.monotonic()
                    jlog(logging.INFO, "PRODUCER_FIRST_CHUNK_READ", ts_mono=ts_mono)
                    await first_chunk_ts_queue.put((ts_mono, 0, len(frames)))
                await audio_queue.put(frames)
                total_bytes += len(frames)
                chunk_count += 1
            
            await audio_queue.put(None)  # Signal end of stream
            
            wav_info.update({
                "chunks": chunk_count,
                "total_bytes": total_bytes,
                "buffer_ms": buffer_ms if buffer else 0
            })
            return wav_info
            
    except Exception as e:
        jlog(logging.CRITICAL, "audio_read_error", file=wav_path, error=str(e))
        await audio_queue.put(None)
        return {}


# --- Main Test Runner ---
async def run_test_iteration(
    stt_config: STTConfig, iam_token: str, folder_id: str, wav_path: str, chunk_ms: int, log_handler: LogRecordHandler
) -> RunMetrics:
    metrics = RunMetrics()
    audio_queue = asyncio.Queue(maxsize=100)
    first_chunk_ts_queue = asyncio.Queue()
    
    streamer = YandexSTTStreamer(stt_config, iam_token, folder_id)
    
    # Get warmed-up connection
    t_start = time.monotonic()
    jlog(logging.DEBUG, "stt_handshake_start")
    response_queue = await streamer.start_recognition(audio_queue)
    metrics.handshake_ms = (time.monotonic() - t_start) * 1000
    jlog(logging.INFO, "stt_handshake_finish", ms=round(metrics.handshake_ms, 2))
    
    # Start audio producer with buffering
    producer_task = asyncio.create_task(produce_wav_chunks(audio_queue, first_chunk_ts_queue, wav_path, chunk_ms, buffer_ms=200))
    
    # Wait for first chunk timestamp
    try:
        ts_mono, buffer_ms, chunk_size = await asyncio.wait_for(first_chunk_ts_queue.get(), timeout=5.0)
        metrics.first_chunk_sent_ts = ts_mono
        metrics.buffer_ms = buffer_ms
        metrics.buffer_size = chunk_size
        jlog(logging.DEBUG, "got_first_chunk_ts", ts_mono=ts_mono)
    except asyncio.TimeoutError:
        jlog(logging.ERROR, "timeout_waiting_for_first_chunk")
    
    try:
        producer_done = False
        last_response_time = time.monotonic()
        
        while True:
            result, err = await response_queue.get()
            
            if result is None and err is None:
                break
            
            metrics.queue_max_depth = max(metrics.queue_max_depth, audio_queue.qsize())
            
            if err:
                jlog(logging.ERROR, "stt_grpc_error", error=str(err))
                break
            
            if result:
                current_time = time.monotonic()
                last_response_time = current_time
                
                if result.text:
                    # Calculate latency from first chunk
                    latency_from_chunk = (
                        round((current_time - metrics.first_chunk_sent_ts) * 1000, 2)
                        if metrics.first_chunk_sent_ts is not None
                        else None
                    )
                    
                    jlog(logging.INFO, "stt_response_received", 
                         text=result.text,
                         is_final=result.is_final,
                         latency_from_chunk_ms=latency_from_chunk)
                    
                    if not result.is_final:
                        metrics.partials_count += 1
                        if metrics.first_partial_ts is None:
                            metrics.first_partial_ts = current_time
                            metrics.ttfp_ms = latency_from_chunk
                            jlog(logging.INFO, "RECEIVER_FIRST_PARTIAL_RECEIVED", 
                                 ts_mono=current_time,
                                 text=result.text,
                                 latency_from_chunk_ms=latency_from_chunk)
                    else:
                        metrics.finals_count += 1
                        if metrics.first_final_ts is None:
                            metrics.first_final_ts = current_time
                            metrics.ttff_ms = latency_from_chunk
                            jlog(logging.INFO, "RECEIVER_FIRST_FINAL_RECEIVED",
                                 ts_mono=current_time,
                                 text=result.text,
                                 latency_from_chunk_ms=latency_from_chunk)
            
            # Check if producer is done
            if not producer_done and producer_task.done():
                producer_done = True
            
            # Check if we should finish
            if producer_done:
                # Wait for more responses
                if response_queue.qsize() == 0:
                    # No more responses in queue, check if we should wait more
                    if time.monotonic() - last_response_time > 1.0:  # Wait up to 1 second for more responses
                        break
                    await asyncio.sleep(0.1)  # Small delay to avoid busy loop
    
    finally:
        # Get producer info first
        wav_info = await producer_task
        metrics.bytes_sent = wav_info.get("total_bytes", 0)
        metrics.chunks_sent = wav_info.get("chunks", 0)
        metrics.buffer_ms = wav_info.get("buffer_ms", 0)
        
        # Calculate total time from first chunk to last response
        if metrics.first_chunk_sent_ts is not None:
            metrics.total_ms = round((time.monotonic() - metrics.first_chunk_sent_ts) * 1000, 2)
        
        jlog(logging.INFO, "stream_end", 
             total_ms=metrics.total_ms,
             ttfp_ms=metrics.ttfp_ms,
             ttff_ms=metrics.ttff_ms,
             buffer_ms=metrics.buffer_ms,
             buffer_size=metrics.buffer_size,
             partials=metrics.partials_count,
             finals=metrics.finals_count,
             max_queue_depth=metrics.queue_max_depth)
        
        await streamer.stop_recognition()
    
    return metrics

# --- Report Generation ---
def calculate_percentage(value: float, total: float) -> float:
    """Calculate percentage with zero check."""
    return round(value / total * 100, 1) if total > 0 else 0.0

@dataclass
class BatchMetrics:
    avg_handshake_ms: float
    avg_ttfp_ms: float
    avg_ttff_ms: float
    p50_handshake_ms: float
    p50_ttfp_ms: float
    p50_ttff_ms: float
    p95_handshake_ms: float
    p95_ttfp_ms: float
    p95_ttff_ms: float

def analyze_batch(results: List[RunMetrics]) -> BatchMetrics:
    """Analyze metrics for a batch of test runs."""
    def get_stats(metric_name: str) -> tuple[float, float, float]:
        values = [getattr(r, metric_name) for r in results if getattr(r, metric_name) is not None]
        if not values:
            return 0.0, 0.0, 0.0
        return (
            statistics.mean(values),
            statistics.median(values),
            sorted(values)[int(len(values) * 0.95)] if len(values) > 1 else values[0]
        )
    
    handshake_avg, handshake_p50, handshake_p95 = get_stats("handshake_ms")
    ttfp_avg, ttfp_p50, ttfp_p95 = get_stats("ttfp_ms")
    ttff_avg, ttff_p50, ttff_p95 = get_stats("ttff_ms")
    
    return BatchMetrics(
        avg_handshake_ms=round(handshake_avg, 2),
        avg_ttfp_ms=round(ttfp_avg, 2),
        avg_ttff_ms=round(ttff_avg, 2),
        p50_handshake_ms=round(handshake_p50, 2),
        p50_ttfp_ms=round(ttfp_p50, 2),
        p50_ttff_ms=round(ttff_p50, 2),
        p95_handshake_ms=round(handshake_p95, 2),
        p95_ttfp_ms=round(ttfp_p95, 2),
        p95_ttff_ms=round(ttff_p95, 2)
    )

def generate_comparison_report(
    batch1_metrics: BatchMetrics,
    batch2_metrics: BatchMetrics,
    idle_time: int,
    report_dir: Path,
    timestamp: str
):
    """Generate a report comparing performance before and after idle period."""
    def calc_degradation(before: float, after: float) -> tuple[float, str]:
        if before == 0:
            return 0.0, "N/A"
        pct = ((after - before) / before) * 100
        return pct, f"{'+' if pct >= 0 else ''}{pct:.1f}%"
    
    # Calculate degradation percentages
    handshake_deg, handshake_pct = calc_degradation(batch1_metrics.avg_handshake_ms, batch2_metrics.avg_handshake_ms)
    ttfp_deg, ttfp_pct = calc_degradation(batch1_metrics.avg_ttfp_ms, batch2_metrics.avg_ttfp_ms)
    ttff_deg, ttff_pct = calc_degradation(batch1_metrics.avg_ttff_ms, batch2_metrics.avg_ttff_ms)
    
    # Determine status
    def get_status(degradation: float) -> str:
        if degradation <= 10:
            return "✅ Good"
        elif degradation <= 25:
            return "⚠️ Warning"
        else:
            return "❌ Critical"
    
    comparison_path = report_dir / f"stt_probe_{timestamp}_comparison.md"
    
    md_content = f"""# STT Performance Degradation Analysis

**Idle Period:** {idle_time} seconds

## Performance Impact Summary

| Metric | Before | After | Change | Status |
|--------|---------|--------|---------|---------|
| Handshake (avg) | {batch1_metrics.avg_handshake_ms:.1f} ms | {batch2_metrics.avg_handshake_ms:.1f} ms | {handshake_pct} | {get_status(handshake_deg)} |
| TTFP (avg) | {batch1_metrics.avg_ttfp_ms:.1f} ms | {batch2_metrics.avg_ttfp_ms:.1f} ms | {ttfp_pct} | {get_status(ttfp_deg)} |
| TTFF (avg) | {batch1_metrics.avg_ttff_ms:.1f} ms | {batch2_metrics.avg_ttff_ms:.1f} ms | {ttff_pct} | {get_status(ttff_deg)} |

## Detailed Metrics

### Before Idle Period

| Metric | Average | p50 | p95 |
|--------|---------|-----|-----|
| Handshake | {batch1_metrics.avg_handshake_ms:.1f} ms | {batch1_metrics.p50_handshake_ms:.1f} ms | {batch1_metrics.p95_handshake_ms:.1f} ms |
| TTFP | {batch1_metrics.avg_ttfp_ms:.1f} ms | {batch1_metrics.p50_ttfp_ms:.1f} ms | {batch1_metrics.p95_ttfp_ms:.1f} ms |
| TTFF | {batch1_metrics.avg_ttff_ms:.1f} ms | {batch1_metrics.p50_ttff_ms:.1f} ms | {batch1_metrics.p95_ttff_ms:.1f} ms |

### After Idle Period

| Metric | Average | p50 | p95 |
|--------|---------|-----|-----|
| Handshake | {batch2_metrics.avg_handshake_ms:.1f} ms | {batch2_metrics.p50_handshake_ms:.1f} ms | {batch2_metrics.p95_handshake_ms:.1f} ms |
| TTFP | {batch2_metrics.avg_ttfp_ms:.1f} ms | {batch2_metrics.p50_ttfp_ms:.1f} ms | {batch2_metrics.p95_ttfp_ms:.1f} ms |
| TTFF | {batch2_metrics.avg_ttff_ms:.1f} ms | {batch2_metrics.p50_ttff_ms:.1f} ms | {batch2_metrics.p95_ttff_ms:.1f} ms |

## Analysis

1. **Handshake Impact:**
   - Average degradation: {handshake_pct}
   - Status: {get_status(handshake_deg)}
   - {
    "No significant impact on connection setup time." if handshake_deg <= 10
    else "Notable increase in connection setup time." if handshake_deg <= 25
    else "Severe degradation in connection setup performance."
   }

2. **First Partial Recognition (TTFP):**
   - Average degradation: {ttfp_pct}
   - Status: {get_status(ttfp_deg)}
   - {
    "Model maintains good responsiveness after idle period." if ttfp_deg <= 10
    else "Some degradation in initial recognition speed." if ttfp_deg <= 25
    else "Significant delay in initial recognition after idle period."
   }

3. **First Final Recognition (TTFF):**
   - Average degradation: {ttff_pct}
   - Status: {get_status(ttff_deg)}
   - {
    "Final recognition timing remains stable." if ttff_deg <= 10
    else "Moderate impact on final recognition timing." if ttff_deg <= 25
    else "Major slowdown in producing final recognition results."
   }

## Recommendations

{
    "✅ Current connection management strategy is effective for the given idle period." if max(handshake_deg, ttfp_deg, ttff_deg) <= 10
    else "⚠️ Consider adjusting connection warmup frequency or strategy." if max(handshake_deg, ttfp_deg, ttff_deg) <= 25
    else "❌ Connection management strategy needs revision for better handling of long idle periods."
}

"""
    
    with open(comparison_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    jlog(logging.INFO, "comparison_report_saved", path=str(comparison_path))

async def main():
    log_handler = setup_logging()

    parser = argparse.ArgumentParser(description="Manual integration test for Yandex STT.")
    parser.add_argument("--wav", type=str, required=True, help="Path to the WAV file.")
    parser.add_argument("--chunk-ms", type=int, default=5, help="Chunk size in milliseconds.")
    parser.add_argument("--repeats", type=int, default=1, help="Number of test repetitions.")
    parser.add_argument("--report-dir", type=str, default="reports", help="Directory to save reports.")
    parser.add_argument("--config", type=str, required=True, help="Path to STT config YAML.")
    parser.add_argument("--idle-time", type=int, default=30, help="Time to wait between test batches (seconds).")
    args = parser.parse_args()

    load_dotenv()
    iam_token = os.getenv("YC_IAM_TOKEN")
    folder_id = os.getenv("YC_FOLDER_ID")

    if not iam_token or not folder_id:
        jlog(logging.CRITICAL, "auth_creds_missing", details="YC_IAM_TOKEN or YC_FOLDER_ID is not set.")
        return

    with open(args.config, "r") as f:
        stt_config_data = yaml.safe_load(f)
    stt_config = STTConfig(**stt_config_data)
    
    # Initialize pool with custom warmup interval
    YandexSTTStreamer.initialize_pool(
        stt_config,
        iam_token,
        folder_id,
        warmup_interval_sec=5.0,
        max_connections=2
    )

    # First batch of tests
    jlog(logging.INFO, "starting_first_batch")
    first_batch_results = []
    try:
        for i in range(args.repeats):
            jlog(logging.INFO, "test_iteration_start", run=i + 1, total=args.repeats, batch=1)
            result = await run_test_iteration(stt_config, iam_token, folder_id, args.wav, args.chunk_ms, log_handler)
            first_batch_results.append(result)

        # Analyze first batch
        batch1_metrics = analyze_batch(first_batch_results)
        jlog(logging.INFO, "first_batch_analysis",
             avg_handshake_ms=batch1_metrics.avg_handshake_ms,
             avg_ttfp_ms=batch1_metrics.avg_ttfp_ms,
             avg_ttff_ms=batch1_metrics.avg_ttff_ms)

        # Wait for connections to potentially expire
        jlog(logging.INFO, "waiting_for_idle", seconds=args.idle_time)
        await asyncio.sleep(args.idle_time)
        
        # Second batch to verify warm connections
        jlog(logging.INFO, "starting_second_batch")
        second_batch_results = []
        for i in range(args.repeats):
            jlog(logging.INFO, "test_iteration_start", run=i + 1, total=args.repeats, batch=2)
            result = await run_test_iteration(stt_config, iam_token, folder_id, args.wav, args.chunk_ms, log_handler)
            second_batch_results.append(result)

        # Analyze second batch
        batch2_metrics = analyze_batch(second_batch_results)
        jlog(logging.INFO, "second_batch_analysis",
             avg_handshake_ms=batch2_metrics.avg_handshake_ms,
             avg_ttfp_ms=batch2_metrics.avg_ttfp_ms,
             avg_ttff_ms=batch2_metrics.avg_ttff_ms)

        # Get wav_info for the report
        with wave.open(args.wav, "rb") as wf:
            wav_info = {
                "sr": wf.getframerate(),
                "nch": wf.getnchannels(),
                "sampwidth": wf.getsampwidth(),
            }
        
        # Generate standard reports for both batches
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        jlog(logging.INFO, "generating_first_batch_report")
        generate_report(first_batch_results, Path(args.report_dir), wav_info, args, suffix="batch1")
        
        jlog(logging.INFO, "generating_second_batch_report")
        generate_report(second_batch_results, Path(args.report_dir), wav_info, args, suffix="batch2")
        
        # Generate comparison report
        jlog(logging.INFO, "generating_comparison_report")
        generate_comparison_report(
            batch1_metrics,
            batch2_metrics,
            args.idle_time,
            Path(args.report_dir),
            timestamp
        )
    
    finally:
        # Close connection pool
        await YandexSTTStreamer.close_pool()

def generate_report(results: List[RunMetrics], report_dir: Path, wav_info: dict, args: argparse.Namespace, suffix: str = ""):
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    base_path = report_dir / f"stt_probe_{timestamp}_{suffix}"
    
    json_path = base_path.with_suffix(".json")
    md_path = base_path.with_suffix(".md")

    def get_stats(metric_name: str) -> dict:
        values = [getattr(r, metric_name) for r in results if getattr(r, metric_name) is not None]
        if not values:
            return {"avg": 0, "p50": 0, "p95": 0}
        return {
            "avg": round(statistics.mean(values), 2),
            "p50": round(statistics.median(values), 2),
            "p95": round(sorted(values)[int(len(values) * 0.95)] if len(values) > 1 else values[0], 2)
        }

    summary = {
        "params": vars(args),
        "wav_info": wav_info,
        "metrics": {
            "handshake_ms": get_stats("handshake_ms"),
            "ttfp_ms": get_stats("ttfp_ms"),
            "ttff_ms": get_stats("ttff_ms"),
            "total_ms": get_stats("total_ms"),
            "buffer_ms": get_stats("buffer_ms"),
            "buffer_size": get_stats("buffer_size"),
            "bytes_sent": get_stats("bytes_sent"),
            "chunks_sent": get_stats("chunks_sent"),
            "queue_max_depth": get_stats("queue_max_depth"),
        },
        "runs": [asdict(r) for r in results]
    }

    # Save JSON report
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Save Markdown report
    ttfp_p50 = summary["metrics"]["ttfp_ms"]["p50"]
    ttfp_goal = 800
    ttfp_status = "✅ OK" if ttfp_p50 < ttfp_goal else "❌ FAIL"

    md_content = f"""# STT Performance Test Report - {suffix}

**Timestamp:** `{timestamp}`
**Target:** TTFP p50 < {ttfp_goal} ms

## Summary
- **WAV File:** `{args.wav}` (`{wav_info.get('sr')} Hz, {wav_info.get('nch')} ch, {wav_info.get('sampwidth')*8}-bit`)
- **Chunk Size:** `{args.chunk_ms} ms`
- **Buffer Size:** `{summary['metrics']['buffer_ms']['avg']} ms`
- **Runs:** `{args.repeats}`
- **TTFP p50:** `{ttfp_p50} ms` ({ttfp_status})
- **Data Sent:** `{round(summary['metrics']['bytes_sent']['avg'] / 1024, 2)} KB`
- **Total Chunks:** `{summary['metrics']['chunks_sent']['avg']}`

## Key Metrics (ms)
| Metric | Average | p50 (Median) | p95 |
|--------|---------|--------------|-----|
| Handshake | {summary['metrics']['handshake_ms']['avg']} | {summary['metrics']['handshake_ms']['p50']} | {summary['metrics']['handshake_ms']['p95']} |
| **TTFP (First Partial)** | **{summary['metrics']['ttfp_ms']['avg']}** | **{summary['metrics']['ttfp_ms']['p50']}** | **{summary['metrics']['ttfp_ms']['p95']}** |
| TTFF (First Final) | {summary['metrics']['ttff_ms']['avg']} | {summary['metrics']['ttff_ms']['p50']} | {summary['metrics']['ttff_ms']['p95']} |
| Total Stream Time | {summary['metrics']['total_ms']['avg']} | {summary['metrics']['total_ms']['p50']} | {summary['metrics']['total_ms']['p95']} |

## Buffering Details
- Initial Buffer Size: {summary['metrics']['buffer_ms']['avg']} ms
- First Chunk Size: {round(summary['metrics']['buffer_size']['avg'], 2)} bytes
- Total Chunks: {summary['metrics']['chunks_sent']['avg']}
- Max Queue Depth: {summary['metrics']['queue_max_depth']['avg']}
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    jlog(logging.INFO, "report_saved", path_md=str(md_path), path_json=str(json_path))


if __name__ == "__main__":
    asyncio.run(main())
