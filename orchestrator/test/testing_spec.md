# Спецификация тестирования: Модуль Orchestrator (v3)

## 1. Цель тестирования

Основная цель — провести комплексное End-to-End (E2E) тестирование модуля `Orchestrator`, чтобы проверить его функциональность, производительность и отказоустойчивость в условиях, максимально приближенных к реальным.

**Ключевые аспекты для проверки:**
- **Корректность логики:** Правильное управление жизненным циклом звонка, координация модулей (`STT`, `IntentClassifier`, `FlowEngine`, `LLM`, `TTS`).
- **Отказоустойчивость:** Адекватная реакция на сбои в зависимых сервисах (gRPC, WebSocket, HTTP API).
- **Производительность:** Измерение ключевых задержек (TTFT, End-to-End response time).
- **Работа с аудио:** Корректное проигрывание плейлистов, филлеров и обработка перебиваний (barge-in).
- **Гибкость сценария:** Способность `FlowEngine` обрабатывать сложные диалоги с дигрессиями и форсированием.

---

## 2. Подготовка к тестированию

Перед запуском тестов необходимо подготовить окружение.

### 2.1. Установка зависимостей
Выполнить установку всех необходимых пакетов для всех модулей системы:
```bash
# General
pip install -U python-dotenv PyYAML pydantic redis

# Intent Classifier & Embeddings
pip install -U numpy onnxruntime transformers tokenizers optimum huggingface_hub

# LLM
pip install -U httpx tiktoken

# Yandex STT
pip install -U grpcio grpcio-tools requests
```

### 2.2. Конфигурация окружения
1.  Создайте файл `.env` в корне проекта на основе `.env.example`.
2.  Заполните все необходимые ключи API и идентификаторы:
    - `YC_IAM_TOKEN`: IAM-токен для Yandex.Cloud.
    - `YC_FOLDER_ID`: Идентификатор каталога в Yandex.Cloud.
    - `ELEVENLABS_API_KEY`: Ключ API для ElevenLabs.
    - `OPENAI_API_KEY`: Ключ API для OpenAI.
    - `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`: Параметры подключения к Redis.

### 2.3. Запуск подготовительных скриптов

Эти скрипты необходимо запустить в строгом порядке для подготовки моделей и данных.

1.  **Загрузка ML-модели для эмбеддингов:**
    ```bash
    python3 scripts/download_model.py --repo-id "intfloat/e5-small-v2-onnx" --target "models/e5-small-v2-onnx"
    ```
2.  **Генерация gRPC-стабов для Yandex STT:**
    ```bash
    python3 scripts/gen_speechkit_stubs.py
    ```
3.  **Подготовка векторов для Intent Classifier:**
    ```bash
    python3 scripts/prepare_embeddings.py --intents "configs/intents.json" --dialogue "configs/dialogue_flow.json" --output "configs/intents_backup.pkl"
    ```
4.  **Загрузка статических аудиофайлов в кэш (Redis):**
    *Предполагается, что аудио-филлеры и статические ответы лежат в `reports/audio_samples/`*
    ```bash
    python3 scripts/load_static_audio.py --audio-dir "reports/audio_samples/" --cache-prefix "static"
    ```
5.  **Валидация конфигурации диалога:**
    ```bash
    python3 scripts/validate_dialogue_map.py --dialogue "configs/dialogue_flow.json" --goals "configs/goals.json" --intents "configs/intents.json"
    ```
---

## 3. Тестовый сценарий: "Уклончивый клиент и технические сбои"

Этот сценарий имитирует сложный разговор, проверяя максимальное количество веток логики `Orchestrator`.

| Шаг | Действие пользователя (текст) | Мок-состояние / Симуляция сбоя | Ожидаемое поведение системы | Критерии проверки (в логах) |
|---|---|---|---|---|
| 1 | *(Начало звонка)* | - | `Orchestrator` запускается, проигрывает приветствие из `dialogue_map[start_greeting]`. | `event: "run_started"`, `event: "play_playlist", state: "start_greeting"`. |
| 2 | "Да, это я" | - | `IntentClassifier` -> `confirm_yes`. `FlowEngine` переходит к следующему шагу (сбор данных). `Orchestrator` проигрывает `ask_property_value`. | `event: "stt_final", text: "..."`, `event: "intent_classified", intent: "confirm_yes"`, `event: "flow_result", next_state: "ask_property_value"`. |
| 3 | "А что за компания?" | - | `IntentClassifier` -> `ask_company` (дигрессия). `FlowEngine` ставит основную задачу на паузу и отвечает на вопрос. | `event: "intent_classified", intent: "ask_company", type: "digression"`, `event: "task_stack_update", stack_size: 2, top_task: "handle_faq_company"`. |
| 4 | *(Во время ответа бота)* "Стой, хватит, какая цена?" | **Barge-in** | `Orchestrator` получает сигнал `barge_in`, отменяет `current_playback_task`, переключает `turn_state` в `USER_TURN`. | `event: "barge_in_detected"`, `event: "playback_task_cancelled"`. |
| 5 | "Какая цена говорю?" | - | `IntentClassifier` -> `demand_final_answer_cost` (форсирование). `FlowEngine` очищает стек от дигрессий, переводит основную задачу в режим `FORCED` и задает первый недостающий вопрос (`force_ask_property_value`). | `event: "intent_classified", intent: "demand_final_answer_cost", type: "forcing"`, `event: "task_mode_changed", task: "provide_total_price", mode: "FORCED"`, `event: "play_playlist", state: "force_ask_property_value"`. |
| 6 | "Пять миллионов" | **Сбой TTS** (симулируется в моке `TTSManager`) | `IntentClassifier` -> `provide_number`. `FlowEngine` пытается перейти к следующему вопросу, `Orchestrator` вызывает `TTSManager`, который падает. `Orchestrator` ловит `TTSConnectionError` и проигрывает `non_secure_response` из кеша. | `event: "tts_stream_failed"`, `event: "playing_fallback", key: "non_secure_response"`. |
| 7 | "Что-то у вас всё сломалось. Вообще, с кем я говорю?" | **Сбой LLM** (симулируется в моке `LLMManager`) | `IntentClassifier` не находит интент. `Orchestrator` вызывает `_handle_unscripted_flow`. `LLMManager` падает. `Orchestrator` ловит ошибку и проигрывает `non_secure_response`. | `event: "intent_not_found"`, `event: "unscripted_flow_started"`, `event: "llm_process_failed"`, `event: "playing_fallback", key: "non_secure_response"`. |
| 8 | "Это небезопасно?" | **LLM отвечает небезопасным контентом** | `IntentClassifier` не находит интент. `_handle_unscripted_flow` запущен. `LLMManager` стримит первый чанк с `is_safe: false`. `Orchestrator` прерывает LLM и проигрывает `non_secure_response`. | `event: "llm_chunk_received", is_safe: false`, `event: "llm_generation_aborted"`, `event: "playing_fallback", key: "non_secure_response"`. |
| 9 | "Всё, мне не интересно, до свидания." | - | `IntentClassifier` -> `provide_reject_reason` (терминальный). `FlowEngine` очищает стек, ставит финальную задачу. `Orchestrator` проигрывает прощание и выставляет `self.call_ended = True`. | `event: "intent_classified", intent: "provide_reject_reason", type: "terminal"`, `event: "task_stack_cleared"`, `event: "play_playlist", state: "refusal_end"`, `event: "call_ending_flag_set"`. |
| 10 | * (Конец звонка)* | - | Цикл `run()` завершается, блок `finally` вызывает `shutdown()`, который останавливает все менеджеры. | `event: "shutdown_started"`, `event: "llm_shutdown"`, `event: "stt_stopped"`. |

---

## 4. Инструменты для тестирования

Для проведения теста будет создан скрипт `orchestrator/test/manual_test_orchestrator.py`.

**Функционал скрипта:**
- **Инициализация:** Создает и настраивает все зависимости (`TTSManager`, `LLMManager` и т.д.) с возможностью подмены на моки.
- **Моки (Mocks):**
  - `MockTTSManager`, `MockLLMManager`, `MockSTTStreamer`: Классы, которые имитируют поведение реальных сервисов и позволяют симулировать сбои (через установку флагов `should_fail_on_next_call`).
  - `MockInboundStream`: Асинхронный генератор, который "поставляет" заранее записанные аудио-чанки для STT.
- **Запуск:** Принимает на вход путь к аудиофайлу с речью пользователя и запускает `Orchestrator.run()`.

**Пример вызова:**
```bash
python3 orchestrator/test/manual_test_orchestrator.py --audio-scenario "path/to/scenario.wav" --simulate-tts-failure --simulate-llm-failure-after 2
```

---

## 5. Метрики для сбора

Во время теста необходимо активно логировать и собирать следующие метрики для каждого шага:
- `end_to_end_response_time_ms`: Общее время от получения `final` от STT до отправки первого аудио-чанка клиенту.
- `intent_classification_time_ms`: Время выполнения `intent_classifier.classify_intent`.
- `flow_engine_process_time_ms`: Время выполнения `flow_engine.process_event`.
- `tts_ttft_ms`: Time-To-First-Chunk от TTS.
- `llm_ttft_ms`: Time-To-First-Chunk от LLM.
- `barge_in_response_time_ms`: Время от детекции barge-in до полной остановки проигрывания.
