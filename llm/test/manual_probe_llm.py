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

from llm.manager import ConversationManager
from domain.interfaces.cache import AbstractCache

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
    async def disconnect(self): pass

def generate_report(metrics: list[dict], report_dir: Path, model: str, text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    report_path = report_dir / f"llm_probe_{timestamp}.md"
    
    # Calculate statistics
    ttfts = [m['ttft_ms'] for m in metrics]
    totals = [m['total_ms'] for m in metrics]
    chunk_rates = [m['chunks'] / (m['total_ms'] / 1000) for m in metrics]
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# LLM Performance Probe Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model:** {model}\n")
        f.write(f"**Test prompt:** `{text}`\n\n")
        
        f.write("## Performance Metrics\n\n")
        f.write("| Metric | Average | P50 | P95 |\n")
        f.write("|:---|---:|---:|---:|\n")
        f.write(f"| Time to First Token (ms) | {statistics.mean(ttfts):.1f} | {statistics.median(ttfts):.1f} | {statistics.quantiles(ttfts, n=20)[-1]:.1f} |\n")
        f.write(f"| Total Response Time (ms) | {statistics.mean(totals):.1f} | {statistics.median(totals):.1f} | {statistics.quantiles(totals, n=20)[-1]:.1f} |\n")
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

async def run_probe(manager: ConversationManager, text: str) -> dict:
    metrics = {}
    
    # Get initial context usage
    metrics['context_before'] = manager.dual_ctx.active_context.estimate_usage_ratio()
    
    t_start = time.monotonic()
    jlog({"event": "request_send", "model": "main", "ts": time.time()})
    
    first_token_time = None
    chunk_count = 0
    
    async for chunk in manager.process_user_turn(text):
        if first_token_time is None and chunk.text_chunk:
            first_token_time = time.monotonic()
            ttft = (first_token_time - t_start) * 1000
            metrics['ttft_ms'] = ttft
            jlog({"event": "first_token", "ttft_ms": ttft})
        
        if not chunk.is_final_chunk and chunk.text_chunk:
            chunk_count += 1
            jlog({"event": "chunk", "i": chunk_count, "bytes": len(chunk.text_chunk)})
    
    t_end = time.monotonic()
    total_ms = (t_end - t_start) * 1000
    metrics['total_ms'] = total_ms
    metrics['chunks'] = chunk_count
    
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
    parser.add_argument("--model", type=str, default="main")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--report-dir", type=str, default="reports")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        jlog({"event": "error", "message": "OPENAI_API_KEY not found in environment"})
        return 1

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

    # Replace config values
    config['llm']['api_key'] = api_key
    if args.model in config['llm']['models']:
        config['llm']['models']['main'] = config['llm']['models'][args.model]

    cache = MockCache()
    manager = ConversationManager(config, prompts, cache, "probe-session")
    
    all_metrics = []
    try:
        for i in range(args.repeats):
            print(f"\n--- Run {i+1}/{args.repeats} ---")
            metrics = await run_probe(manager, args.text)
            all_metrics.append(metrics)
            
            # Print progress metrics
            print(f"TTFT: {metrics['ttft_ms']:.1f}ms")
            print(f"Total: {metrics['total_ms']:.1f}ms")
            print(f"Chunks: {metrics['chunks']}")
            
            if i < args.repeats - 1:
                await asyncio.sleep(1)  # Brief pause between runs
    finally:
        await manager.shutdown()
    
    # Generate and save report
    report_path = generate_report(all_metrics, report_dir, args.model, args.text)
    print(f"\nReport saved to: {report_path}")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 