### **Задача для LLM: Модуль `stt_yandex.py` (Финальная, оптимизированная версия)**

**1. Контекст и цель модуля (CONTEXT):**
Модуль является высокопроизводительным и отказоустойчивым клиентом для Yandex SpeechKit v3 gRPC API. Он предназначен для работы в асинхронной среде `asyncio` и является критически важным компонентом в пайплайне распознавания речи. Его главная задача — принимать аудиопоток, эффективно управляя сетевым соединением и ресурсами, и предоставлять `Orchestrator`-у поток типизированных, удобных для анализа `partial` и `final` результатов распознавания.

**2. Основные требования к реализации (REQUIREMENTS):**

**2.1. Структуры данных:**

  * **`STTResponse`:** Создать `dataclass` с опцией `slots=True` для максимальной производительности и уменьшения потребления памяти.
    ```python
    from dataclasses import dataclass

    @dataclass(slots=True)
    class STTResponse:
        text: str
        is_final: bool
        stability_level: float
        utterance_index: int
    ```
  * **`STTConfig`:** Создать `dataclass` для инкапсуляции всех настроек сессии gRPC, включая `model`, `sample_rate_hertz` и `eou_sensitivity`.

**2.2. Архитектура класса `YandexSTTStreamer`:**

  * Класс должен управлять жизненным циклом gRPC-соединения и фоновых задач.
  * **Конструктор `__init__`:** Принимает `STTConfig` и объект учетных данных `credentials`.
  * **Основной метод `start_recognition(...)`:**
      * Должен быть асинхронным.
      * Принимает на вход `audio_chunk_queue: asyncio.Queue`. **Важно:** Оркестратор должен создавать эту очередь с параметром `maxsize` (например, `maxsize=50`) для реализации механизма противодавления.
      * Создает и возвращает `response_queue: asyncio.Queue`, из которой Оркестратор будет асинхронно читать готовые объекты `STTResponse`.
      * Запускает две приватные фоновые задачи (`asyncio.Task`) для отправки и получения данных.
      * Сохраняет ссылки на эти задачи, чтобы иметь возможность их остановить.
  * **Метод `stop_recognition()`:**
      * Должен быть асинхронным.
      * Корректно отменяет (`task.cancel()`) и ожидает завершения фоновых задач.
      * Закрывает gRPC-соединение.

**2.3. Логика фоновых задач:**

  * **Приватная корутина `_send_requests(grpc_stream, audio_chunk_queue)`:**
    1.  Формирует и отправляет **первое** сообщение с `session_options` на основе `self.config`.
    2.  Входит в цикл `while True`.
    3.  Асинхронно ожидает (`await audio_chunk_queue.get()`) и получает аудио-чанк из очереди.
    4.  Отправляет чанк в gRPC-стрим, обернув его в `StreamingRequest(chunk=...)`.
    5.  Обрабатывает маркер конца потока (например, `None`) для штатного завершения отправки.
  * **Приватная корутина `_receive_responses(grpc_stream, response_queue)`:**
    1.  Инициализирует внутренний счетчик `current_utterance_index = 0`.
    2.  Входит в цикл `async for response in grpc_stream`.
    3.  При получении сообщения `final` **инкрементирует** `current_utterance_index`.
    4.  Вызывает приватный метод `_parse_response(response, current_utterance_index)` для преобразования Protobuf-сообщения в `STTResponse`.
    5.  Если парсинг успешен, кладет результат в `response_queue` (`await response_queue.put(...)`).

**2.4. Логика парсинга `_parse_response`:**

  * Метод должен принимать `response: StreamingResponse` и `current_utterance_index: int`.
  * Он должен проверять тип события (`partial` или `final`).
  * Он должен корректно извлекать текст и `confidence` из `response.partial.alternatives[0]` или `response.final.alternatives[0]`.
  * Он должен использовать переданный `current_utterance_index` для заполнения соответствующего поля в `STTResponse`, **игнорируя** `response.audio_cursors.final_index` для `partial` результатов.

**2.5. Обработка ошибок:**

  * Обе фоновые корутины должны быть обернуты в `try...except grpc.aio.AioRpcError`.
  * При возникновении ошибки gRPC, она должна быть залогирована, а в `response_queue` должно быть помещено специальное сообщение об ошибке или выброшено исключение, которое будет обработано Оркестратором.

**3. Зависимости (DEPENDENCIES):**

  * **Внешние:** `grpcio`, `yandex.cloud.api`, `asyncio`, `dataclasses`.
  * **Внутренние:** Отсутствуют.

**4. План тестирования (TESTING PLAN):**

  * **Интеграционный тест:** Проверить полный цикл: запуск `start_recognition`, отправка аудио-чанков в `audio_chunk_queue`, получение `STTResponse` из `response_queue`, вызов `stop_recognition`.
  * **Unit-тест `_parse_response`:** Проверить корректность парсинга для `partial` и `final` сообщений, убедиться, что `utterance_index` используется правильно.
  * **Тест на противодавление (Backpressure):** Создать `audio_chunk_queue` с маленьким `maxsize`, быстро заполнить ее и убедиться, что вызывающая сторона блокируется, а не падает с ошибкой памяти.
  * **Тест на отмену:** Вызвать `stop_recognition` в середине процесса и убедиться, что фоновые задачи корректно отменяются и gRPC-соединение закрывается.

**5. Задание (TASK):**
### **План реализации модуля `stt_yandex.py`**

Этот документ описывает пошаговый план создания модуля для взаимодействия с Yandex SpeechKit v3 gRPC API, с фокусом на производительность, асинхронность и отказоустойчивость.

#### **1. Финальные определения `dataclass`'ов**

Будут определены две структуры данных для конфигурации и возвращаемых значений.

  * **`STTConfig`**: Конфигурационный `dataclass` для инкапсуляции всех настроек gRPC сессии. Это делает код чище и упрощает передачу параметров.
    ```python
    # Location: stt_yandex.py
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class STTConfig:
        model: str = "general:rc"
        language_code: str = "ru-RU"
        sample_rate_hertz: int = 8000
        audio_encoding: str = "LINEAR16_PCM"
        eou_sensitivity: int = 3 # Соответствует EouSensitivity.HIGH
        profanity_filter: bool = True
        text_normalization: str = "TEXT_NORMALIZATION_ENABLED"
    ```
  * **`STTResponse`**: `dataclass` для унификации ответов от API. Использование `slots=True` критически важно для снижения потребления памяти и ускорения доступа к атрибутам в высоконагруженной системе.
    ```python
    # Location: stt_yandex.py
    from dataclasses import dataclass

    @dataclass(slots=True, frozen=True)
    class STTResponse:
        text: str
        is_final: bool
        stability_level: float # Переименованное поле 'confidence'
        utterance_index: int
    ```

#### **2. Структура класса `YandexSTTStreamer`**

Класс будет спроектирован как менеджер состояния для одного gRPC-стрима.

  * **Атрибуты экземпляра:**

      * `_config: STTConfig`: Приватное хранилище конфигурации.
      * `_credentials`: Объект учетных данных для аутентификации в Yandex Cloud.
      * `_grpc_stub`: Экземпляр gRPC-стаба, создаваемый при подключении.
      * `_grpc_stream`: Активный двунаправленный gRPC-стрим.
      * `_send_task: asyncio.Task | None`: Ссылка на фоновую задачу отправки аудио.
      * `_receive_task: asyncio.Task | None`: Ссылка на фоновую задачу получения результатов.
      * `_logger`: Экземпляр логгера для отладки и мониторинга.

  * **Публичные методы:**

      * `__init__(self, config: STTConfig, credentials)`: Конструктор для инициализации конфигурации и учетных данных.
      * `async start_recognition(self, audio_chunk_queue: asyncio.Queue) -> asyncio.Queue`: Основной метод, запускающий процесс распознавания.
      * `async stop_recognition(self)`: Метод для корректной остановки и очистки ресурсов.

  * **Приватные методы:**

      * `_generate_requests(self, audio_chunk_queue: asyncio.Queue)`: Асинхронный генератор, который формирует gRPC-сообщения.
      * `_send_requests(self, audio_chunk_queue: asyncio.Queue)`: Корутина, управляющая отправкой данных в gRPC-стрим.
      * `_receive_responses(self, response_queue: asyncio.Queue)`: Корутина, управляющая получением и парсингом ответов.
      * `_parse_response(self, response: StreamingResponse, current_utterance_index: int) -> STTResponse | None`: Синхронный метод для парсинга Protobuf-сообщения в `STTResponse`.

#### **3. Детальная логика методов**

**3.1. `start_recognition(self, audio_chunk_queue)`**

1.  Создать `response_queue = asyncio.Queue()` для отправки результатов `STTResponse` Оркестратору.
2.  Инициализировать gRPC-канал и стаб (`stt_service_pb2_grpc.RecognizerStub`).
3.  Вызвать `self._grpc_stream = self._grpc_stub.RecognizeStreaming()` для установления двунаправленного соединения.
4.  Создать две фоновые задачи с помощью `asyncio.create_task()`:
      * `self._send_task = asyncio.create_task(self._send_requests(audio_chunk_queue))`
      * `self._receive_task = asyncio.create_task(self._receive_responses(response_queue))`
5.  Сохранить ссылки на обе задачи в атрибутах класса (`self._send_task`, `self._receive_task`).
6.  Вернуть `response_queue` вызывающей стороне (Оркестратору).

**3.2. `_send_requests(self, audio_chunk_queue)`**

1.  Обернуть всю логику в блок `try...except grpc.aio.AioRpcError...finally`.
2.  **Шаг 1: Отправка конфигурации.**
      * Создать конфигурационный объект `StreamingRequest`, заполняя `session_options` на основе `self._config`.
      * Отправить его в стрим: `await self._grpc_stream.write(config_request)`.
3.  **Шаг 2: Цикл отправки аудио.**
      * Войти в бесконечный цикл `while True`.
      * Асинхронно ожидать чанк из очереди: `chunk = await audio_chunk_queue.get()`.
      * **Обработка завершения:** Если `chunk is None`, это сигнал от Оркестратора о завершении потока. Вызвать `await self._grpc_stream.done_writing()` и выйти из цикла.
      * Обернуть байты аудио-чанка в `StreamingRequest(chunk={"data": chunk})`.
      * Отправить сообщение в стрим: `await self._grpc_stream.write(audio_request)`.
      * Вызвать `audio_chunk_queue.task_done()` для механизма противодавления.
4.  **Обработка ошибок:** В блоке `except` залогировать ошибку и убедиться, что другая задача будет отменена.

**3.3. `_receive_responses(self, response_queue)`**

1.  Обернуть всю логику в блок `try...except grpc.aio.AioRpcError`.
2.  Инициализировать счетчик завершенных фраз: `current_utterance_index = 0`.
3.  **Цикл получения ответов:**
      * Использовать `async for response in self._grpc_stream:`.
      * Вызвать `parsed_data = self._parse_response(response, current_utterance_index)`.
      * Если `parsed_data` не `None` (т.е. это `partial` или `final`):
          * Поместить результат в очередь: `await response_queue.put(parsed_data)`.
          * Если `parsed_data.is_final` имеет значение `True`, инкрементировать счетчик: `current_utterance_index += 1`.
4.  **Обработка ошибок:** В блоке `except` залогировать ошибку, поместить в `response_queue` специальный объект-маркер ошибки (или перевыбросить кастомное исключение) и завершить работу.

**3.4. `stop_recognition(self)`**

1.  Проверить, что задачи существуют (`if self._send_task and not self._send_task.done()`).
2.  Отменить обе задачи: `self._send_task.cancel()` и `self._receive_task.cancel()`.
3.  Использовать `asyncio.gather` с `return_exceptions=True` для ожидания их завершения: `await asyncio.gather(self._send_task, self._receive_task, return_exceptions=True)`. Это гарантирует, что все `CancelledError` обработаны.
4.  Проверить, что gRPC-стрим существует, и закрыть его, если он активен.

#### **4. Логика парсинга `_parse_response`**

Метод принимает `response` от gRPC и `current_utterance_index`.

1.  Проверить, какое поле в `response` заполнено, используя `response.WhichOneof('event')`.
2.  **Если `event == 'partial'`:**
      * Извлечь первый и наиболее вероятный вариант: `alternative = response.partial.alternatives[0]`.
      * Создать и вернуть экземпляр `STTResponse(text=alternative.text, is_final=False, stability_level=alternative.confidence, utterance_index=current_utterance_index)`.
3.  **Если `event == 'final'`:**
      * Извлечь первый вариант: `alternative = response.final.alternatives[0]`.
      * Создать и вернуть экземпляр `STTResponse(text=alternative.text, is_final=True, stability_level=alternative.confidence, utterance_index=current_utterance_index)`.
4.  Если это другой тип события (например, `status_code`), проигнорировать его и вернуть `None`.

#### **5. Стратегия обработки ошибок и жизненного цикла**

  * **Жизненный цикл:** Один экземпляр `YandexSTTStreamer` управляет одним полным циклом распознавания (от `start` до `stop`). Для нового звонка создается новый экземпляр.
  * **Ошибки gRPC:** Любая `grpc.aio.AioRpcError` в любой из двух фоновых задач является фатальной для текущего стрима.
  * **Цепочка отказа:**
    1.  Задача (отправки или получения), поймавшая исключение, логирует его.
    2.  Она должна инициировать отмену второй задачи, чтобы избежать "зависания". Это можно сделать, вызвав `self.stop_recognition()` внутри блока `except`.
    3.  В `response_queue` помещается специальный объект (например, `None` или кастомный класс `STTError`), чтобы Оркестратор знал о сбое.
    4.  Блок `finally` в корутинах должен обеспечить базовую очистку, если это необходимо.
  * **Противодавление (Backpressure):** Использование `asyncio.Queue` с `maxsize` на стороне Оркестратора является встроенным механизмом противодавления. Если Оркестратор не успевает обрабатывать аудио, `audio_chunk_queue.put()` будет блокироваться, предотвращая переполнение памяти. `task_done()` не обязателен для этого механизма, но является хорошей практикой.