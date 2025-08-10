from __future__ import annotations
from typing import List, Optional, Dict, Any, Union
import numpy as np
import logging
import time
import re
from ru_word2number import w2n

from intent_classifier.model_manager import ModelManager
from intent_classifier.repository import IntentRepository
from intent_classifier.entity_extractors import SimpleNumericExtractor, BooleanExtractor
from domain.models import IntentResult
# Импортируем наш новый FastText классификатор
from intent_classifier.fasttext_classifier import FastTextClassifier
from domain.models import FaqResult

logger = logging.getLogger("intent.classifier")

class IntentClassifier:
    def __init__(
        self,
        model_path: str,
        repo: IntentRepository,
        config: dict,
        extractors: Dict[str, Any],
        device: str = "cpu",
        fasttext_model_path: Optional[str] = "configs/fasttext_model.bin" # Путь к модели FastText
    ) -> None:
        self.repo = repo
        self.config = config
        self.extractors = extractors
        ModelManager.initialize(model_path, device)
        
        # Инициализируем FastText классификатор
        self.fasttext_classifier = FastTextClassifier(model_path=fasttext_model_path)
        if not self.fasttext_classifier.model:
            logger.warning("FastText model not found or failed to load. The secondary classifier will be disabled.")

    def _extract_number(self, text: str) -> Optional[Union[int, float]]:
        """Быстрое извлечение числа из текста."""
        # 1. Пробуем регулярки для цифр
        number_pattern = r'\d+(?:\.\d+)?'
        match = re.search(number_pattern, text)
        if match:
            return float(match.group())
        
        # 2. Пробуем ru_word2number для текстовых чисел
        try:
            return w2n.word_to_num(text)
        except ValueError:
            return None

    async def _classify_with_primary_model(
        self,
        text: str,
        expected_intents: List[str],
        previous_leader: Optional[str] = None
    ) -> Optional[IntentResult]:
        """Основная логика классификации с использованием семантической модели."""
        user_embedding = await ModelManager.get_instance().embed([text])
        user_embedding = user_embedding[0]

        candidate_vectors = self.repo.get_intent_vectors(expected_intents)
        if not candidate_vectors:
            return None

        scores = {intent_id: np.dot(user_embedding, centroid) for intent_id, centroid in candidate_vectors.items()}
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

        if not sorted_scores:
            return None

        leader_intent, leader_score = sorted_scores[0]

        # Confirmation Gates
        if leader_score < self.config["thresholds"]["confidence"]:
            logger.debug(f"Primary model score {leader_score} is below confidence threshold.")
            return None

        if len(sorted_scores) > 1:
            second_score = sorted_scores[1][1]
            if (leader_score - second_score) < self.config["thresholds"]["gap"]:
                logger.debug(f"Primary model score gap {leader_score - second_score} is below threshold.")
                return None
        
        if previous_leader and leader_intent != previous_leader:
            logger.debug(f"Primary model detected intent '{leader_intent}' which is not the previous leader '{previous_leader}'.")
            return None
        
        return IntentResult(
            intent_id=leader_intent,
            score=leader_score,
            entities=None, # Сущности извлекаются отдельно
            current_leader=leader_intent
        )
        
    def _classify_with_secondary_model(self, text: str) -> Optional[IntentResult]:
        """Резервная логика классификации с использованием FastText."""
        if not self.fasttext_classifier or not self.fasttext_classifier.model:
            return None
        
        prediction = self.fasttext_classifier.predict(text)
        if prediction:
            intent_id, score = prediction
            # Используем отдельный, более строгий порог для FastText
            if score >= self.config.get("fasttext_threshold", 0.7):
                logger.info(f"Secondary model (FastText) classified text as '{intent_id}' with score {score:.4f}")
                return IntentResult(
                    intent_id=intent_id,
                    score=score,
                    entities=None,
                    current_leader=intent_id
                )
        return None

    async def classify_intent(
        self,
        text: str,
        expected_intents: List[str],
        previous_leader: Optional[str] = None
    ) -> Optional[IntentResult]:
        t_start = time.monotonic()
        logger.info(f"classify_intent started for text: '{text}'")

        # 1. Быстрая проверка на число (эвристика)
        number = self._extract_number(text)
        if number is not None and "provide_number" in expected_intents:
            metadata = self.repo.get_intent_metadata("provide_number")
            if metadata:
                return IntentResult(
                    intent_id="provide_number",
                    score=0.95,
                    entities={"value": number},
                    current_leader="provide_number"
                )
        
        # 2. Основная семантическая модель
        result = await self._classify_with_primary_model(text, expected_intents, previous_leader)

        # 3. Если основная модель не справилась, используем вторичную (FastText)
        if result is None:
            logger.debug("Primary model failed. Falling back to secondary model (FastText).")
            result = self._classify_with_secondary_model(text)

        # 4. Если результат есть (от любой из моделей), извлекаем сущности
        if result:
            entities = None
            metadata = self.repo.get_intent_metadata(result.intent_id)
            if metadata and "entity" in metadata:
                entity_meta = metadata["entity"]
                # Для `provide_number` мы уже извлекли число
                if result.intent_id == "provide_number" and number is not None:
                    entities = {"value": number}
                else:
                    parser_name = entity_meta.get("parser")
                    if parser_name in self.extractors:
                        extractor = self.extractors[parser_name]
                        extracted_value = extractor.extract(text)
                        if extracted_value is not None:
                            entities = {"value": extracted_value}
                        elif entity_meta.get("required", False):
                            # Если сущность обязательна, но не найдена, отменяем результат
                            logger.warning(f"Required entity for intent '{result.intent_id}' not found in text.")
                            return None
            result.entities = entities
            
        t_end = time.monotonic()
        if result:
            logger.info(f"classify_intent finished in {(t_end - t_start) * 1000:.2f}ms. Leader: {result.intent_id}")
        else:
            logger.info(f"classify_intent finished in {(t_end - t_start) * 1000:.2f}ms. No intent found.")
            
        return result
        
    async def find_faq_answer(self, text: str) -> Optional[FaqResult]:
        t_start = time.monotonic()
        logger.info(f"find_faq_answer started for text: '{text}'")

        # Используем ModelManager для получения эмбеддинга
        user_embedding = await ModelManager.get_instance().embed([text])
        user_embedding = user_embedding[0]
        
        faq_vectors = self.repo.get_all_faq_vectors()
        if not faq_vectors:
            return None
            
        scores = {qid: np.dot(user_embedding, vec) for qid, vec in faq_vectors.items()}
        
        if not scores:
            return None
            
        best_qid, best_score = max(scores.items(), key=lambda item: item[1])
        
        if best_score < self.config.get("faq", {}).get("confidence", 0.7):
            return None
            
        answer_text = self.repo.get_faq_answer_text(best_qid)
        if not answer_text:
            return None
            
        t_end = time.monotonic()
        logger.info(f"find_faq_answer finished in {(t_end - t_start) * 1000:.2f}ms. Best QID: {best_qid}")
        
        return FaqResult(
            question_id=best_qid,
            answer_text=answer_text,
            score=best_score
        )
