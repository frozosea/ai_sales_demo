# Модуль llm: Спецификация и План Реализации (обновл.)

Этот документ является финальной спецификацией для модуля **llm**. Он описывает роль в системе, архитектуру, жизненный цикл, зависимости и детальный план реализации.

-----

## 1. Контекст и Цель

### 1.1. Роль в системе

Модуль **llm** — креативное ядро системы. Задача: генерировать ответы предсказуемо, безопасно и с низкой задержкой, управляя диалоговым контекстом, промпт-инжинирингом, потоковым выводом и фоновыми оптимизациями.

### 1.2. Потребитель (Consumer)

Единственный потребитель: **Orchestrator**.

### 1.3. Жизненный цикл (Lifecycle)

1.  **Создание**: на каждый новый звонок **Orchestrator** создаёт один экземпляр `ConversationManager`.
2.  **Использование**: `ConversationManager` живёт весь звонок. На вход принимает финализированные реплики пользователя, на выход отдаёт поток токенов/чанков ответа.
3.  **Завершение**: при окончании звонка **Orchestrator** обязан вызвать `await manager.shutdown()`. Метод гарантирует корректную отмену фоновых задач (суммаризация и пр.) и закрытие соединений.

### 1.4. Configs

**`config.yml`**:

```yaml
llm:
  api_key: "sk-..."
  models:
    main: "gpt-4-turbo"
    summarization: "gpt-3.5-turbo"
  context_window_size: 8192
  dual_context:
    warmup_threshold_ratio: 0.5   # при 50% запускаем подготовку резервного контекста
    handover_threshold_ratio: 0.9 # при 90% выполняем мгновенную смену
  keep_alive_interval_sec: 45
  http_timeout_sec: 30
```

**`prompts.yml`**:

```yaml
system_prompt: |
  Ты — первоклассный, вежливый и очень быстрый ИИ-ассистент по продажам...
response_format_instruction: |
  Твой ответ ДОЛЖЕН БЫТЬ в формате JSON...
summarization_prompt: |
  Ты — эксперт по сжатию текста. Суммаризируй следующий диалог...
```

> *Примечание по консистентности: во всех упоминаниях ниже используются именно ключи `models.main` и `models.summarization` из `config.yml`.*

-----

## 2. Архитектура и Зависимости

### 2.1. Стратегия управления контекстом: Dual-Context Handover

Ключ к стабильной скорости ответа на длинных диалогах.

  * **Внешний контракт**: **Orchestrator** вызывает один метод `process_user_turn(final_user_text)`.
  * **Инкапсуляция**: `ConversationManager` управляет состоянием и историей (user/assistant/system), а также переключениями контекстов.
  * **Фоновая оптимизация**: при достижении `warmup_threshold_ratio` менеджер запускает создание `StandbyContext` (суммаризация активного).
  * **Мгновенное переключение**: при достижении `handover_threshold_ratio` выполняется атомарная замена `ActiveContext` → `StandbyContext`, без пауз в основном потоке.
  * **Контроллер**: логику порогов, подготовки и атомарной смены ведёт `DualContextController` (см. ниже).

### 2.2. Зависимости

  * **Внешние**: `openai` (или совместимый клиент), `pydantic`, `tiktoken`, `httpx`. Опционально — `instructor` для структурированного ответа.
  * **Внутренние интерфейсы**:
      * `domain.interfaces.cache.AbstractCache` — кэширование суммаризаций по `session_id`.
      * (Опционально) счётчик токенов на базе `tiktoken` для прогнозирования порогов.

### 2.3. Классы и ответственность (уровень архитектуры)

  * **`ConversationManager`** — главный фасад для **Orchestrator**: принимает текст, стримит ответ, управляет состоянием диалога и жизненным циклом.
  * **`DualContextController`** — отвечает за подготовку `StandbyContext` и атомарный `handover` по порогам; не взаимодействует с сетью напрямую.
  * **`LLMContext`** — инкапсулирует историю и сборку промптов, считает/оценивает токены, отдаёт срез истории для суммаризации.
  * **`OpenAILLMClient`** (или другой поставщик) — потоковый вызов модели и парсинг структурированного стрима.
  * **`LLMConnectionManager`** — держит тёплый HTTP-клиент, keep-alive, таймауты, завершение.

-----

## 3. Детальный План Реализации

### 3.1. Пакет domain: Модели и Интерфейсы

#### 3.1.1. `domain/models.py`

  * `Role = Literal["user","assistant","system"]`.
  * `ConversationMessage` (TypedDict): `{ role: Role, content: str }`.
  * `ConversationHistory` (TypeAlias) = `List[ConversationMessage]`.
  * `LLMStreamChunk` (dataclass, `slots=True`):
      * `text_chunk: str`
      * `is_final_chunk: bool = False`
      * метаданные первого чанка: `is_safe: Optional[bool]`, `aggression_score: Optional[int]`
  * `LLMStructuredResponse` (Pydantic):
      * `internal_thought: str`
      * `is_safe: bool`
      * `answer: str`

> *Консистентность: поток от клиента маппится в `LLMStreamChunk` (наружу), а внутри клиент формирует объекты, совместимые с `LLMStructuredResponse`.*

#### 3.1.2. `domain/interfaces/llm.py`

```python
# Концептуальные контракты (без кода)

class LLMConnectionManager(abc.ABC):
  # Держит один httpx.AsyncClient c headers/Auth и keep-alive.
  # Консистентность: всегда возвращает один и тот же тёплый клиент.
  async def get_client(self) -> httpx.AsyncClient: ...
  async def shutdown(self) -> None: ...
  async def _keep_alive_ping(self) -> None: ...
  # Параметры интервала и таймаутов берёт из config.llm

class AbstractLLMClient(abc.ABC):
  # Возвращает поток Pydantic-объектов response_model, собранных из стрима LLM.
  async def stream_structured_generate(
      self,
      http_client: httpx.AsyncClient,
      full_prompt: str,
      model: str,
      response_model: Type[BaseModel]
  ) -> AsyncGenerator[BaseModel, None]: ...

class AbstractLLMContext(abc.ABC):
  # Принимает словарь промптов (из prompts.yml) и ограничения окна.
  def __init__(self, prompt_config: dict, max_tokens: int): ...
  def add_message(self, message: ConversationMessage) -> None: ...
  def build_prompt(self) -> str: ...
  def build_summary_prompt(self, history: ConversationHistory) -> str: ...
  def get_history_for_summary(self) -> ConversationHistory: ...
  def estimate_usage_ratio(self) -> float: ...
  # estimate_usage_ratio ∈ [0..1] – оценка заполнения окна контекста

class AbstractConversationManager(abc.ABC):
  # Инициализирует connection_manager, llm_client, active_context.
  def __init__(self, call_config: dict, cache: AbstractCache, session_id: str): ...

  # Главный метод: принимает финальный текст пользователя, стримит LLMStreamChunk.
  async def process_user_turn(self, final_user_text: str) -> AsyncGenerator[LLMStreamChunk, None]: ...

  # Завершение: отмена фоновых задач, закрытие соединений.
  async def shutdown(self) -> None: ...

  # Вспомогательное: построить standby-контекст (в фоне).
  async def _build_standby_context(self) -> None: ...
```

> **Исправления консистентности:**
>
>   * `LLMConnectionManager.get_client()` теперь `async` и возвращает один общий `httpx.AsyncClient`.
>   * `OpenAILLMClient` не принимает `api_key` напрямую — он получает готовый `http_client` из `LLMConnectionManager`.
>   * `AbstractLLMClient.stream_structured_generate(...)` всегда принимает `response_model`, `model` и `full_prompt`.

-----

### 3.2. Пакет llm: Реализация Логики

#### 3.2.1. `llm/client.py` — OpenAILLMClient

  * **Наследование**: `AbstractLLMClient`.
  * **Поведение**: потоковый вызов `models.main`/`models.summarization`; парсинг стрима в `response_model` (например, `LLMStructuredResponse`); маппинг первых метаданных в первый `LLMStreamChunk`.

#### 3.2.2. `llm/context.py` — LLMContext

  * **Назначение**: хранит историю, считает/оценивает заполнение окна, собирает промпты.
  * **Методы**:
      * `__init__(prompt_config, max_tokens)`
      * `add_message(message)`
      * `build_prompt()` — комбинирует `system_prompt` + история + `response_format_instruction`.
      * `get_history_for_summary()` — отдаёт релевантный срез для сжатия.
      * `build_summary_prompt(history)` — использует `summarization_prompt`.
      * `estimate_usage_ratio()` — оценка доли окна (на основе `tiktoken` или эвристики).

#### 3.2.3. `llm/dual_context.py` — DualContextController (НОВОЕ)

  * **Роль**: инкапсулирует стратегию `Dual-Context Handover`.
  * **Состояние**:
      * `active_context: LLMContext`
      * `standby_context: Optional[LLMContext] = None`
      * `warmup_task: Optional[asyncio.Task] = None`
      * пороги из `config.llm.dual_context`
  * **Методы**:
      * `on_user_message(message)` — добавляет в `active_context`, возвращает текущую `usage_ratio`.
      * `should_warmup(usage_ratio)` — сравнение с `warmup_threshold_ratio`.
      * `should_handover(usage_ratio)` — сравнение с `handover_threshold_ratio`.
      * `set_standby(context)` — установить готовый `standby_context`.
      * `perform_handover()` — атомарно меняет `active_context` <- `standby_context`, `standby_context = None`.
      * `cancel_warmup_if_running()` — отмена незавершённой подготовки.
  * **Требования к атомарности**: `handover` выполняется без модификации истории в процессе; любые новые сообщения после `handover` пишутся уже в новый `active_context`.

#### 3.2.4. `llm/manager.py` — ConversationManager

  * **Наследование**: `AbstractConversationManager`.
  * **Состав**:
      * `self.connection_manager: LLMConnectionManager`
      * `self.llm_client: AbstractLLMClient`
      * `self.dual_ctx: DualContextController`
      * `self.cache: AbstractCache`
      * `self._background_tasks: set[asyncio.Task]`
      * `self._session_id_hash: str` (ключ для кэша суммаризаций)
  * **Публичные методы**:
      * `__init__(config, llm_client, cache, session_id)` — инициализация всего, создание `active_context` и `dual_ctx`.
      * `async process_user_turn(final_user_text)`:
        1. Добавить сообщение пользователя через `dual_ctx.on_user_message(...)`.
        2. Проверить `usage_ratio` → при необходимости стартовать `warmup_task` (если нет) через `_initiate_standby_creation()`.
        3. Собрать `prompt = active_context.build_prompt()`.
        4. Вызвать `llm_client.stream_structured_generate(http_client, prompt, models.main, LLMStructuredResponse)`.
        5. На первом чанке пробросить метаданные (`is_safe`, и т.п.) в `LLMStreamChunk`.
        6. Параллельно с приёмом токенов периодически оценивать `usage_ratio`; при достижении порога выполнить `dual_ctx.perform_handover()` (если `standby_context` готов).
        7. По окончании стрима — финализировать ответ: сохранить полную реплику ассистента в текущий `active_context` (после `handover` записываем уже в новый).
      * `async shutdown()` — корректно завершает фоновые задачи и соединения.
      * `async abort_generation()` - корректно останавливает стриминг чтобы не жечь токены, и безопасно завершить стриминг, не нарушая работу для следующего вызова
  * **Приватные методы**:
      * `_initiate_standby_creation()` — если нет активной задачи, запускает `_build_standby_context()` в фоне.
      * `_build_standby_context()` — берёт `history = active_context.get_history_for_summary()`, проверяет кэш по `session_id_hash`; если нет — строит `summary_prompt`, вызывает `llm_client.stream_structured_generate(..., models.summarization, ...)` , собирает `summary` и формирует новый `LLMContext` как `standby`. Кэширует `summary`.
      * `_stream_and_capture_response(prompt)` — обёртка для стрима наружу + накопление полного ответа (для истории).

> *Консистентность handover: handover возможен в любой момент после готовности `standby_context`. Если handover произошёл во время стрима ответа ассистента — оставшуюся часть ответа добавляем уже в новый `active_context` (ответ логически относится к текущему состоянию диалога).*

-----

## 4. Поток данных и контракты

  * **Вход**: `final_user_text: str` (финальная реплика от ASR/Orchestrator).
  * **Выход**: `AsyncGenerator[LLMStreamChunk]`:
      * первый чанк может содержать метаданные безопасности;
      * далее — последовательные текстовые чанки;
      * последний чанк — `is_final_chunk = True`.
  * **Структурный ответ внутри**: `LLMStructuredResponse` (стрим парсится в него, поле `answer` маппится на `text_chunk`).
  * **Кэш**: ключ — `hash(session_id)`, значение — последняя `summary` либо набор промежуточных суммаризаций.

-----

## 5. Управление ресурсами и устойчивость

  * **Connection keep-alive**: `LLMConnectionManager` делает лёгкий пинг каждые `keep_alive_interval_sec`.
  * **Фоновые задачи**: хранятся в `self._background_tasks` для централизованной отмены.
  * **Отмена и shutdown**: `shutdown()` отменяет warmup/summary-задачи, ждёт их завершения, закрывает HTTP-клиент.
  * **Дедупликация warmup**: новый `warmup` не стартует, если уже есть активный.
  * **Backpressure**: при перегрузке (медленный потребитель стрима) — буфер ограничен, излишки дропаются на грани токенизации (мелкие чанки, без разрыва JSON-структуры).

-----

## 6. Метрики и пороги

  * `estimate_usage_ratio()` обязателен для принятия решений `should_warmup`/`should_handover`.
  * Пороговые значения читаются из `config.llm.dual_context`.
  * **Метрики**: время до первого чанка, полная латентность ответа, частота `handover`, процент попаданий в кэш суммаризаций.

-----

## 7. Риски и деградации

  * **Если summarization-модель медленная** → `warmup` может не успеть: тогда `handover` откладывается до готовности `standby_context`.
  * **Если кэш недоступен** → продолжаем без кэша, но логируем деградацию.
  * **При ошибке в стриме основного ответа** — возвращаем `is_final_chunk=True` и пробрасываем сигнал в **Orchestrator**; контексты остаются валидными.

-----

## 8. Итоговые выравнивания (что было пофикшено)

  * Единые названия моделей: `models.main`, `models.summarization`.
  * Единый способ доступа к сети: `OpenAILLMClient` получает готовый `http_client` от `LLMConnectionManager`.
  * Единая сигнатура потокового клиента: `stream_structured_generate(http_client, full_prompt, model, response_model)`.
  * Добавлен `DualContextController` как явный владелец логики порогов и атомарного `handover`.
  * Прояснено, в какой контекст пишется хвост ответа при `handover` (в текущий `active`, т.е. после смены — уже в новый).
  * Формализованы правила фоновых задач, кэша и `shutdown`.

⸻

Быстрый старт (после реализации)

# deps
python -m pip install -U httpx pydantic tiktoken PyYAML redis python-dotenv

# ручной пробник стрима и TTFT
python llm/test/manual_probe_llm.py --config configs/config.yml --prompts configs/prompts.yml --text "Коротко объясни преимущества."

# e2e с кэшем суммаризаций
export REDIS_HOST=127.0.0.1 REDIS_PORT=6379 REDIS_DB=0
python llm/test/manual_test_llm_agent.py --config configs/config.yml --prompts configs/prompts.yml --session-id demo-123 --repeats 2