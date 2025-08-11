from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple, Union
import numpy as np
import logging
import time
import re
from ru_word2number import w2n

from intent_classifier.model_manager import ModelManager
from intent_classifier.repository import IntentRepository
from intent_classifier.entity_extractors import SimpleNumericExtractor, BooleanExtractor
from domain.models import IntentResult, FaqResult

logger = logging.getLogger("intent.classifier")

class IntentClassifier:
    def __init__(self, model_path: str, repo: IntentRepository, config: dict, extractors: Dict[str, Any], device: str = "cpu") -> None:
        self.repo = repo
        self.config = config
        self.extractors = extractors
        self.heuristics = {
            "exact_match": {
                # confirm_yes
                "ага": "confirm_yes",
                "угу": "confirm_yes",
                "конеч": "confirm_yes",
                # confirm_no
                "отбой": "confirm_no",
                "не хочу": "confirm_no", # Часто это простое "нет", а не причина
                "не не хочу": "confirm_no",
                # ask_cost
                # request_callback
                "не сейчас": "request_callback",
                "не могу говорить": "request_callback",
            }
        }
        # Инициализируем ModelManager вместо хранения ссылки на модель
        ModelManager.initialize(model_path, device)


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
        except:
            return None

    def _apply_heuristics(self, text: str) -> Optional[IntentResult]:
            """Отдельный слой для правил и эвристик."""
            clean_text = text.strip().lower()

            # Проверка на точное совпадение
            if clean_text in self.heuristics["exact_match"]:
                intent_id = self.heuristics["exact_match"][clean_text]
                logger.info(f"Heuristic applied: exact match for '{clean_text}' -> '{intent_id}'")
                return IntentResult(intent_id=intent_id, score=0.95, entities=None,current_leader=intent_id) # Score 1.0 - мы уверены
            
            # ... другие эвристики, если есть ...
            
            return None

    async def classify_intent(
        self,
        text: str,
        expected_intents: List[str],
        previous_leader: Optional[str] = None
    ) -> Optional[IntentResult]:
        t_start = time.monotonic()
        logger.info(f"classify_intent started for text: '{text}'")
        
        # Быстрая проверка на наличие числа
        number = self._extract_number(text)
        
        # Если нашли число и среди expected_intents есть provide_number,
        # проверяем его первым
        if number is not None and "provide_number" in expected_intents:
            metadata = self.repo.get_intent_metadata("provide_number")
            if metadata:
                # Возвращаем provide_number с высоким score и извлеченным числом
                return IntentResult(
                    intent_id="provide_number",
                    score=0.95,  # Высокий score, так как мы уверены что это число
                    entities={"value": number},
                    current_leader="provide_number"
                )
        heuristic_result = self._apply_heuristics(text)
        if heuristic_result and heuristic_result.intent_id in expected_intents:
            return heuristic_result
        
        SILENCE_MARKERS = {'...', 'хм', 'ммм', 'эм', 'эээ', 'ааа'}
        # Проверяем точное совпадение после очистки
        if text.strip().lower() in SILENCE_MARKERS:
            logger.info("Heuristic applied: matched silence marker.")
            return IntentResult(intent_id="silence", score=1.0, entities=None, current_leader="silence")

        # 2. Жесткое правило для "неа": исправляем самую частую ошибку confirm_no -> confirm_yes
        if text.strip().lower() == 'неа':
            logger.info("Heuristic applied: matched 'неа' as confirm_no.")
            return IntentResult(intent_id="confirm_no", score=0.99, entities=None, current_leader="confirm_no")

        # 3. Эвристика для коротких вопросительных фраз, которые модель путает с confirm_yes
        # "что", "зачем", "почем", "в чем дело" - это точно не согласие.
        # Мы не будем пытаться угадать интент, а просто предотвратим ложное срабатывание.
        SHORT_QUESTION_WORDS = {'что', 'зачем', 'почем', 'чего', 'как'}
        words = text.strip().lower().split()
        if len(words) <= 2 and any(word in SHORT_QUESTION_WORDS for word in words):
            # Вместо того чтобы пытаться угадать, мы просто говорим "не уверен",
            # пропуская классификацию. Оркестратор может это обработать.
            logger.info("Heuristic applied: short question detected, skipping classification to avoid false positive.")
            return None
        
        # Если число не найдено или provide_number не в expected_intents,
        # используем модель для классификации через ModelManager
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
        print(f"[DEBUG] Текст: '{text}' -> Лидер: '{leader_intent}' (Score: {leader_score:.4f})")

        # Confirmation Gates
        if leader_score < self.config["thresholds"]["confidence"]:
            return None

        if len(sorted_scores) > 1:
            second_score = sorted_scores[1][1]
            second_intent, _ = sorted_scores[1]
            print(f"[DEBUG] ...Второй: '{second_intent}' (Score: {second_score:.4f}), Разрыв: {(leader_score - second_score):.4f}")
            if (leader_score - second_score) < self.config["thresholds"]["gap"]:
                return None
        
        if previous_leader and leader_intent != previous_leader:
            return None

        # Entity Extraction - используем уже извлеченное число если оно есть
        entities = None
        metadata = self.repo.get_intent_metadata(leader_intent)
        if metadata and "entity" in metadata:
            entity_meta = metadata["entity"]
            if entity_meta.get("type") == "number" and number is not None:
                # Используем уже извлеченное число
                entities = {"value": number}
            else:
                # Для других типов сущностей используем соответствующие экстракторы
                parser_name = entity_meta.get("parser")
                if parser_name in self.extractors:
                    extractor = self.extractors[parser_name]
                    extracted_value = extractor.extract(text)
                    if extracted_value is not None:
                        entities = {"value": extracted_value}
                    elif entity_meta.get("required", False):
                        return None
        
        t_end = time.monotonic()
        logger.info(f"classify_intent finished in {(t_end - t_start) * 1000:.2f}ms. Leader: {leader_intent}")
        print(f"leader_intent: {leader_intent}, score: {leader_score}")
        return IntentResult(
            intent_id=leader_intent,
            score=leader_score,
            entities=entities,
            current_leader=leader_intent
        )

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
