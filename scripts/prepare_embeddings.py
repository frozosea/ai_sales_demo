from __future__ import annotations
import os, json, time, argparse, logging, pickle
from pathlib import Path
from dotenv import dotenv_values, load_dotenv
import numpy as np
import asyncio

# Add project root to path for absolute imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from intent_classifier.model_wrapper import OnnxModelWrapper
from intent_classifier.repository import IntentRepository

logging.basicConfig(level=logging.INFO, format='%(message)s')

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intents", type=str, required=True, help="Path to intents.json")
    parser.add_argument("--dialogue", type=str, help="Path to dialogue_map.json (optional)")
    parser.add_argument("--output", type=str, required=True, help="Path to save intents_backup.pkl")
    parser.add_argument("--batch", type=int, default=64, help="Batch size for embedding")
    parser.add_argument("--device", type=str, default="cpu", help="Device to use (cpu or cuda)")
    args = parser.parse_args()

    load_dotenv()
    model_path = os.getenv("EMB_MODEL_PATH")
    if not model_path:
        logging.error(json.dumps({"event": "error", "message": "EMB_MODEL_PATH not set in .env"}))
        return

    logging.info(json.dumps({"event": "prepare_start"}))

    with open(args.intents, "r", encoding="utf-8") as f:
        intents_data = json.load(f)

    dialogue_data = {}
    if args.dialogue:
        with open(args.dialogue, "r", encoding="utf-8") as f:
            dialogue_data = json.load(f)
    
    model = OnnxModelWrapper(model_path, device=args.device)
    repo = IntentRepository()

    all_phrases = []
    intent_phrase_counts = {}
    for intent_id, intent_content in intents_data.items():
        phrases = [item['response'] for item in intent_content.get('description', [])]
        intent_phrase_counts[intent_id] = len(phrases)
        all_phrases.extend(phrases)

    # Используем динамический размер эмбеддинга из модели
    embedding_dim = model.embedding_dim
    all_embeddings = np.zeros((len(all_phrases), embedding_dim))
    
    for i in range(0, len(all_phrases), args.batch):
        batch_phrases = all_phrases[i:i+args.batch]
        t_start = time.monotonic()
        batch_embeddings = await model.embed(batch_phrases)
        all_embeddings[i:i+len(batch_phrases)] = batch_embeddings
        t_end = time.monotonic()
        logging.info(json.dumps({
            "event": "embed_batch_done",
            "batch_idx": i // args.batch,
            "batch_size": len(batch_phrases),
            "ms": (t_end - t_start) * 1000
        }))

    phrase_idx = 0
    for intent_id, count in intent_phrase_counts.items():
        intent_embeddings = all_embeddings[phrase_idx:phrase_idx+count]
        repo.vectors[intent_id] = intent_embeddings
        repo.centroids[intent_id] = np.mean(intent_embeddings, axis=0)
        phrase_idx += count
        logging.info(json.dumps({
            "event": "intent_ready",
            "intent_id": intent_id,
            "phrases": count,
            "D": repo.centroids[intent_id].shape[0]
        }))

    repo.intents = intents_data

    with open(args.output, "wb") as f:
        pickle.dump({
            "intents": repo.intents,
            "vectors": repo.vectors,
            "centroids": repo.centroids,
            "faq": repo.faq,
            "faq_vectors": repo.faq_vectors
        }, f, protocol=5)
        
    logging.info(json.dumps({
        "event": "backup_saved",
        "path": args.output,
        "size_bytes": os.path.getsize(args.output)
    }))

if __name__ == "__main__":
    asyncio.run(main())
