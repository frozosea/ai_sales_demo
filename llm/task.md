📄 File 1 — SPEC-LLM-1-Core.md

Модуль llm (ядро): ConnectionManager, Client (stream), Context, DualContext, Manager + базовая телеметрия

0) Контекст

Это ядро модуля llm. Цель — обеспечить предсказуемо быстрый потоковый ответ LLM с управлением контекстом (dual-context) и вшитыми точками измерения:
	•	время рукопожатия (handshake) менеджера соединений,
	•	сетевые задержки (до сервера и до первого токена),
	•	время до первого токена,
	•	среднее время ответа,
	•	заполнение контекста,
	•	время тёплого handover между контекстами.

В этом файле реализуются только базовые классы и «песочничные» раннеры. Тесты и интеграция — в отдельных задачах.

1) Дерево проекта (фрагмент)

project_root/
├─ configs/
│  ├─ config.yml            # llm.api_key, models.*, timeouts, dual_context
│  └─ prompts.yml           # system_prompt, response_format_instruction, summarization_prompt
├─ infra/
│  └─ redis_config.py       # уже реализовано в модуле cache спринта
├─ domain/
│  ├─ models.py             # Role, ConversationMessage, LLMStreamChunk, LLMStructuredResponse
│  └─ interfaces/
│     └─ llm.py             # контракты LLM*
└─ llm/
   ├─ __init__.py
   ├─ connection.py         # LLMConnectionManager (httpx AsyncClient + keep-alive)
   ├─ client.py             # OpenAILLMClient: stream_structured_generate(...)
   ├─ context.py            # LLMContext: история, build_prompt(), estimate_usage_ratio()
   ├─ dual_context.py       # DualContextController: warmup/handover
   └─ manager.py            # ConversationManager: фасад + фоновая суммаризация/кэш

2) Зависимости (runtime)
	•	httpx>=0.27
	•	pydantic>=2.7
	•	tiktoken>=0.7 (оценка токенов; допускается эвристика, но интерфейс оставить)
	•	PyYAML>=6.0 (чтение configs/prompts)
	•	redis>=5.0 (интеграция кэша — в другой задаче, но импорт интерфейса нужен)
	•	python-dotenv>=1.0 (опц., для .env)
	•	stdlib: asyncio, time, typing, dataclasses, contextlib, json, hashlib, logging

3) Контракты (обязательные импорты/типы)

domain/models.py (минимум):

from dataclasses import dataclass
from typing import Optional, Literal, TypedDict, List

Role = Literal["user", "assistant", "system"]

class ConversationMessage(TypedDict):
    role: Role
    content: str

ConversationHistory = List[ConversationMessage]

@dataclass(slots=True)
class LLMStreamChunk:
    text_chunk: str
    is_final_chunk: bool = False
    # first-chunk metadata
    is_safe: Optional[bool] = None
    aggression_score: Optional[int] = None

# Для client.stream_structured_generate(...) — разрешён любой Pydantic BaseModel
# Пример целевой структуры для стрима:
# class LLMStructuredResponse(BaseModel):
#     internal_thought: Optional[str] = None
#     is_safe: Optional[bool] = True
#     answer: str

domain/interfaces/llm.py (минимум сигнатур):

import abc
import httpx
from typing import AsyncGenerator, Type, List
from pydantic import BaseModel

class LLMConnectionManager(abc.ABC):
    async def get_client(self) -> httpx.AsyncClient: ...
    async def shutdown(self) -> None: ...

class AbstractLLMClient(abc.ABC):
    async def stream_structured_generate(
        self,
        http_client: httpx.AsyncClient,
        full_prompt: str,
        model: str,
        response_model: Type[BaseModel]
    ) -> AsyncGenerator[BaseModel, None]: ...

class AbstractLLMContext(abc.ABC):
    def add_message(self, message) -> None: ...
    def build_prompt(self) -> str: ...
    def build_summary_prompt(self, history) -> str: ...
    def get_history_for_summary(self): ...
    def estimate_usage_ratio(self) -> float: ...

class AbstractConversationManager(abc.ABC):
    async def process_user_turn(self, final_user_text: str) -> AsyncGenerator["LLMStreamChunk", None]: ...
    async def shutdown(self) -> None: ...

4) Реализация (краткие требования)

4.1. llm/connection.py — LLMConnectionManager
	•	Держит пул httpx.AsyncClient с (на каждый звонок у нас своя цепочка llm модуля, то есть соединения будут сделаны для каждого звонка):
	•	headers={"Authorization": f"Bearer {api_key}"}, timeout=config.llm.http_timeout_sec, http2=True. Прогревает модель делая handshanke и warmup, помимо этого отправляем пустой текст, чтоб модель всегда была готова к обработке. Работает на основе конфига, там указано время раз в которое надо прогревать модель. Соединение должно отдавать всегда прогретым где отправлен чанк. 
	•	Метрики (JSON-лог, logger="llm.conn"):
	•	conn_handshake_start/finish (ms): создание клиента,
	•	keep_alive_ping_start/finish (ms): лёгкий GET/POST ping (конфигурируемый endpoint, можно /v1/models).
	•	Обязательный if __name__ == "__main__"::
	•	читает .env/configs/config.yml,
	•	создаёт и закрывает клиент, печатает два JSON-события.

4.2. llm/client.py — OpenAILLMClient
	•	Метод stream_structured_generate(...):
	•	Формирует тело запроса (/v1/chat/completions или /responses — выбрать один маршрут и зафиксировать),
	•	Включает stream=True,
	•	Стрим читает чанками, на первом чанке фиксирует:
	•	t_first_token_ms (от отправки запроса до получения первого чанка),
	•	парсит первые метаданные (если есть) и прокидывает в вызывающий код через первый LLMStreamChunk.
	•	Логи logger="llm.client":
	•	request_send (ts),
	•	first_token (ms),
	•	chunk (size, seq),
	•	stream_end (total_ms, chunks).
	•	Обязательный if __name__ == "__main__"::
	•	моковый вызов (без реального ключа): строит фейковый AsyncGenerator из 3-4 чанков, печатает JSON-события.

4.3. llm/context.py — LLMContext
	•	Хранит историю: List[ConversationMessage].
	•	build_prompt() = system_prompt + история + response_format_instruction.
	•	estimate_usage_ratio():
	•	либо через tiktoken (реально),
	•	либо эвристика: символы/лимит.
	•	Лог logger="llm.context": usage_ratio (0..1) при каждом add_message.
	•	Обязательный if __name__ == "__main__"::
	•	грузит prompts.yml (фейковые значения ок), добавляет 2–3 сообщения, печатает prompt и ratio.

4.4. llm/dual_context.py — DualContextController
	•	Пороговые значения из config.yml: warmup_threshold_ratio, handover_threshold_ratio.
	•	Состояния: active_context, standby_context, warmup_task.
	•	События (JSON-логи logger="llm.dual"):
	•	warmup_start/ready,
	•	handover_perform (ms от warmup_ready до handover),
	•	warmup_cancelled.
	•	Обязательный if __name__ == "__main__"::
	•	эмуляция роста usage_ratio → запуск warmup → установка standby → handover.

4.5. llm/manager.py — ConversationManager
	•	Склеивает всё: connection → client → dual context → context.
	•	process_user_turn(text):
	•	добавляет user в active_context,
	•	проверяет usage_ratio → при необходимости warmup_start,
	•	собирает prompt → вызывает client.stream_structured_generate(...),
	•	на первом чанке логирует time_to_first_token_ms,
	•	стримит LLMStreamChunk наружу,
	•	по завершении собирает полный ответ, добавляет в текущий активный контекст (учесть возможный handover),
	•	возвращает финальный чанк с is_final_chunk=True.
	•	Логи logger="llm.manager":
	•	user_turn_start/finish,
	•	time_to_first_token_ms,
	•	response_total_ms,
	•	context_ratio_before/after,
	•	handover_ms_if_any.
	•	Обязательный if __name__ == "__main__"::
	•	моковый прогон: фейковый client (из client.py песочницы), context, dual-context — вывести 3–4 чанка и метрики.

5) Критерии приёмки
	•	Все пять файлов импортируются и запускаются по отдельности (песочницы не падают).
	•	Логи строго в JSON-однострочном формате.
	•	В client.py фиксируется time_to_first_token_ms.
	•	В dual_context.py фиксируется время от готовности standby до handover.
	•	В manager.py есть все целевые метрики.

⸻

📄 File 2 — SPEC-LLM-2-Manual-Probe.md

Ручной «пробник» стриминга LLM: метрики до первого токена, среднее время, сетевые задержки, handshake

0) Контекст

Нужен самостоятельный исполняемый файл для быстрой проверки без Orchestrator. Он делает реальный запрос к LLM-провайдеру (OpenAI-совместимый), собирает ключевые метрики, печатает логи и пишет сводный отчёт для людей.

1) Дерево

project_root/
└─ llm/
   └─ test/
      └─ manual_probe_llm.py     # этот файл

2) Зависимости
	•	Использует код из llm/ ядра (File 1).
	•	PyYAML, python-dotenv.
	•	.env должен содержать OPENAI_API_KEY (или совместимый ключ).

3) Что измеряем
	•	Handshake: время создания httpx.AsyncClient + первый лёгкий ping. А также время отправки пустого текста и получения сообщения. 
	•	Network RTT: t_send_request → t_socket_written (опционально) → t_first_byte (приблизительно через time перед/после await client.stream(...)).
	•	Time to First Token (TTFT): от request_send до первого чанка (не считаем время прогрева соединенрия). 
	•	Average total response: от request_send до конца стрима.
	•	Chunk rate: чанков/сек.
	•	Context usage: ratio до/после.
	•	Dual-context event timings: warmup_started → warmup_ready → handover.
	•	Сохранение отчёта: Markdown-файл с таблицей значений.

4) Формат логов (пример)

{"event":"handshake_start","ts":...}
{"event":"handshake_finish","ms":42.1}
{"event":"request_send","model":"gpt-4o-mini","ts":...}
{"event":"first_token","ttft_ms":612.7}
{"event":"chunk","i":1,"bytes":128}
{"event":"stream_end","total_ms":2123.5,"chunks":98}
{"event":"context_usage","before":0.31,"after":0.55}
{"event":"warmup_start","ratio":0.52}
{"event":"warmup_ready","ms":340.4}
{"event":"handover_perform","ms_since_ready":12.9}
{"event":"report_saved","path":"reports/llm_probe_2025-08-09T12-30-00.md"}

5) CLI

python llm/test/manual_probe_llm.py \
  --config configs/config.yml \
  --prompts configs/prompts.yml \
  --model main \
  --text "Привет! Дай короткое описание продукта." \
  --repeats 5 \
  --report-dir reports

6) Поведение скрипта
	1.	Загружает ключ из .env, конфиги config.yml/prompts.yml.
	2.	Создаёт LLMConnectionManager → логирует handshake.
	3.	Создаёт ConversationManager с пустой историей.
	4.	Делает repeats запусков:
	•	добавляет одно user сообщение,
	•	стримит ответ; на первом чанке фиксирует TTFT,
	•	собирает финальную длительность и число чанков.
	5.	Считает средние/медиану/р95 TTFT и total.
	6.	Пишет Markdown-отчёт (таблица, краткие выводы) в --report-dir.
	7.	Печатает report_saved (JSON-лог).
	8.	if __name__ == "__main__": — полноценный раннер с argparse, падать нельзя (если нет ключа — печатает JSON-ошибку и sys.exit(1)).

7) Критерии приёмки
	•	Скрипт запускается одной командой, создаёт reports/llm_probe_*.md.
	•	TTFT и total записаны как p50/p95 + среднее.
	•	Логи строго JSON-однострочные, отчёт — удобочитаемый Markdown.

⸻

📄 File 3 — SPEC-LLM-3-Manual-E2E-With-Cache.md

Ручной e2e-тест llm c Dual-Context + кэш суммаризаций (Redis) + метрики до первого аудио-чанка

0) Контекст

Это боевой интеграционный тест только для модуля llm, но с подключённым модулем cache (Redis). Мы:
	•	Прогоняем диалог с несколькими шагами.
	•	Проверяем работу Dual-Context (warmup → handover).
	•	Кэшируем суммаризации (summary:session:<hash>) и меряем cache hit/miss.
	•	Фиксируем время до первого токена и оцениваем, укладываемся ли в <800ms для демо.
	•	Логируем сетевые задержки, handshake, контекст, и сохраняем человекочитаемый отчёт.

1) Дерево

project_root/
├─ cache/
│  ├─ cache.py                     # RedisCacheManager (из прошлого спринта)
│  └─ test/
│     └─ manual_test_cache.py      # уже есть
└─ llm/
   └─ test/
      └─ manual_test_llm_agent.py  # этот файл

2) Зависимости
	•	Из File 1: llm/connection.py, llm/client.py, llm/context.py, llm/dual_context.py, llm/manager.py.
	•	redis>=5.0 (через infra/redis_config.RedisConfig + cache.cache.RedisCacheManager).
	•	PyYAML, python-dotenv.
	•	.env: OPENAI_API_KEY, REDIS_HOST/PORT/DB/PASSWORD.

3) Что именно проверяем
	1.	TTFT (Time to First Token) — критично.
	2.	Среднее время ответа (end-to-end).
	3.	Заполнение контекста по шагам.
	4.	Dual-context:
	•	когда стартовал warmup,
	•	когда стал готов standby,
	•	сколько занял handover.
	5.	Кэш суммаризаций:
	•	Первый длинный диалог → cache miss (суммаризация генерится и сохраняется),
	•	Повтор того же диалога → cache hit (суммаризация читается, время меньше).
	6.	Сетевые задержки и handshake.
	7.	Экспорт метрик: Markdown-отчёт + JSON-сырьё.

4) Сценарий диалога (пример)
	•	Step 1 (user): «Привет! Скажи в двух фразах, чем ты полезен клиентам страховой компании?»
	•	Step 2 (user): «А теперь в одном предложении объясни выгоды вежливо и без воды.»
	•	Step 3 (user): «Суммаризируй весь диалог списком из 3 пунктов.»
	•	Повторить Step 3 ещё раз (новая сессия или та же сессия, см. ключи кэша) для cache hit.

5) CLI

python llm/test/manual_test_llm_agent.py \
  --config configs/config.yml \
  --prompts configs/prompts.yml \
  --session-id demo-123 \
  --repeats 2 \
  --report-dir reports

6) Лог-события (обязательно)
	•	conn_handshake_*
	•	request_send, first_token, stream_end
	•	time_to_first_token_ms, response_total_ms
	•	context_usage (before/after)
	•	warmup_start, warmup_ready, handover_perform
	•	summary_cache_check {key, hit: bool, latency_ms}
	•	summary_cache_save {key, bytes, latency_ms}
	•	report_saved {path}

7) Как формируем ключи кэша
	•	session_hash = sha1(session_id.encode()).hexdigest()[:16]
	•	Ключ для суммаризаций: summary:session:{session_hash}

8) Поведение скрипта
	1.	Поднимает Redis через infra.redis_config.RedisConfig → RedisCacheManager.connect().
	2.	Создаёт ConversationManager с подключённым кэшем.
	3.	Прогоняет диалог один раз (ожидаемый miss по суммаризации).
	4.	Прогоняет повторный финальный шаг (ожидаемый hit).
	5.	Считает p50/p95 для TTFT и total (по всем шагам).
	6.	Пишет сводный Markdown-отчёт (таблица метрик + комментарии о попадании в цель <800ms по TTFT).
	7.	Закрывает кэш и соединения LLM.
	8.	if __name__ == "__main__": — полный раннер с argparse; при ошибке Redis/ключа — логирует JSON-ошибку и не валит процесс жёстко (возвращает код 1).

9) Критерии приёмки
	•	Скрипт создаёт два файла:
	•	reports/llm_agent_YYYYmmdd-HHMM.md (читаемый отчёт),
	•	reports/llm_agent_YYYYmmdd-HHMM.json (сырой дамп метрик).
	•	Логи — строго JSON в stdout.
	•	На втором прогоnе виден cache hit по ключу суммаризации.
	•	В отчёте есть явная строка: TTFT p50: ... ms (цель < 800 ms) — OK/FAIL.

10) Мини-скелет песочницы (внутри файла)

if __name__ == "__main__":
    # 1) argparse + загрузка конфигов/ключей
    # 2) connect Redis + create ConversationManager
    # 3) run scenario (steps) → collect metrics
    # 4) save reports (md + json)
    # 5) close/shutdown
    # Все шаги с try/except и JSON-логами
    pass



