from __future__ import annotations
import asyncio
import argparse
import yaml
import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import logging

from llm.manager import ConversationManager
from cache.cache import RedisCacheManager
from infra.redis_config import RedisConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.agent")

def jlog(data: dict):
    """Log JSON data with proper encoding for Russian text."""
    class CustomEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return str(obj)
    
    logger.info(json.dumps(data, ensure_ascii=False, cls=CustomEncoder))

def get_session_hash(session_id: str) -> str:
    """Generate a 16-character hash for Redis keys."""
    return hashlib.sha1(session_id.encode()).hexdigest()[:16]

def get_cache_key(session_hash: str) -> str:
    """Generate Redis key for summary cache."""
    return f"summary:session:{session_hash}"

def safe_stats(values: List[float]) -> tuple[float, float, float]:
    """Calculate statistics safely handling empty lists."""
    if not values:
        return 0.0, 0.0, 0.0
    
    values = [v for v in values if v is not None]
    if not values:
        return 0.0, 0.0, 0.0
    
    mean = sum(values) / len(values)
    median = sorted(values)[len(values)//2]
    p95 = sorted(values)[int(len(values)*0.95)]
    return mean, median, p95

def format_float(value: Optional[float], format_spec: str = '.1f') -> str:
    """Safely format float value with fallback to '-' for None."""
    if value is None:
        return '-'
    return f"{value:{format_spec}}"

class TestMetricsCollector:
    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []
        self.raw_events: List[Dict[str, Any]] = []
    
    def add_metric(self, metric: Dict[str, Any]):
        self.metrics.append(metric)
    
    def add_event(self, event: Dict[str, Any]):
        self.raw_events.append(event)
        jlog(event)
    
    def save_reports(self, report_dir: Path, session_id: str) -> tuple[Path, Path]:
        """Generate both MD and JSON reports."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        
        # Save raw JSON data
        json_path = report_dir / f"llm_agent_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "metrics": self.metrics,
                "events": self.raw_events
            }, f, indent=2, ensure_ascii=False)
        
        # Generate MD report
        md_path = report_dir / f"llm_agent_{timestamp}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# LLM Agent E2E Test Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Session ID:** {session_id}\n\n")
            
            # Performance metrics
            f.write("## Performance Metrics\n\n")
            f.write("| Metric | Average | P50 | P95 | Target | Status |\n")
            f.write("|:---|---:|---:|---:|---:|:---:|\n")
            
            # Calculate statistics safely
            ttfts = [m.get('ttft_ms') for m in self.metrics]
            network_latencies = [m.get('network_latency_ms') for m in self.metrics]
            inference_ttfts = [m.get('inference_ttft_ms') for m in self.metrics]
            totals = [m.get('total_ms') for m in self.metrics]
            chunk_rates = [
                m.get('chunks', 0) / (m.get('total_ms', 1000) / 1000)
                for m in self.metrics 
                if m.get('total_ms', 0) > 0 and m.get('chunks', 0) > 0
            ]
            
            ttft_mean, ttft_p50, ttft_p95 = safe_stats(ttfts)
            net_mean, net_p50, net_p95 = safe_stats(network_latencies)
            inf_mean, inf_p50, inf_p95 = safe_stats(inference_ttfts)
            total_mean, total_p50, total_p95 = safe_stats(totals)
            chunk_mean, chunk_p50, chunk_p95 = safe_stats(chunk_rates)
            
            status = "✅" if ttft_p50 < 800 else "❌"
            f.write(f"| TTFT (ms) | {format_float(ttft_mean)} | {format_float(ttft_p50)} | {format_float(ttft_p95)} | 800 | {status} |\n")
            f.write(f"|  - Network Latency | {format_float(net_mean)} | {format_float(net_p50)} | {format_float(net_p95)} | - | - |\n")
            f.write(f"|  - Inference TTFT | {format_float(inf_mean)} | {format_float(inf_p50)} | {format_float(inf_p95)} | - | - |\n")
            f.write(f"| Total Time (ms) | {format_float(total_mean)} | {format_float(total_p50)} | {format_float(total_p95)} | - | - |\n")
            f.write(f"| Chunk Rate (chunks/sec) | {format_float(chunk_mean)} | {format_float(chunk_p50)} | {format_float(chunk_p95)} | - | - |\n")
            
            # Cache performance
            f.write("\n## Cache Performance\n\n")
            cache_hits = sum(1 for m in self.metrics if m.get('cache_hit', False))
            cache_misses = sum(1 for m in self.metrics if 'cache_hit' in m and not m['cache_hit'])
            if cache_hits + cache_misses > 0:
                hit_rate = cache_hits / (cache_hits + cache_misses)
                f.write(f"- Cache Hit Rate: {hit_rate:.1%}\n")
                f.write(f"- Cache Hits: {cache_hits}\n")
                f.write(f"- Cache Misses: {cache_misses}\n")
                if cache_hits > 0:
                    hit_latencies = [m.get('cache_latency_ms') for m in self.metrics if m.get('cache_hit') and m.get('cache_latency_ms') is not None]
                    if hit_latencies:
                        avg_latency = sum(hit_latencies) / len(hit_latencies)
                        f.write(f"- Avg Cache Hit Latency: {format_float(avg_latency)} ms\n")
            
            # Context management
            f.write("\n## Context Management\n\n")
            f.write("| Turn | Context Before | Context After | Warmup | Chunks | Rate |\n")
            f.write("|:---|---:|---:|:---:|---:|---:|\n")
            
            for i, m in enumerate(self.metrics, 1):
                warmup = "✓" if m.get('warmup_started', False) else "-"
                chunks = m.get('chunks', 0)
                rate = chunks / (m.get('total_ms', 1000) / 1000) if m.get('total_ms', 0) > 0 and chunks > 0 else 0
                f.write(f"| {i} | {m.get('context_before', 0):.1%} | {m.get('context_after', 0):.1%} | {warmup} | {chunks} | {rate:.1f}/s |\n")
            
            # Conversation flow
            f.write("\n## Conversation Flow\n\n")
            for i, m in enumerate(self.metrics, 1):
                f.write(f"### Turn {i}\n\n")
                f.write(f"**User:** {m.get('user_text', '')}\n\n")
                f.write(f"**Assistant:** {m.get('assistant_text', '')}\n\n")
                f.write("**Metrics:**\n")
                f.write(f"- TTFT: {format_float(m.get('ttft_ms'))} ms\n")
                f.write(f"  - Network: {format_float(m.get('network_latency_ms'))} ms\n")
                f.write(f"  - Inference: {format_float(m.get('inference_ttft_ms'))} ms\n")
                f.write(f"- Total Time: {format_float(m.get('total_ms'))} ms\n")
                f.write(f"- Chunks: {m.get('chunks', 0)} ({format_float(m.get('chunks', 0) / (m.get('total_ms', 1000) / 1000) if m.get('total_ms', 0) > 0 and m.get('chunks', 0) > 0 else 0)}/s)\n")
                if 'cache_hit' in m:
                    f.write(f"- Cache: {'Hit' if m['cache_hit'] else 'Miss'}")
                    if m.get('cache_latency_ms') is not None:
                        f.write(f" ({format_float(m['cache_latency_ms'])} ms)\n")
                    else:
                        f.write("\n")
                f.write("\n")
        
        return md_path, json_path

async def run_conversation_turn(
    manager: ConversationManager,
    text: str,
    metrics_collector: TestMetricsCollector
) -> None:
    """Run a single conversation turn and collect metrics."""
    metrics = {
        'user_text': text,
        'context_before': manager.dual_ctx.active_context.estimate_usage_ratio()
    }
    
    t_start = time.monotonic()
    metrics_collector.add_event({
        "event": "turn_start",
        "text": text,
        "ts": time.time()
    })
    
    first_token_time = None
    assistant_text = ""
    chunk_count = 0
    
    try:
        async for chunk in manager.process_user_turn(text):
            if first_token_time is None and chunk.text_chunk:
                first_token_time = time.monotonic()
                ttft = (first_token_time - t_start) * 1000
                
                # Capture timing metrics from the first chunk
                metrics.update({
                    'ttft_ms': ttft,
                    'network_latency_ms': chunk.network_latency_ms,
                    'inference_ttft_ms': chunk.inference_ttft_ms
                })
                
                metrics_collector.add_event({
                    "event": "first_token",
                    "ttft_ms": ttft,
                    "network_latency_ms": chunk.network_latency_ms,
                    "inference_ttft_ms": chunk.inference_ttft_ms
                })
            
            if not chunk.is_final_chunk and chunk.text_chunk:
                chunk_count += 1
                assistant_text += chunk.text_chunk
                metrics_collector.add_event({
                    "event": "chunk",
                    "i": chunk_count,
                    "bytes": len(chunk.text_chunk)
                })
    except Exception as e:
        metrics_collector.add_event({
            "event": "turn_error",
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise
    
    t_end = time.monotonic()
    total_ms = (t_end - t_start) * 1000
    
    metrics.update({
        'total_ms': total_ms,
        'chunks': chunk_count,
        'assistant_text': assistant_text,
        'context_after': manager.dual_ctx.active_context.estimate_usage_ratio()
    })
    
    # Set default values for metrics that might be missing due to errors
    if 'ttft_ms' not in metrics:
        metrics['ttft_ms'] = total_ms  # Use total time as TTFT if no tokens received
        metrics['network_latency_ms'] = None
        metrics['inference_ttft_ms'] = None
    
    # Check warmup/handover status
    warmup_started = False
    warmup_time = None
    handover_time = None
    
    # Get warmup status from dual_ctx
    if hasattr(manager.dual_ctx, '_warmup_task'):
        warmup_started = manager.dual_ctx._warmup_task is not None
    if hasattr(manager.dual_ctx, '_warmup_ready_time'):
        warmup_time = manager.dual_ctx._warmup_ready_time
    if hasattr(manager.dual_ctx, '_handover_time'):
        handover_time = manager.dual_ctx._handover_time
    
    metrics.update({
        'warmup_started': warmup_started,
        'warmup_time_ms': (warmup_time - t_start) * 1000 if warmup_time else None,
        'handover_ms': (handover_time - t_start) * 1000 if handover_time else None
    })
    
    metrics_collector.add_metric(metrics)
    metrics_collector.add_event({
        "event": "turn_complete",
        "metrics": metrics
    })

async def run_test_scenario(
    manager: ConversationManager,
    session_hash: str,
    metrics_collector: TestMetricsCollector
):
    """Run the full test scenario with cache checks."""
    # Диалог для тестирования
    conversation = [
        "Привет! Скажи в двух фразах, чем ты полезен клиентам страховой компании?",
        "А теперь в одном предложении объясни выгоды вежливо и без воды.",
        "Суммаризируй весь диалог списком из 3 пунктов."
    ]
    
    print("\n=== Starting Test Scenario ===")
    
    # Основной диалог
    for i, text in enumerate(conversation, 1):
        print(f"\n[Turn {i}] User: {text}")
        print("Assistant: ", end="", flush=True)
        
        await run_conversation_turn(manager, text, metrics_collector)
        print()  # New line after assistant's response
        
        if i < len(conversation):
            await asyncio.sleep(0.5)
    
    # Повторный запрос суммаризации для проверки кэша
    print("\n=== Cache Test: Repeating Summary Request ===")
    await run_conversation_turn(
        manager,
        "Суммаризируй весь диалог списком из 3 пунктов.",
        metrics_collector
    )

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--prompts", type=str, required=True)
    parser.add_argument("--session-id", type=str, required=True)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--report-dir", type=str, default="reports")
    args = parser.parse_args()

    # Load configs and env vars
    load_dotenv()
    
    # Validate OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        jlog({"event": "error", "message": "OPENAI_API_KEY not found"})
        return 1
    
    # Load config files
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        with open(args.prompts, 'r') as f:
            prompts = yaml.safe_load(f)
    except Exception as e:
        jlog({"event": "error", "message": f"Failed to load configs: {str(e)}"})
        return 1

    # Setup directories
    report_dir = Path(args.report_dir)
    report_dir.mkdir(exist_ok=True)

    # Update config with API key
    config['llm']['api_key'] = api_key

    # Initialize Redis
    try:
        redis_cfg = RedisConfig()
        cache = RedisCacheManager(
            config=redis_cfg
        )
        await cache.connect()
    except Exception as e:
        jlog({"event": "redis_error", "error": str(e)})
        return 1

    # Generate session hash
    session_hash = get_session_hash(args.session_id)
    jlog({"event": "session_start", "session_id": args.session_id, "hash": session_hash})

    # Initialize metrics collector
    metrics_collector = TestMetricsCollector()

    try:
        # Create and initialize manager
        manager = ConversationManager(config, prompts, cache, args.session_id)
        await manager.initialize()

        # Run test scenario
        for i in range(args.repeats):
            print(f"\n=== Iteration {i + 1}/{args.repeats} ===")
            await run_test_scenario(manager, session_hash, metrics_collector)
            
            if i < args.repeats - 1:
                await asyncio.sleep(2)
    except Exception as e:
        jlog({"event": "test_error", "error": str(e)})
        return 1
    finally:
        # Cleanup
        await manager.shutdown()

    # Generate reports
    try:
        md_path, json_path = metrics_collector.save_reports(report_dir, args.session_id)
        print(f"\nReports saved:")
        print(f"- Markdown: {md_path}")
        print(f"- Raw JSON: {json_path}")
    except Exception as e:
        jlog({"event": "report_error", "error": str(e)})
        return 1

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)