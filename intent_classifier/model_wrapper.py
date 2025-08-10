from __future__ import annotations
import asyncio
from pathlib import Path
from typing import List
import numpy as np
import logging
import time
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForFeatureExtraction

logger = logging.getLogger("intent.model")

class OnnxModelWrapper:
    """
    - model_path: абсолютный путь до каталога с моделью (./models/our_model)
    - device: 'cpu' | 'cuda' (по умолчанию cpu)
    - Гарантирует: embed(List[str]) -> np.ndarray [N, D], L2-нормализованный
    """
    def __init__(self, model_path: str, device: str = "cpu") -> None:
        provider = "CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        # Теперь мы просто загружаем готовую ONNX-модель, без повторного экспорта
        self.model = ORTModelForFeatureExtraction.from_pretrained(model_path, provider=provider)

    @property
    def embedding_dim(self) -> int:
        """Возвращает размерность эмбеддингов модели."""
        return self.model.config.hidden_size

    async def embed(self, texts: List[str]) -> np.ndarray:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: List[str]) -> np.ndarray:
        t_start_tokenization = time.monotonic()
        inputs = self.tokenizer(texts, padding=True, truncation=True, return_tensors="np")
        t_end_tokenization = time.monotonic()
        
        logger.info(
            f"Tokenization took {(t_end_tokenization - t_start_tokenization) * 1000:.2f}ms for {len(texts)} texts"
        )

        t_start_inference = time.monotonic()
        outputs = self.model(**inputs)
        # Используем mean_pooling как в compare_onnx_pytorch.py
        input_mask_expanded = np.expand_dims(inputs["attention_mask"], axis=-1)
        sum_embeddings = np.sum(outputs.last_hidden_state * input_mask_expanded, axis=1)
        sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        embeddings = sum_embeddings / sum_mask
        t_end_inference = time.monotonic()

        logger.info(
            f"Inference took {(t_end_inference - t_start_inference) * 1000:.2f}ms for {len(texts)} texts"
        )

        # L2 нормализация
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings.astype(np.float32)
