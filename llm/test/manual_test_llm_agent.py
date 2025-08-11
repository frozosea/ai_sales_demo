from __future__ import annotations
import asyncio
import argparse
import yaml
import os
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import logging

from llm.manager import ConversationManager
from infra.redis_config import RedisCacheManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.agent")

def jlog(data: dict):
    logger.info(json.dumps(data))

def generate_report(metrics: list[dict], report_dir: Path, session_id: str):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    report_path = report_dir / f"llm_agent_{timestamp}.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# LLM Agent E2E Test Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Session ID:** {session_id}\n\n")
        
        f.write("## Performance Summary\n\n")
        f.write("| Metric | Average | P50 | P95 |\n")
        f.write("|:---|---:|---:|---:|\n")
        
        ttfts = [m['ttft_ms'] for m in metrics if 'ttft_ms' in m]
        totals = [m['total_ms'] for m in metrics if 'total_ms' in m]
        
        if ttfts:
            f.write(f"| TTFT (ms) | {sum(ttfts)/len(ttfts):.1f} | {sorted(ttfts)[len(ttfts)//2]:.1f} | {sorted(ttfts)[int(len(ttfts)*0.95)]:.1f} |\n")
        if totals:
            f.write(f"| Total Time (ms) | {sum(totals)/len(totals):.1f} | {sorted(totals)[len(totals)//2]:.1f} | {sorted(totals)[int(len(totals)*0.95)]:.1f} |\n")
        
        f.write("\n## Cache Performance\n\n")
        cache_hits = sum(1 for m in metrics if m.get('cache_hit', False))
        total_queries = len([m for m in metrics if 'cache_hit' in m])
        if total_queries > 0:
            hit_rate = cache_hits / total_queries
            f.write(f"- Cache Hit Rate: {hit_rate:.1%}\n")
            f.write(f"- Total Cache Queries: {total_queries}\n")
            f.write(f"- Cache Hits: {cache_hits}\n")
        
        f.write("\n## Context Management\n\n")
        f.write("| Turn | Context Size Before | Context Size After | Warmup Started | Handover Time (ms) |\n")
        f.write("|:---|---:|---:|:---:|---:|\n")
        
        for i, m in enumerate(metrics, 1):
            warmup = "Yes" if m.get('warmup_started', False) else "No"
            handover = f"{m['handover_ms']:.1f}" if 'handover_ms' in m else "-"
            f.write(f"| {i} | {m.get('context_before', 0):.1%} | {m.get('context_after', 0):.1%} | {warmup} | {handover} |\n")
        
        f.write("\n## Conversation Flow\n\n")
        for i, m in enumerate(metrics, 1):
            f.write(f"### Turn {i}\n\n")
            f.write(f"**User:** {m.get('user_text', '')}\n\n")
            f.write(f"**Assistant:** {m.get('assistant_text', '')}\n\n")
            f.write(f"- TTFT: {m.get('ttft_ms', '-'):.1f} ms\n")
            f.write(f"- Total Time: {m.get('total_ms', '-'):.1f} ms\n")
            if 'cache_hit' in m:
                f.write(f"- Cache: {'Hit' if m['cache_hit'] else 'Miss'}\n")
            f.write("\n")
    
    jlog({"event": "report_saved", "path": str(report_path)})
    return report_path

async def run_conversation_turn(manager: ConversationManager, text: str) -> dict:
    metrics = {}
    metrics['user_text'] = text
    
    # Measure context before
    metrics['context_before'] = manager.dual_ctx.active_context.estimate_usage_ratio()
    
    t_start = time.monotonic()
    jlog({"event": "turn_start", "text": text})
    
    first_token_time = None
    assistant_text = ""
    
    async for chunk in manager.process_user_turn(text):
        if first_token_time is None and chunk.text_chunk:
            first_token_time = time.monotonic()
            metrics['ttft_ms'] = (first_token_time - t_start) * 1000
            jlog({"event": "first_token", "ms": metrics['ttft_ms']})
        
        if not chunk.is_final_chunk:
            assistant_text += chunk.text_chunk
    
    t_end = time.monotonic()
    metrics['total_ms'] = (t_end - t_start) * 1000
    metrics['assistant_text'] = assistant_text
    
    # Measure context after
    metrics['context_after'] = manager.dual_ctx.active_context.estimate_usage_ratio()
    
    # Check if warmup/handover occurred
    if hasattr(manager.dual_ctx, '_warmup_ready_time'):
        metrics['warmup_started'] = manager.dual_ctx._warmup_ready_time is not None
        if manager.dual_ctx._warmup_ready_time:
            metrics['handover_ms'] = (t_end - manager.dual_ctx._warmup_ready_time) * 1000
    
    jlog({
        "event": "turn_complete",
        "ttft_ms": metrics.get('ttft_ms'),
        "total_ms": metrics['total_ms'],
        "context": {
            "before": metrics['context_before'],
            "after": metrics['context_after']
        }
    })
    
    return metrics

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--prompts", type=str, required=True)
    parser.add_argument("--session-id", type=str, required=True)
    parser.add_argument("--repeats", type=int, default=1)
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

    # Replace API key in config
    config['llm']['api_key'] = api_key

    # Initialize Redis cache
    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_db = int(os.getenv("REDIS_DB", 0))
    
    try:
        cache = RedisCacheManager(host=redis_host, port=redis_port, db=redis_db)
    except Exception as e:
        jlog({"event": "error", "message": f"Failed to connect to Redis: {str(e)}"})
        return 1

    manager = ConversationManager(config, prompts, cache, args.session_id)
    
    # Test conversation flow that will trigger context management
    conversation = [
        "What is the capital of France?",
        "And what is its population?",
        "Tell me about its most famous landmark.",
        "What's the weather like there in summer?",
        "Thank you, that's all for now."
    ]
    
    all_metrics = []
    try:
        for iteration in range(args.repeats):
            print(f"\n=== Iteration {iteration + 1}/{args.repeats} ===")
            
            for turn, text in enumerate(conversation, 1):
                print(f"\n[Turn {turn}] User: {text}")
                print("Assistant: ", end="", flush=True)
                
                metrics = await run_conversation_turn(manager, text)
                all_metrics.append(metrics)
                
                print(metrics['assistant_text'])
                
                if turn < len(conversation):
                    await asyncio.sleep(0.5)  # Brief pause between turns
            
            if iteration < args.repeats - 1:
                await asyncio.sleep(2)  # Longer pause between iterations
                print("\n" + "="*50)
    finally:
        await manager.shutdown()
        await cache.disconnect()
    
    # Generate and save report
    report_path = generate_report(all_metrics, report_dir, args.session_id)
    print(f"\nReport saved to: {report_path}")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
