📄 File 1 — SPEC-IC-1-Core.md

IntentClassifier v3 (Stateless) — ядро модуля

0) Контекст

Модуль отвечает за быструю (<100мс) и предсказуемую классификацию интентов и поиск FAQ-ответов. Полностью stateless, потокобезопасный. Потребители: Orchestrator (runtime) и офлайн-скрипты (подготовка эмбеддингов).

1) Область работ (файлы)

project_root/
├─ intent_classifier/
│  ├─ __init__.py
│  ├─ model_wrapper.py         # OnnxModelWrapper: загрузка модели, async embed()
│  ├─ repository.py            # IntentRepository: хранение интентов/векторов/метаданных
│  ├─ entity_extractors.py     # Примитивные парсеры (число/boolean)
│  └─ classifier.py            # IntentClassifier v3 (stateless)
├─ domain/
│  └─ models.py                # содержит: IntentResult, FaqResult (см. ниже)
└─ configs/
   ├─ intents.json             # { "intents": { ... }, опционально "faq": {...} }
   └─ dialogue_map.json        # диалоговая карта (для скриптов и валидации контекстов)

2) Зависимости (runtime)
	•	numpy>=1.24
	•	onnxruntime>=1.17 (или onnxruntime-gpu — опционально, выбирается переменной окружения)
	•	transformers>=4.41, tokenizers>=0.15
	•	optimum>=1.17 (через optimum.onnxruntime для оннх-инференса)
	•	stdlib: asyncio, dataclasses, typing, pathlib, logging, time, math, json
	•	без faiss/annoy — косинус считаем в NumPy

3) Контракты (domain/models.py)

Если ещё нет — добавить (или переиспользовать уже существующие с той же сигнатурой):

from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass(slots=True)
class IntentResult:
    intent_id: str
    score: float
    entities: Optional[Dict[str, Any]]
    current_leader: str

@dataclass(slots=True)
class FaqResult:
    question_id: str
    answer_text: str
    score: float

4) Файл intent_classifier/model_wrapper.py

Цель: инкапсулировать работу с ONNX-моделью на базе optimum.onnxruntime.

# Импорты (жёстко)
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import List
import numpy as np
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForFeatureExtraction

class OnnxModelWrapper:
    """
    - model_path: абсолютный путь до каталога с моделью (./models/our_model)
    - device: 'cpu' | 'cuda' (по умолчанию cpu)
    - Гарантирует: embed(List[str]) -> np.ndarray [N, D], L2-нормализованный
    """
    def __init__(self, model_path: str, device: str = "cpu") -> None: ...
    async def embed(self, texts: List[str]) -> np.ndarray: ...

Требования к реализации:
	•	В конструкторе: загрузить AutoTokenizer.from_pretrained(model_path), ORTModelForFeatureExtraction.from_pretrained(model_path, provider=...).
	•	В embed: вызовы модели (токенизация + forward) выполнять через await asyncio.to_thread(...).
	•	Выход — np.ndarray float32, L2-нормализованный (вектор на единичной сфере).
	•	Логгер: logging.getLogger("intent.model"). Логировать время токенизации и инференса.

5) Файл intent_classifier/repository.py

Цель: слой доступа к данным интентов/FAQ и их векторов. Бэкап/восстановление.

# Импорты (жёстко)
from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import pickle
import numpy as np

class IntentRepository:
    """
    Держит в памяти:
      - intents: Dict[intent_id, dict]     # метаданные интента (phrases, entity и т.п.)
      - vectors: Dict[intent_id, np.ndarray]  # эмбеддинги фраз (shape: [K, D])
      - centroids: Dict[intent_id, np.ndarray] # усреднённый вектор интента (D,)
      - faq: Dict[question_id, dict] (опц.)
      - faq_vectors: Dict[question_id, np.ndarray] (опц.)
    """
    def __init__(self) -> None: ...
    def load_from_backup(self, filepath: str) -> None: ...
    def prepare_and_save_backup(self, dialogue_map: dict, intents: dict, model: "OnnxModelWrapper", filepath: str) -> None: ...
    def get_intent_vectors(self, intent_ids: List[str]) -> Dict[str, np.ndarray]: ...
    def get_intent_metadata(self, intent_id: str) -> Optional[dict]: ...
    def get_all_faq_vectors(self) -> Dict[str, np.ndarray]: ...
    def get_faq_answer_text(self, qid: str) -> Optional[str]: ...

Детали:
	•	Формат бэкапа: pickle (protocol=5): {"intents":..., "vectors":..., "centroids":..., "faq":..., "faq_vectors":...}.
	•	prepare_and_save_backup:
	•	Собрать фразы из intents.json (intents.*.phrases) и при желании из dialogue_flow (system_response.template как «весовые подсказки» — опционально).
	•	Векторизовать пачками через model.embed.
	•	Сохранить массивы и центроиды (mean по фразам интента).
	•	Векторы фраз каждого интента храним в одном массиве [K, D]; centroid — [D].

6) Файл intent_classifier/entity_extractors.py

Цель: минимальные парсеры сущностей.

from __future__ import annotations
from typing import Optional

class SimpleNumericExtractor:
    def extract(self, text: str) -> Optional[int]:
        """
        Извлекает первое целое число (цифры, пробелы, разделители), возвращает int или None.
        """
        ...

class BooleanExtractor:
    def extract(self, text: str) -> Optional[bool]:
        """
        Простая эвристика: ["да","ага","верно"] -> True; ["нет","не","неа"] -> False; иначе None.
        """
        ...

7) Файл intent_classifier/classifier.py

Цель: фасадный stateless-класс.

# Импорты (жёстко)
from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import logging
import time

from intent_classifier.model_wrapper import OnnxModelWrapper
from intent_classifier.repository import IntentRepository
from intent_classifier.entity_extractors import SimpleNumericExtractor, BooleanExtractor
from domain.models import IntentResult, FaqResult

class IntentClassifier:
    def __init__(self, model: OnnxModelWrapper, repo: IntentRepository, config: dict, extractors: Dict[str, Any]) -> None: ...

    async def classify_intent(
        self,
        text: str,
        expected_intents: List[str],
        previous_leader: Optional[str] = None
    ) -> Optional[IntentResult]: ...

    async def find_faq_answer(self, text: str) -> Optional[FaqResult]: ...

Требования:
	•	Косинус: cos(u,v) = (u·v) / (||u||*||v||). Векторы уже нормализованы → просто dot.
	•	Скоринг кандидатов: либо против центроидов интентов, либо максимальный скор среди фраз интента (конфигurable). По умолчанию центроид.
	•	Ворота подтверждения:
	1.	score > config["thresholds"]["confidence"]
	2.	score - score_second > config["thresholds"]["gap"]
	3.	previous_leader (если передан) совпадает с текущим лидером
	•	Извлечение сущностей (если в метаданных интента есть entity):
	•	entity: { "type": "number", "parser": "simple_numeric", "required": true }
	•	если required=True и не извлекли → return None.
	•	Возвращать IntentResult(intent_id, score, entities, current_leader=intent_id) либо None.
	•	find_faq_answer: косинус к FAQ-вопросам (repo.get_all_faq_vectors()), вернуть FaqResult при превышении config["faq"]["confidence"].

8) Критерии приёмки
	•	classify_intent даёт стабильный лид на повторных вызовах с тем же текстом (stateless).
	•	Latency (на CPU, локально): <100мс на запрос при D≈384/768, K≈1–10 фраз/интент, M≈10–30 интентов.
	•	Логи JSON: intent.classify_start/finish, faq.search_start/finish, со временем и размерами.

⸻

📄 File 2 — SPEC-IC-2-Scripts-and-Model.md

Офлайн-скрипты: скачивание модели, подготовка бэкапа эмбеддингов, бенчмарки

0) Контекст

Нужны боевые скрипты в root/scripts/, которые работают с реальными файлами клиента:
	•	configs/intents.json, configs/dialogue_map.json.
	•	Скачивают модель в models/our_model/.
	•	Обогащают проект бэкапом эмбеддингов configs/intents_backup.pkl.
	•	Замеряют и логируют задержки.

1) Дерево

project_root/
├─ .env                           # добавим EMB_MODEL_PATH=/abs/path/to/models/our_model
├─ models/
│  └─ our_model/                  # папка с ONNX моделью
├─ configs/
│  ├─ intents.json
│  ├─ dialogue_map.json
│  └─ intents_backup.pkl          # создаёт prepare_embeddings.py
└─ scripts/
   ├─ download_model.py           # скачивание/проверка модели + запись в .env
   ├─ prepare_embeddings.py       # векторизация интентов/FAQ и pkl-бэкап
   └─ benchmark_embed.py          # замер латентностей embed() и поиск по интентам

2) Зависимости (scripts)
	•	huggingface_hub>=0.23 (для загрузки модели) — или предоставь локальный архив/папку
	•	python-dotenv>=1.0 (чтение/запись .env)
	•	runtime зависимости ядра (см. File 1)

3) scripts/download_model.py

Задача: скачать (или скопировать) модель в models/our_model, пробросить абсолютный путь в .env → EMB_MODEL_PATH.

Импорты:

from __future__ import annotations
import argparse, os, sys, shutil
from pathlib import Path
from huggingface_hub import snapshot_download
from dotenv import set_key, dotenv_values

CLI:
	•	--repo-id (напр. intfloat/e5-small-v2-onnx) или --from-dir /path/to/local_model
	•	--target models/our_model

Логика:
	1.	Если --from-dir → рекурсивно скопировать в --target (перезаписать).
	2.	Иначе snapshot_download(repo_id, local_dir=target, local_dir_use_symlinks=False).
	3.	Получить abs_path = str(Path(target).resolve()), записать в .env ключ EMB_MODEL_PATH.
	4.	Напечатать JSON-лог: {"event":"model_ready","path":abs_path}.

Приёмка: файл .env содержит корректный EMB_MODEL_PATH, папка модели существует и доступна.

4) scripts/prepare_embeddings.py

Задача: прочитать configs/intents.json (+опц. FAQ из configs/dialogue_map.json), векторизовать, сохранить configs/intents_backup.pkl.

Импорты:

from __future__ import annotations
import os, json, time, argparse, logging, pickle
from pathlib import Path
from dotenv import dotenv_values
import numpy as np

from intent_classifier.model_wrapper import OnnxModelWrapper
from intent_classifier.repository import IntentRepository

CLI:
	•	--intents configs/intents.json
	•	--dialogue configs/dialogue_map.json (опционально — для FAQ раздела)
	•	--output configs/intents_backup.pkl
	•	--batch 64 (размер партии для embed)
	•	--device cpu|cuda (дефолт cpu)

Логика:
	1.	Прочитать .env, взять EMB_MODEL_PATH (abort, если отсутствует).
	2.	Загрузить интенты: intents["intents"][intent_id]["phrases"].
	•	Нормализовать пробелы; "{number}" не заменяем (это шаблон).
	3.	Собрать FAQ (если есть): dialogue_map["faq"] или иной раздел (если договоримся) — опционально, можно пропустить.
	4.	Батчами вызвать await model.embed(phrases) (в скрипте можно через asyncio.run).
	5.	Сформировать vectors[intent_id] = np.ndarray[K,D] и centroids[intent_id] = mean(axis=0).
	6.	Сохранить pickle с полями (см. File 1).
	7.	Логировать JSON-события:
	•	prepare_start, embed_batch_done {batch_idx, batch_size, ms}
	•	intent_ready {intent_id, phrases, D}
	•	backup_saved {path, size_bytes}

Приёмка: configs/intents_backup.pkl создаётся и читается repo.load_from_backup() без ошибок.

5) scripts/benchmark_embed.py

Задача: замерить латентности end-to-end: embed одной фразы, embed батча, классификация против N интентов (через центроиды), логировать JSON.

Импорты:

from __future__ import annotations
import os, json, time, argparse, logging
from pathlib import Path
import numpy as np
from dotenv import dotenv_values

from intent_classifier.model_wrapper import OnnxModelWrapper
from intent_classifier.repository import IntentRepository
from intent_classifier.classifier import IntentClassifier
from intent_classifier.entity_extractors import SimpleNumericExtractor, BooleanExtractor

CLI:
	•	--backup configs/intents_backup.pkl
	•	--device cpu|cuda
	•	--text "давайте 500000"
	•	--expected confirm_yes,provide_number,confirm_no
	•	--repeat 20

Логика:
	1.	Поднять модель из .env["EMB_MODEL_PATH"].
	2.	repo.load_from_backup(--backup).
	3.	Инициализировать IntentClassifier(config={"thresholds":{"confidence":0.4,"gap":0.05}, "faq":{"confidence":0.55}}).
	4.	Замерить:
	•	t_embed_single (повторно N раз → p50/p95)
	•	t_embed_batch (синтетический батч из 32/64 одинаковых строк)
	•	t_classify (повторно N раз)
	5.	Печатать JSON-события:
	•	{"event":"embed_single","ms":...}
	•	{"event":"embed_batch","n":64,"ms":...}
	•	{"event":"classify","intent": "...","score":...,"ms":...}
	•	финальный свод: {"event":"summary","p50":...,"p95":...}

Приёмка: На CPU p50 по classify укладывается в ~<100мс (ориентир), все шаги логируются.

⸻

📄 File 3 — SPEC-IC-3-Manual-E2E-Test.md

Ручной e2e-тест IntentClassifier (без pytest), на реальном скрипте клиента

0) Контекст

Мы тестируем реальную логику на реальных configs/intents.json и configs/dialogue_map.json, без синтетики. Нужен один исполняемый файл, который:
	•	Загружает модель (из .env), бэкап векторов (intents_backup.pkl).
	•	Прогоняет сценарии распознавания: подтверждения, числа, несовпадения, стабильность previous_leader.
	•	Замеряет латентность и логирует JSON.

1) Файл и дерево

project_root/
└─ intent_classifier/
   └─ test/
      ├─ manual_test_intents.py         # этот файл пишем
      └─ test_data/
         └─ phrases.txt                 # (опц.) вручную добавляем фразы для стресс-теста

2) Импорты (жёстко)

from __future__ import annotations
import asyncio, json, time, logging, argparse
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import dotenv_values

from intent_classifier.model_wrapper import OnnxModelWrapper
from intent_classifier.repository import IntentRepository
from intent_classifier.classifier import IntentClassifier
from intent_classifier.entity_extractors import SimpleNumericExtractor, BooleanExtractor

3) CLI
	•	--backup configs/intents_backup.pkl
	•	--intents configs/intents.json
	•	--device cpu|cuda
	•	--repeat 5
	•	--cases basic,missing_entity,stability,faq (через запятую; по умолчанию все)

4) Сценарии, которые обязаны быть реализованы
	1.	BASIC
	•	Входы:
	•	"Да" → среди expected (confirm_yes, confirm_no, provide_number) должен победить confirm_yes (если пороги ОК).
	•	"пусть будет 500000" → provide_number с entities={"value":500000}.
	•	Логи:
	•	{"event":"case_basic","step":"confirm_yes","status":"ok","score":...,"ms":...}
	•	{"event":"case_basic","step":"provide_number","status":"ok","entities":{"value":500000},"ms":...}
	2.	MISSING_ENTITY
	•	Текст без числа, но в expected только provide_number → результат None.
	•	Лог: {"event":"case_missing_entity","status":"none","reason":"entity_not_extracted"}
	3.	STABILITY (previous_leader)
	•	3 подряд вызова на близких фразах:
	•	partial1: “да” → лидер confirm_yes
	•	partial2: “да подтверждаю” → лидер должен совпасть с previous_leader (confirm_yes)
	•	final: “да всё верно” → лидер совпадает
	•	Если на шаге 2 лидер иной → лог {"event":"case_stability","status":"fail","prev":"...","now":"..."}
	4.	FAQ (если есть в бэкапе)
	•	Текст из домена FAQ → find_faq_answer возвращает FaqResult со score >= config["faq"]["confidence"].
	•	Лог: {"event":"case_faq","qid":"...","score":...,"ms":...}
	•	Если FAQ не настроен — лог {"event":"case_faq","skipped":true}

5) Каркас теста
	•	Настроить logging.basicConfig(level=logging.INFO, format="%(message)s").
	•	JSON-логгер:

def jlog(event: str, **fields):
    logging.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


	•	Загрузка модели:

env = dotenv_values()
model_path = env.get("EMB_MODEL_PATH")
if not model_path: jlog("error", msg="EMB_MODEL_PATH missing in .env"); return
model = OnnxModelWrapper(model_path, device=args.device)


	•	repo.load_from_backup(args.backup); инициализация IntentClassifier(config=...).

6) Метрики

Для каждого вызова:
	•	ms_total (весь classify_intent)
	•	внутри (опц., через внутренние логи ядра) — ms_embed, ms_score.

В конце:
	•	свод: p50/p95 classify_intent для BASIC-кейса.
	•	{"event":"summary","p50_ms":...,"p95_ms":...,"n":...}

7) Критерии приёмки
	•	Скрипт запускается одной командой:

python intent_classifier/test/manual_test_intents.py \
    --backup configs/intents_backup.pkl \
    --intents configs/intents.json \
    --device cpu \
    --repeat 10


	•	Печатает только JSON-строки.
	•	BASIC проходит, STABILITY удерживает лидера, MISSING_ENTITY → None, FAQ — по конфигу.
	•	p50 classify_intent ≈ <100мс на CPU (ориентир).

