from __future__ import annotations
from typing import Optional
import re

class SimpleNumericExtractor:
    def extract(self, text: str) -> Optional[int]:
        """
        Извлекает первое целое число (цифры, пробелы, разделители), возвращает int или None.
        """
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int("".join(numbers))
        return None

class BooleanExtractor:
    def extract(self, text: str) -> Optional[bool]:
        """
        Простая эвристика: ["да","ага","верно"] -> True; ["нет","не","неа"] -> False; иначе None.
        """
        text_lower = text.lower()
        if any(word in text_lower for word in ["да", "ага", "верно", "подтверждаю"]):
            return True
        if any(word in text_lower for word in ["нет", "не", "неа", "отмена"]):
            return False
        return None
