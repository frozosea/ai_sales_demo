from __future__ import annotations
import os, json, time, argparse, logging
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
import asyncio
import statistics

# Add project root to path for absolute imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from intent_classifier.model_manager import ModelManager, ModelManagerConfig
from intent_classifier.repository import IntentRepository
from intent_classifier.classifier import IntentClassifier
from intent_classifier.entity_extractors import SimpleNumericExtractor, BooleanExtractor

logging.basicConfig(level=logging.INFO, format='%(message)s')

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=str, required=True, help="Path to intents_backup.pkl")
    parser.add_argument("--device", type=str, default="cpu", help="Device to use (cpu or cuda)")
    parser.add_argument("--text", type=str, required=True, help="Text to classify")
    parser.add_argument("--expected", type=str, required=True, help="Comma-separated expected intents")
    parser.add_argument("--repeat", type=int, default=20, help="Number of repetitions for benchmarks")
    args = parser.parse_args()

    load_dotenv()
    model_path = os.getenv("EMB_MODEL_PATH")
    if not model_path:
        logging.error(json.dumps({"event": "error", "message": "EMB_MODEL_PATH not set in .env"}))
        return
        
    # Инициализируем ModelManager с более частым прогревом для бенчмарка
    config = ModelManagerConfig(warmup_interval_sec=5.0)
    ModelManager.initialize(model_path, device=args.device, config=config)
    
    repo = IntentRepository()
    repo.load_from_backup(args.backup)

    extractors = {
        "simple_numeric": SimpleNumericExtractor(),
        "boolean": BooleanExtractor()
    }
    
    config = {
        "thresholds": {"confidence": 0.4, "gap": 0.05},
        "faq": {"confidence": 0.55}
    }
    classifier = IntentClassifier(model_path, repo, config, extractors, device=args.device)
    
    expected_intents = args.expected.split(',')

    # Benchmark single embed
    embed_single_times = []
    for _ in range(args.repeat):
        t_start = time.monotonic()
        await ModelManager.get_instance().embed([args.text])
        t_end = time.monotonic()
        embed_single_times.append((t_end - t_start) * 1000)
    
    logging.info(json.dumps({"event": "embed_single", "ms": statistics.median(embed_single_times)}))

    # Benchmark batch embed
    batch_text = [args.text] * 64
    t_start = time.monotonic()
    await ModelManager.get_instance().embed(batch_text)
    t_end = time.monotonic()
    logging.info(json.dumps({"event": "embed_batch", "n": 64, "ms": (t_end - t_start) * 1000}))

    # Benchmark classify
    classify_times = []
    for _ in range(args.repeat):
        t_start = time.monotonic()
        result = await classifier.classify_intent(args.text, expected_intents)
        t_end = time.monotonic()
        classify_times.append((t_end - t_start) * 1000)
        if result:
            logging.info(json.dumps({
                "event": "classify",
                "intent": result.intent_id,
                "score": result.score,
                "ms": (t_end - t_start) * 1000
            }))

    if classify_times:
        p50 = statistics.median(classify_times)
        p95 = np.percentile(classify_times, 95)
        logging.info(json.dumps({"event": "summary", "p50": p50, "p95": p95}))

    # Закрываем ModelManager
    await ModelManager.close()

if __name__ == "__main__":
    asyncio.run(main()) 