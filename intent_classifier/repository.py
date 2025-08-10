from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import pickle
import numpy as np
from intent_classifier.model_wrapper import OnnxModelWrapper

class IntentRepository:
    """
    Держит в памяти:
      - intents: Dict[intent_id, dict]     # метаданные интента (phrases, entity и т.п.)
      - vectors: Dict[intent_id, np.ndarray]  # эмбеддинги фраз (shape: [K, D])
      - centroids: Dict[intent_id, np.ndarray] # усреднённый вектор интента (D,)
      - faq: Dict[question_id, dict] (опц.)
      - faq_vectors: Dict[question_id, np.ndarray] (опц.)
    """
    def __init__(self) -> None:
        self.intents: Dict[str, dict] = {}
        self.vectors: Dict[str, np.ndarray] = {}
        self.centroids: Dict[str, np.ndarray] = {}
        self.faq: Dict[str, dict] = {}
        self.faq_vectors: Dict[str, np.ndarray] = {}

    def load_from_backup(self, filepath: str) -> None:
        with open(filepath, "rb") as f:
            backup = pickle.load(f)
            self.intents = backup.get("intents", {})
            self.vectors = backup.get("vectors", {})
            self.centroids = backup.get("centroids", {})
            self.faq = backup.get("faq", {})
            self.faq_vectors = backup.get("faq_vectors", {})

    async def prepare_and_save_backup(self, dialogue_map: dict, intents: dict, model: "OnnxModelWrapper", filepath: str) -> None:
        all_phrases_map = {}
        for intent_id, intent_data in intents.items():
            phrases = [item["response"] for item in intent_data.get("description", [])]
            all_phrases_map[intent_id] = phrases

        intent_vectors = {}
        intent_centroids = {}
        
        for intent_id, phrases in all_phrases_map.items():
            if not phrases:
                continue
            embeddings = await model.embed(phrases)
            intent_vectors[intent_id] = embeddings
            intent_centroids[intent_id] = np.mean(embeddings, axis=0)

        backup_data = {
            "intents": intents,
            "vectors": intent_vectors,
            "centroids": intent_centroids,
            "faq": {}, # FAQ backup preparation can be added here
            "faq_vectors": {},
        }

        with open(filepath, "wb") as f:
            pickle.dump(backup_data, f, protocol=5)

    def get_intent_vectors(self, intent_ids: List[str]) -> Dict[str, np.ndarray]:
        return {k: self.centroids[k] for k in intent_ids if k in self.centroids}

    def get_intent_metadata(self, intent_id: str) -> Optional[dict]:
        return self.intents.get(intent_id)

    def get_all_faq_vectors(self) -> Dict[str, np.ndarray]:
        return self.faq_vectors

    def get_faq_answer_text(self, qid: str) -> Optional[str]:
        return self.faq.get(qid, {}).get("answer")
