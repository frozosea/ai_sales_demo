import asyncio
import argparse
import yaml
import os
import json
import time
import statistics
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Optional
from llm.manager import ConversationManager
from domain.interfaces.cache import AbstractCache
import copy

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.probe")

def jlog(data: dict):
    logger.info(json.dumps(data))

class MockCache(AbstractCache):
    _data = {}
    async def get(self, key: str): return self._data.get(key)
    async def set(self, key: str, value: str, ttl: int): self._data[key] = value
    async def delete(self, key: str): self._data.pop(key, None)
    async def connect(self) -> None: return None 
    async def disconnect(self): pass
    async def load_and_set_audio(self, key: str, wav_filepath: str, chunk_size_ms: int = 20) -> bool: return True
    async def set_audio_chunks(self, key: str, audio_chunks: List[bytes]) -> bool: return True
    async def get_audio_chunks(self, key: str) -> Optional[List[bytes]]: return None
    async def set_text(self, key: str, text: str, ttl_seconds: int) -> bool: return True
    async def get_text(self, key: str) -> Optional[str]: return None
    async def close(self) -> None: return None


def generate_report(metrics: list[dict], report_dir: Path, model: str, text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    report_path = report_dir / f"llm_probe_{timestamp}.md"
    
    # Calculate statistics
    ttfts = [m['ttft_ms'] for m in metrics if 'ttft_ms' in m]
    totals = [m['total_ms'] for m in metrics if 'total_ms' in m]
    chunk_rates = [m['chunks'] / (m['total_ms'] / 1000) for m in metrics if 'total_ms' in m and m['total_ms'] > 0]
    network_latencies = [m['network_latency_ms'] for m in metrics if m.get('network_latency_ms') is not None]
    inference_ttfts = [m['inference_ttft_ms'] for m in metrics if m.get('inference_ttft_ms') is not None]
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# LLM Performance Probe Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model:** {model}\n")
        f.write(f"**Test prompt:** `{text}`\n\n")
        
        f.write("## Performance Metrics\n\n")
        f.write("| Metric | Average | P50 | P95 |\n")
        f.write("|:---|---:|---:|---:|\n")
        if ttfts:
            f.write(f"| Time to First Token (ms) | {statistics.mean(ttfts):.1f} | {statistics.median(ttfts):.1f} | {statistics.quantiles(ttfts, n=20)[-1]:.1f} |\n")
        if network_latencies:
            f.write(f"|  - Network Latency (ms) | {statistics.mean(network_latencies):.1f} | {statistics.median(network_latencies):.1f} | {statistics.quantiles(network_latencies, n=20)[-1]:.1f} |\n")
        if inference_ttfts:
            f.write(f"|  - Inference TTFT (ms) | {statistics.mean(inference_ttfts):.1f} | {statistics.median(inference_ttfts):.1f} | {statistics.quantiles(inference_ttfts, n=20)[-1]:.1f} |\n")
        if totals:
            f.write(f"| Total Response Time (ms) | {statistics.mean(totals):.1f} | {statistics.median(totals):.1f} | {statistics.quantiles(totals, n=20)[-1]:.1f} |\n")
        if chunk_rates:
            f.write(f"| Chunk Rate (chunks/sec) | {statistics.mean(chunk_rates):.1f} | {statistics.median(chunk_rates):.1f} | {statistics.quantiles(chunk_rates, n=20)[-1]:.1f} |\n\n")
        
        f.write("## Context Usage\n\n")
        f.write("| Turn | Before | After |\n")
        f.write("|:---|---:|---:|\n")
        for i, m in enumerate(metrics, 1):
            f.write(f"| {i} | {m['context_before']:.2%} | {m['context_after']:.2%} |\n")
        
        if any('warmup_ms' in m for m in metrics):
            f.write("\n## Dual-Context Events\n\n")
            f.write("| Turn | Warmup Time (ms) | Time to Handover (ms) |\n")
            f.write("|:---|---:|---:|\n")
            for i, m in enumerate(metrics, 1):
                warmup = f"{m.get('warmup_ms', '-'):.1f}" if 'warmup_ms' in m else "-"
                handover = f"{m.get('handover_ms', '-'):.1f}" if 'handover_ms' in m else "-"
                f.write(f"| {i} | {warmup} | {handover} |\n")
    
    jlog({"event": "report_saved", "path": str(report_path)})
    return report_path

async def run_probe(manager: ConversationManager, text: str, low_latency_mode: bool) -> dict:
    metrics = {}
    
    # Get initial context usage
    metrics['context_before'] = manager.dual_ctx.active_context.estimate_usage_ratio()
    
    t_start = time.monotonic()
    jlog({"event": "request_send", "model": "main", "ts": time.time()})
    
    first_token_time = None
    chunk_count = 0
    
    try:
        async for chunk in manager.process_user_turn(text, low_latency_mode):
            if first_token_time is None and chunk.text_chunk:
                first_token_time = time.monotonic()
                ttft = (first_token_time - t_start) * 1000
                metrics['ttft_ms'] = ttft
                metrics['network_latency_ms'] = chunk.network_latency_ms
                metrics['inference_ttft_ms'] = chunk.inference_ttft_ms
                jlog({
                    "event": "first_token", 
                    "ttft_ms": ttft, 
                    "network_latency_ms": chunk.network_latency_ms,
                    "inference_ttft_ms": chunk.inference_ttft_ms
                })
            
            if not chunk.is_final_chunk and chunk.text_chunk:
                chunk_count += 1
                jlog({"event": "chunk", "i": chunk_count, "bytes": len(chunk.text_chunk)})
    except Exception as e:
        jlog({"event": "probe_error", "error": str(e), "error_type": type(e).__name__})
    finally:
        t_end = time.monotonic()
        total_ms = (t_end - t_start) * 1000
        metrics['total_ms'] = total_ms
        metrics['chunks'] = chunk_count
        # Set default values for metrics that might be missing due to errors
        if 'ttft_ms' not in metrics:
            metrics['ttft_ms'] = total_ms  # Use total time as TTFT if no tokens received
            metrics['network_latency_ms'] = None
            metrics['inference_ttft_ms'] = None
        
        # Get final context usage
        metrics['context_after'] = manager.dual_ctx.active_context.estimate_usage_ratio()
        
        jlog({
            "event": "stream_end",
            "total_ms": total_ms,
            "chunks": chunk_count,
            "context_usage": {
                "before": metrics['context_before'],
                "after": metrics['context_after']
            }
        })
    
    return metrics

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--prompts", type=str, required=True)
    parser.add_argument("--text", type=str, required=True)
    parser.add_argument("--model", type=str, default="main", help="Model to use (e.g., main, summarization)")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--report-dir", type=str, default="reports")
    parser.add_argument("--api-key", type=str, help="OpenAI API key")
    parser.add_argument("--endpoint", type=str, default="https://api.openai.com/v1", help="API endpoint")
    parser.add_argument("--low-latency", action="store_true", help="Enable low latency mode")
    args = parser.parse_args()

    load_dotenv()
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        jlog({"event": "error", "message": "OPENAI_API_KEY not found in environment"})
        return 1

    # Clean up API key
    api_key = api_key.strip()  # Remove any whitespace
    if not api_key.startswith("sk-"):
        jlog({"event": "error", "message": "Invalid API key format: must start with 'sk-'"})
        return 1

    # Log API key info (safely)
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    jlog({
        "event": "api_key_loaded",
        "length": len(api_key),
        "prefix": api_key[:8],
        "suffix": api_key[-4:],
        "env_vars": {k: '***' for k in os.environ if 'API' in k or 'KEY' in k or 'TOKEN' in k}
    })

    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        with open(args.prompts, 'r') as f:
            prompts = yaml.safe_load(f)
    except Exception as e:
        jlog({"event": "error", "message": f"Failed to load configs: {str(e)}"})
        return 1

    # Ensure report directory exists
    report_dir = Path(args.report_dir)
    report_dir.mkdir(exist_ok=True)

    # Create a deep copy of config to avoid modifying the original
    config = copy.deepcopy(config)
    
    # Replace config values and log them
    config['llm']['api_key'] = api_key
    if args.model in config['llm']['models']:
        config['llm']['models']['main'] = config['llm']['models'][args.model]
    
    # Log config (safely)
    debug_config = copy.deepcopy(config)
    if 'api_key' in debug_config.get('llm', {}):
        debug_config['llm']['api_key'] = masked_key
    jlog({"event": "config_loaded", "config": debug_config})

    cache = MockCache()
    
    all_metrics = []
    try:
        # Initialize manager once
        manager = ConversationManager(config, prompts, cache, "probe-session")
        await manager.initialize()
        for i in range(args.repeats):
            print(f"\n--- Run {i+1}/{args.repeats} ---")
            try:
                metrics = await run_probe(manager, args.text, args.low_latency)
                all_metrics.append(metrics)
                
                # Print progress metrics
                print(f"TTFT: {metrics['ttft_ms']:.1f}ms")
                print(f"Total: {metrics['total_ms']:.1f}ms")
                print(f"Chunks: {metrics['chunks']}")
                
                if i < args.repeats - 1:
                    await asyncio.sleep(1)  # Brief pause between runs
            except Exception as e:
                jlog({"event": "iteration_error", "run": i + 1, "error": str(e), "error_type": type(e).__name__})
                print(f"Error in run {i + 1}: {str(e)}")
                continue
    finally:
        if 'manager' in locals() and manager:
            await manager.shutdown()
    
    if all_metrics:
        report_path = generate_report(all_metrics, report_dir, args.model, args.text)
        print(f"\nReport saved to: {report_path}")
        return 0
    else:
        print("\nNo successful runs to generate report.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 