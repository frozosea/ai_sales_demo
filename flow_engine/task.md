✅ File 1 — SPEC-FE-1-Core-Engine.md

FlowEngine v2 — ядро (engine.py) + минимальные модели

Контекст

FlowEngine — «мозг» сценария: по intent_id и entities выбирает переход, исполняет execute_code над SessionState и возвращает новый state или ошибку. Требования: отказоустойчивость, валидация данных, атомарность обновлений.

Область работ
	•	flow_engine/engine.py — класс FlowEngine
	•	Зависимости:
	•	stdlib: json, copy, dataclasses, typing, pathlib, logging
	•	внутренние типы (импорты см. ниже)

Внешние контракты (импорты)

Предполагаем наличие общих моделей (как в дереве проекта):

# ВНИМАНИЕ: использовать ровно такие импорты
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Literal

# domain/models.py — уже существует в проекте
from domain.models import SessionState  # dataclass: call_id, current_state_id, variables, state_history, previous_intent_leader, turn_state
from domain.models import FlowResult    # dataclass: status: Literal['SUCCESS','EXECUTION_ERROR','MISSING_ENTITY']; updated_session: Optional[SessionState]

Если FlowResult нет — генератору разрешено создать локальный fallback в flow_engine/engine.py с той же сигнатурой (на время разработки), но в проде использовать общий.

Структура проекта (фрагмент)

project_root/
└─ flow_engine/
   ├─ __init__.py
   ├─ engine.py                 # ТО, что пишем здесь
   ├─ utils.py                  # Будет реализовано в SPEC-FE-2
   └─ test/
      ├─ manual_test_flow_engine.py   # Будет реализовано в SPEC-FE-3
      └─ test_data/
         └─ dialogue_map_customer.json  # Скрипт заказчика (вставим вручную)

Требования к FlowEngine

Инициализация

class FlowEngine:
    def __init__(self, dialogue_map_path: str):
        """
        - Загружает JSON (UTF-8) → self.dialogue_map: dict
        - Достает раздел 'dialogue_flow' (обязателен)
        - Валидирует карту (через utils.validate_dialogue_map)
        - Готовит индекс переходов для быстрого доступа (self._states)
        - Логгер: logging.getLogger("flow_engine")
        """

Публичный метод

async def process_event(
    self,
    session_state: SessionState,
    intent_id: str,
    entities: Optional[Dict[str, Any]] = None
) -> FlowResult:
    """
    Контракт:
    - Самодостаточный: принимает любые entities, сам проверяет их пригодность под переход.
    - Находит state по session_state.current_state_id.
    - Ищет переход по intent_id в state['transitions'].
      - Если нет перехода → SUCCESS без изменения state (мягкая деградация) ИЛИ вернуть EXECUTION_ERROR (решение: мягкая деградация).
    - Если у перехода есть execute_code:
       * Перед выполнением — валидация наличия обязательных сущностей (эвристика: ищем обращения вида entities['xxx'] в коде и проверяем присутствие).
       * Если сущности отсутствуют → MISSING_ENTITY.
       * Безопасный exec (через utils.safe_exec), атомарно: работаем на copy.deepcopy(session_state), при успехе — коммит результата.
    - Применяет next_state: session_state.current_state_id = <next_state>.
    - Добавляет state_history.append(next_state).
    - Возвращает FlowResult('SUCCESS', updated_session=session_state) либо 'MISSING_ENTITY'/'EXECUTION_ERROR'.
    """

Приватные помощники (минимум)

def _get_current_state_block(self, session_state: SessionState) -> Dict[str, Any]: ...
def _get_transition(self, state_block: Dict[str, Any], intent_id: str) -> Optional[Dict[str, Any]]: ...
def _extract_required_entity_names(self, execute_code: str) -> List[str]:
    """
    Примитив: парсим подстроки вида entities['...'] или entities["..."] → список уникальных ключей.
    """

Безопасность выполнения
	•	Код исполняем только через utils.safe_exec(session, entities, user_message=None) (реализация в SPEC-FE-2).
	•	Нельзя позволять import, open, сетевые операции. safe_exec обязан резать опасные токены (см. SPEC-FE-2).

Приёмка
	•	FlowEngine.__init__ падает с логом до старта звонка, если карта невалидна.
	•	process_event:
	•	Возвращает MISSING_ENTITY при недостающей сущности.
	•	Возвращает EXECUTION_ERROR при ошибке в execute_code.
	•	Возвращает SUCCESS и переносит состояние корректно.
	•	Логирование: INFO — успешные переходы (from_state → intent → next_state), WARNING — отсутствующий переход, ERROR — ошибки exec/валидации.

⸻

✅ File 2 — SPEC-FE-2-Validator-and-Utils.md

FlowEngine v2 — валидатор карты и безопасное исполнение (utils.py) + CLI-валидатор

Контекст

Нужно упасть при старте, если карта битая. Нужен безопасный exec для execute_code, чтобы не убиться на демо. Всё — без внешних зависимостей.

Область работ
	•	flow_engine/utils.py — валидация карты и безопасный exec
	•	scripts/validate_dialogue_map.py — CLI-проверка (использует utils)
	•	Зависимости: stdlib re, json, ast, typing, logging, pathlib, argparse, copy

Импорты (жёстко)

from __future__ import annotations
import ast
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import copy

API flow_engine/utils.py

def validate_dialogue_map(dialogue_map: Dict[str, Any]) -> List[str]:
    """
    Проверяет:
      - Наличие ключа 'dialogue_flow' (dict)
      - Каждый state имеет 'transitions' (dict) и/или 'system_response' (dict)
      - Для каждого transition:
          * string next_state присутствует в dialogue_flow
          * execute_code, если есть — синтаксически валиден (ast.parse)
      - Нет зацикливания сам-на-себя без условий (эвристика: если единственный переход — на самого себя и нет long_operation)
    Возвращает список строк-ошибок; пусто — валидно.
    """

def check_exec_valid(execute_code: str) -> Optional[str]:
    """
    ast.parse(execute_code) и статическая проверка на запрещённые токены:
      - 'import', 'open', 'exec', 'eval', '__', 'os.', 'sys.', 'subprocess', 'socket', 'http', 'requests'
      - доступ к builtins сверх whitelists
    Возврат: None если ок, иначе строка-ошибка.
    """

def safe_exec(execute_code: str, session: Dict[str, Any], entities: Optional[Dict[str, Any]], user_message: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Безопасное исполнение фрагмента:
      - Перед выполнением: check_exec_valid()
      - Сбор окружения:
          locals = {'session': session, 'entities': entities or {}, 'user_message': user_message}
          globals = {'__builtins__': { 'len': len, 'min': min, 'max': max, 'sum': sum, 'abs': abs, 'round': round, 'range': range }}
      - Выполняем на deepcopy(session) в вызывающей стороне (рекомендуемая схема: вызывающий готовит копию).
      - Ловим любые исключения → (False, "error...")
      - Успех → (True, None)
    """

CLI-валидатор (scripts/validate_dialogue_map.py)
	•	Аргументы: --path configs/dialogue_map.json
	•	Загружает JSON, вызывает validate_dialogue_map.
	•	Печатает:
	•	«VALID» и exit(0) если ошибок нет,
	•	или JSON-массив ошибок и exit(1).

Приёмка
	•	На реальном «скрипте заказчика» (вставленном JSON) — отчёт об ошибках формата: ["state 'X' missing transitions", "transition 'provide_number' -> unknown state 'Y'"].
	•	check_exec_valid ловит запрещённые конструкции; safe_exec не падает процессом, всегда возвращает (ok, err).

⸻

✅ File 3 — SPEC-FE-3-Manual-E2E-Test.md

FlowEngine v2 — ручной e2e-тест сценария (без pytest)

Контекст

Никаких синтетических юнитов. E2E-скрипт, который имитирует реальный звонок, используя «скрипт заказчика» (карта состояний), прогоняет несколько путей, замеряет латентности и логирует JSON-события. Без Redis, без TTS/STT — чисто логика FlowEngine.

Область работ
	•	flow_engine/test/manual_test_flow_engine.py
	•	flow_engine/test/test_data/dialogue_map_customer.json — положить сюда JSON из сообщения заказчика (см. твой большой блок).
Если файла нет — тест логирует предупреждение и завершает работу.

Импорты (жёстко)

from __future__ import annotations
import asyncio
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from flow_engine.engine import FlowEngine
from domain.models import SessionState, FlowResult   # как в проекте

Сценарии, которые должен покрыть тест
	1.	Базовый позитивный путь: start_greeting -> confirm_yes -> pitch_offer -> ask_property_value -> provide_number -> confirm_property_value -> confirm_yes -> ask_inner_amount -> confirm_no -> summary_single -> confirm_yes -> address_confirmation -> finalize_policy
	•	Проверяем корректную установку переменных (например, property_value).
	2.	Отсутствующая сущность: в состоянии ask_property_value отправить provide_number без entities['value'] → ожидаем MISSING_ENTITY.
	3.	Ошибочный execute_code: искусственно подменить transition с ошибкой в коде → ожидаем EXECUTION_ERROR.
	4.	Rollback-кейс: confirm_property_value -> confirm_no должен удалить inner_amount (или откатить переменные, согласно карте).
	5.	Неизвестный intent в состоянии: отправить несуществующий intent → WARNING-лог, состояние не меняется.

Логирование
	•	Формат: одна строка — одно JSON-событие:
	•	{"event":"start","state":"start_greeting"}
	•	{"event":"transition","from":"X","intent":"provide_number","to":"Y","status":"SUCCESS","dt_ms":12.3}
	•	{"event":"missing_entity","state":"ask_property_value","intent":"provide_number"}
	•	{"event":"execution_error","error":"..."}
	•	{"event":"end","state":"finalize_policy"}

Скелет теста (обязательно реализовать)
	•	Аргументы (опц.): --map flow_engine/test/test_data/dialogue_map_customer.json
	•	Загрузчик карты: проверка наличия, иначе лог и выход.
	•	Инициализация FlowEngine(map_path).
	•	Создаём SessionState(call_id="demo", current_state_id="start_greeting", variables={"contact_name":"Иван", "address":"Москва, Тверская 1"}).
	•	Хелпер:

async def step(engine: FlowEngine, s: SessionState, intent: str, entities: Optional[Dict[str,Any]]=None) -> FlowResult:
    t0 = time.perf_counter()
    res = await engine.process_event(s, intent, entities)
    dt = round((time.perf_counter()-t0)*1000, 2)
    logging.info(json.dumps({"event":"transition", "from":s.state_history[-2] if len(s.state_history)>1 else "∅",
                             "intent":intent, "to":s.current_state_id, "status":res.status, "dt_ms":dt}))
    return res


	•	Последовательно прогоняем сценарии 1–5. Между кейсами сбрасываем SessionState в нужное состояние.
	•	По завершению — logging.info(json.dumps({"event":"done"})).

Приёмка
	•	Скрипт запускается python flow_engine/test/manual_test_flow_engine.py и печатает только JSON-строки.
	•	На позитивном пути — все статусы SUCCESS, время шага < ~10–20ms локально.
	•	На негативных — корректные события missing_entity/execution_error.

⸻

Мини-Tree (для README спринта)

project_root/
├─ flow_engine/
│  ├─ __init__.py
│  ├─ engine.py                      # SPEC-FE-1
│  ├─ utils.py                       # SPEC-FE-2
│  └─ test/
│     ├─ manual_test_flow_engine.py  # SPEC-FE-3
│     └─ test_data/
│        └─ dialogue_map_customer.json
├─ scripts/
│  └─ validate_dialogue_map.py       # SPEC-FE-2 (CLI)
└─ domain/
   └─ models.py                      # SessionState, FlowResult (как в твоём дереве)

Быстрый запуск спринта

# 1) Подложи карту
cp path/to/customer.json flow_engine/test/test_data/dialogue_map_customer.json

# 2) Проверка карты (CLI)
python scripts/validate_dialogue_map.py --path flow_engine/test/test_data/dialogue_map_customer.json

# 3) E2E логики FlowEngine
python flow_engine/test/manual_test_flow_engine.py
