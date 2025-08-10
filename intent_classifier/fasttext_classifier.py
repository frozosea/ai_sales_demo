from __future__ import annotations
import fasttext
from typing import Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger("intent.fasttext")

class FastTextClassifier:
    """
    Враппер для обучения и использования модели FastText.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        if self.model_path and Path(self.model_path).exists():
            self.load_model()

    def train(self, data_path: str, model_save_path: str, **kwargs):
        """
        Обучает модель на данных и сохраняет ее.
        :param data_path: Путь к обучающему файлу в формате fasttext.
        :param model_save_path: Путь для сохранения обученной модели.
        :param kwargs: Дополнительные параметры для fasttext.train_supervised.
        """
        logger.info(f"Starting FastText model training with data from: {data_path}")
        try:
            model = fasttext.train_supervised(input=data_path, **kwargs)
            model.save_model(model_save_path)
            self.model_path = model_save_path
            self.model = model
            logger.info(f"FastText model trained and saved to: {model_save_path}")
        except Exception as e:
            logger.error(f"Error during FastText model training: {e}")
            raise

    def load_model(self):
        """Загружает обученную модель."""
        if self.model_path:
            try:
                self.model = fasttext.load_model(self.model_path)
                logger.info(f"FastText model loaded from: {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load FastText model from {self.model_path}: {e}")
                self.model = None
        else:
            logger.warning("Model path is not set. Cannot load FastText model.")

    def predict(self, text: str, k: int = 1) -> Optional[Tuple[str, float]]:
        """
        Предсказывает интент для текста.
        Возвращает кортеж (intent_id, score) или None, если предсказание не удалось.
        """
        if not self.model:
            logger.warning("FastText model is not loaded. Cannot predict.")
            return None

        try:
            # fasttext возвращает список лейблов и список вероятностей
            labels, scores = self.model.predict(text, k=k)
            if labels:
                # Убираем префикс __label__
                intent = labels[0].replace('__label__', '')
                score = scores[0]
                return intent, score
            return None
        except Exception as e:
            logger.error(f"Error during FastText prediction for text '{text}': {e}")
            return None 