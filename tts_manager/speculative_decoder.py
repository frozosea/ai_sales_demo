#!/usr/bin/env python3
"""
Speculative Decoding для ускорения LLM генерации
Использует быструю draft модель для предсказания токенов
"""

import asyncio
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class SpeculativeConfig:
    """Конфигурация speculative decoding"""
    draft_model_name: str = "gpt-3.5-turbo"  # Быстрая draft модель
    target_model_name: str = "gpt-4"         # Основная модель
    max_draft_tokens: int = 8                # Максимум токенов для draft
    acceptance_threshold: float = 0.8        # Порог принятия draft токенов
    enable_speculation: bool = True


class SpeculativeDecoder:
    """Speculative Decoder для ускорения генерации"""
    
    def __init__(self, config: SpeculativeConfig):
        self.config = config
        self.draft_model = None  # Быстрая draft модель
        self.target_model = None  # Основная модель
        self.cache = {}  # Кэш для draft токенов
        
    async def generate_with_speculation(self, prompt: str) -> List[str]:
        """Генерирует текст с speculative decoding"""
        if not self.config.enable_speculation:
            return await self._generate_normal(prompt)
        
        tokens = []
        current_text = prompt
        
        while len(tokens) < 100:  # Ограничение для демонстрации
            # 1. Draft модель генерирует несколько токенов быстро
            draft_start = time.perf_counter()
            draft_tokens = await self._generate_draft(current_text, self.config.max_draft_tokens)
            draft_time = (time.perf_counter() - draft_start) * 1000
            
            # 2. Target модель проверяет draft токены
            target_start = time.perf_counter()
            accepted_tokens = await self._verify_draft(current_text, draft_tokens)
            target_time = (time.perf_counter() - target_start) * 1000
            
            # 3. Добавляем принятые токены
            tokens.extend(accepted_tokens)
            current_text = prompt + "".join(tokens)
            
            # Логируем производительность
            print(f"Draft: {draft_time:.1f}ms, Target: {target_time:.1f}ms, "
                  f"Accepted: {len(accepted_tokens)}/{len(draft_tokens)}")
            
            # Если приняли все draft токены, продолжаем
            if len(accepted_tokens) == len(draft_tokens):
                continue
            else:
                # Если не приняли все, генерируем один токен обычным способом
                fallback_token = await self._generate_single_token(current_text)
                tokens.append(fallback_token)
                break
        
        return tokens
    
    async def _generate_draft(self, text: str, max_tokens: int) -> List[str]:
        """Быстрая draft модель генерирует несколько токенов"""
        # Симуляция быстрой draft модели
        await asyncio.sleep(0.01)  # 10ms для draft модели
        
        # Простое предсказание на основе контекста
        draft_tokens = []
        for i in range(max_tokens):
            # Простая эвристика для демонстрации
            if "привет" in text.lower():
                draft_tokens.append(" мир")
            elif "как" in text.lower():
                draft_tokens.append(" дела")
            else:
                draft_tokens.append(" и")
        
        return draft_tokens
    
    async def _verify_draft(self, text: str, draft_tokens: List[str]) -> List[str]:
        """Target модель проверяет draft токены"""
        # Симуляция проверки target моделью
        await asyncio.sleep(0.05)  # 50ms для target модели
        
        # Простая логика принятия для демонстрации
        accepted_tokens = []
        for i, token in enumerate(draft_tokens):
            # Принимаем токен с вероятностью acceptance_threshold
            if i < len(draft_tokens) * self.config.acceptance_threshold:
                accepted_tokens.append(token)
            else:
                break
        
        return accepted_tokens
    
    async def _generate_single_token(self, text: str) -> str:
        """Генерирует один токен обычным способом"""
        await asyncio.sleep(0.1)  # 100ms для обычной генерации
        return "."
    
    async def _generate_normal(self, prompt: str) -> List[str]:
        """Обычная генерация без speculation"""
        tokens = []
        current_text = prompt
        
        for _ in range(10):  # Ограничение для демонстрации
            token = await self._generate_single_token(current_text)
            tokens.append(token)
            current_text = prompt + "".join(tokens)
        
        return tokens


# Функция для тестирования speculative decoding
async def test_speculative_decoding():
    """Тестирует speculative decoding"""
    config = SpeculativeConfig(
        enable_speculation=True,
        max_draft_tokens=8,
        acceptance_threshold=0.8
    )
    
    decoder = SpeculativeDecoder(config)
    
    # Тестируем с speculation
    start_time = time.perf_counter()
    tokens_spec = await decoder.generate_with_speculation("Привет, как дела?")
    spec_time = (time.perf_counter() - start_time) * 1000
    
    # Тестируем без speculation
    config.enable_speculation = False
    start_time = time.perf_counter()
    tokens_normal = await decoder.generate_with_speculation("Привет, как дела?")
    normal_time = (time.perf_counter() - start_time) * 1000
    
    print(f"Speculative: {spec_time:.1f}ms, Normal: {normal_time:.1f}ms")
    print(f"Speedup: {normal_time/spec_time:.1f}x")
    print(f"Tokens (spec): {tokens_spec}")
    print(f"Tokens (normal): {tokens_normal}")


if __name__ == "__main__":
    asyncio.run(test_speculative_decoding())


