📄 File 1 — SPEC-STT-1-Core.md

Модуль stt_yandex.py (v3, production-ready): gRPC клиент + очереди + метрики

0) Контекст

Это боевой клиент к Yandex SpeechKit STT v3 (gRPC, AsyncRecognizer). Задача — принять аудиопоток через asyncio.Queue, отправить в Yandex, и параллельно отдавать в другую очередь partial/final результаты. Обязательны: backpressure, корректное завершение, детальные метрики (в т.ч. до первого partial и первого final), и JSON-логирование для трассировки.

1) Дерево проекта (фрагмент)

project_root/
├─ .env.example                         # YC_IAM_TOKEN, YC_FOLDER_ID, STT_MODEL, STT_LANG, etc.
├─ configs/
│  └─ stt_config.yml                    # дефолтные значения STT (model, sample_rate_hz, eou_sensitivity,...)
├─ domain/
│  ├─ __init__.py
│  └─ stt_models.py                     # STTResponse, STTConfig, STTConnectionError
├─ stt_yandex/
│  ├─ __init__.py
│  └─ stt_yandex.py                     # <-- ЭТОТ ФАЙЛ
└─ third_party/
   └─ speechkit_stt_v3/                 # сгенерённые gRPC stubs (см. File 2)
      ├─ __init__.py
      ├─ stt_service_pb2.py
      ├─ stt_service_pb2_grpc.py
      ├─ recognition_pb2.py
      └─ common_pb2.py

2) Зависимости
	•	Runtime: grpcio>=1.62, python-dotenv>=1.0, PyYAML>=6.0
	•	Vendor stubs: third_party/speechkit_stt_v3/* (см. File 2, мы не тянем их из сети во время рантайма)
	•	Stdlib: asyncio, time, dataclasses, typing, logging, json

3) Контракты (импорты и типы)

domain/stt_models.py (должен существовать):

from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class STTResponse:
    text: str
    is_final: bool
    stability_level: float
    utterance_index: int

@dataclass(slots=True)
class STTConfig:
    endpoint: str            # "stt.api.cloud.yandex.net:443"
    language_code: str       # "ru-RU"
    model: str               # "general" | "general:rc" | ...
    sample_rate_hz: int      # 8000|16000|48000 (для LINEAR16_PCM)
    audio_encoding: str      # "LINEAR16_PCM" | "OGG_OPUS"
    partial_results: bool    # True — нужны partial
    single_utterance: bool   # False — много фраз в одной сессии
    profanity_filter: bool   # False|True
    raw_results: bool        # False — числа цифрами
    eou_sensitivity: float   # 0..1 (если поддерживается)
    normalize_partials: bool # x-normalize-partials (metadata)

class STTConnectionError(RuntimeError):
    pass

4) Реализуемый класс

stt_yandex/stt_yandex.py → class YandexSTTStreamer:

4.1. __init__(self, config: STTConfig, iam_token: str, folder_id: str)
	•	Сохраняет конфиг и креды.
	•	Готовит self._channel: grpc.aio.Channel | None = None, self._stub = None.
	•	Параметры канала: secure channel (grpc.ssl_channel_credentials()), опции: grpc.keepalive_time_ms, grpc.keepalive_timeout_ms, grpc.http2.max_pings_without_data, grpc.max_send_message_length, grpc.max_receive_message_length — разумные значения по дефолту.
	•	Логирует JSON событие stt_conn_init.

4.2. async start_recognition(self, audio_chunk_queue: asyncio.Queue[bytes | None]) -> asyncio.Queue[tuple]
	•	Создаёт канал и stub (handshake), замеряет и логирует:
	•	stt_handshake_start/finish (ms)
	•	Формирует bidirectional stream: вызывает stub.StreamingRecognize() (имя метода/тип — из сгенерённых stubs).
	•	Создаёт response_queue: asyncio.Queue[tuple] (элементы: (STTResponse|None, STTConnectionError|None)).
	•	Запускает две фоновые задачи:
	•	_send_requests(stream, audio_chunk_queue)
	•	_receive_responses(stream, response_queue)
	•	Возвращает response_queue.

4.3. async stop_recognition(self)
	•	Корректно отменяет обе задачи (task.cancel() → await asyncio.gather(..., return_exceptions=True)).
	•	Закрывает stream, канал (await self._channel.close()), зануляет ссылки.
	•	Логирует stt_stop.

4.4. _send_requests(self, stream, audio_chunk_queue)
	•	Сначала отправляет config message (per API v3): язык, модель, формат, частота, folder_id. Части:
	•	message: StreamingRequest(config=...) (конкретный класс — из stubs).
	•	Metadata: ("authorization", f"Bearer {iam_token}"), ("x-client-request-id", trace_id), ("x-normalize-partials","true|false").
	•	Затем в цикле:
	•	ждёт chunk = await audio_chunk_queue.get()
	•	если chunk is None — посылает финальный audio_finished/закрывает отправку (по протоколу), выходит.
	•	иначе — отправляет StreamingRequest(audio_content=chunk).
	•	try/except grpc.aio.AioRpcError: лог stt_send_error и кладёт в response_queue (None, STTConnectionError(...)).

4.5. _receive_responses(self, stream, response_queue)
	•	Локальный utter_idx = 0.
	•	async for rsp in stream: разбирает:
	•	массив rsp.chunks[] (v2/v3 различается названием, но в сгенерённых stubs это будет поле вроде chunks).
	•	для каждого чанка берёт alt = chunk.alternatives[0] → text=alt.text.
	•	is_final = bool(chunk.final).
	•	end_of_utt = bool(chunk.endOfUtterance) (если присутствует).
	•	stability_level: если нет явного поля — выставляем эвристику: 1.0 if is_final else 0.5.
	•	если is_final: utter_idx += 1.
	•	формируем STTResponse(text, is_final, stability_level, utter_idx) и кладём (resp, None).
	•	try/except AioRpcError: лог stt_recv_error и кладём (None, STTConnectionError(...)).
	•	на завершение стрима — лог stt_stream_closed.

4.6. Метрики и JSON-логи (обязательно)
	•	stt_conn_init
	•	stt_handshake_start/finish (ms)
	•	stt_send_cfg (model, lang, sample_rate, encoding, partial=bool, single_utt=bool)
	•	stt_first_partial_ms — с момента stt_send_cfg (или request_send) до первого partial
	•	stt_first_final_ms — до первого final
	•	stt_stream_closed
	•	Ошибки: stt_send_error, stt_recv_error, stt_grpc_error (status_code, details)

Примечание: точный импорт классов сообщений (*_pb2, *_pb2_grpc) — из наших сгенерённых stubs (см. File 2). В этой задаче важно зафиксировать контракт и места вставки.

4.7. if __name__ == "__main__": (песочница)
	•	Загрузить .env → YC_IAM_TOKEN, YC_FOLDER_ID.
	•	Считать configs/stt_config.yml.
	•	Создать STTConfig (дефолты ок).
	•	Создать audio_chunk_queue = asyncio.Queue(maxsize=50).
	•	Создать объект YandexSTTStreamer и await start_recognition(queue) → response_queue.
	•	НЕ слать аудио (только конфиг), закрыть через None → убедиться, что соединение поднимается и корректно гасится. Все логи — однострочный JSON.

5) Критерии приёмки
	•	Файл импортируется и запускается отдельно (без падений).
	•	Создание канала/стаба и закрытие — корректны (handshake-метрики есть).
	•	Две фоновые задачи запускаются/останавливаются.
	•	Контракты очередей соблюдены: response_queue отдаёт (STTResponse|None, STTConnectionError|None).

⸻

📄 File 2 — SPEC-STT-2-Protos-and-Creds.md

Генерация gRPC stubs SpeechKit v3 + проверка кредов

0) Зачем

Чтобы код из File 1 компилировался и запускался без скачивания в рантайме, нужно единожды сгенерировать Python-стабы по официальным proto из SpeechKit v3 и сохранить их в проект (third_party/speechkit_stt_v3/). Плюс — валидация .env: токен/каталог.

1) Дерево

project_root/
├─ .env.example
├─ scripts/
│  ├─ fetch_speechkit_protos.py      # скачать proto (git-raw), сложить во временную папку
│  ├─ gen_speechkit_stubs.py         # сгенерировать *_pb2*.py → third_party/speechkit_stt_v3
│  └─ check_yc_creds.py              # проверить YC_IAM_TOKEN и YC_FOLDER_ID
└─ third_party/
   └─ speechkit_stt_v3/              # результат генерации
      ├─ __init__.py
      ├─ stt_service.proto           # (опц.) сохранить исходники рядом
      ├─ recognition.proto
      ├─ common.proto
      ├─ stt_service_pb2.py
      ├─ stt_service_pb2_grpc.py
      ├─ recognition_pb2.py
      └─ common_pb2.py

2) Зависимости
	•	grpcio-tools>=1.62 (для python -m grpc_tools.protoc)
	•	requests>=2.32 (скачать сырой proto из GitHub; интернет нужен один раз)
	•	python-dotenv>=1.0

3) Источники proto (зафиксировать)
	•	Репозиторий Yandex SpeechKit v3 proto (официальный): speechkit/stt/v3.
Пути:
	•	recognizer/recognizer.proto (или stt_service.proto — имя укажем после проверки)
	•	recognition.proto
	•	common.proto
⚠️ Если структура репо изменится, в fetch_speechkit_protos.py держим список URL’ов явным массивом.

4) Скрипты

4.1. scripts/fetch_speechkit_protos.py
	•	Аргументы: --dest third_party/speechkit_stt_v3
	•	Скачивает конкретные raw-URL’ы, проверяет SHA256 (опц.), кладёт в dest.
	•	Пишет лог JSON: protos_fetched {count, dest}.

4.2. scripts/gen_speechkit_stubs.py
	•	Аргументы: --src third_party/speechkit_stt_v3 --out third_party/speechkit_stt_v3
	•	Вызов python -m grpc_tools.protoc -I{src} --python_out={out} --grpc_python_out={out} {src}/*.proto
	•	Создаёт __init__.py если отсутствует.
	•	Лог JSON: stubs_generated {files, out}.

4.3. scripts/check_yc_creds.py
	•	Читает .env: YC_IAM_TOKEN, YC_FOLDER_ID.
	•	Проверяет, что токен похож на JWT (точка/два разделителя) или IAM-формат; длина folder_id ≤ 50.
	•	Возвращает код 0 и лог JSON creds_ok/creds_invalid.

5) Обновление .env.example

# Yandex Cloud SpeechKit
YC_IAM_TOKEN=ya29.a0AR...   # IAM-токен (или SA-key flow)
YC_FOLDER_ID=b1gabc123def4567890
STT_MODEL=general
STT_LANG=ru-RU
STT_SAMPLE_RATE=16000
STT_AUDIO_ENCODING=LINEAR16_PCM
STT_PARTIAL_RESULTS=true
STT_SINGLE_UTTERANCE=false
STT_PROFANITY_FILTER=false
STT_RAW_RESULTS=false
STT_EOU_SENSITIVITY=0.45
STT_NORMALIZE_PARTIALS=true

6) Критерии приёмки
	•	Выполнение:
	•	python scripts/fetch_speechkit_protos.py --dest third_party/speechkit_stt_v3
	•	python scripts/gen_speechkit_stubs.py --src third_party/speechkit_stt_v3 --out third_party/speechkit_stt_v3
	•	python scripts/check_yc_creds.py → creds_ok
	•	После этого импорт в stt_yandex/stt_yandex.py вида:

from third_party.speechkit_stt_v3 import stt_service_pb2, stt_service_pb2_grpc, recognition_pb2

— работает без интернета.

⸻

📄 File 3 — SPEC-STT-3-Manual-Test.md

Ручной интеграционный тест STT: стрим с WAV, backpressure, TTFT(partial/final), отчёты

0) Контекст

Нам нужен реалистичный прогон «как в проде»: читаем example.wav, режем на чанки, кладём в audio_chunk_queue (ограниченный maxsize для backpressure), параллельно читаем response_queue от YandexSTTStreamer. Замеряем:
	•	TTFP (Time-to-First-Partial)
	•	TTFF (Time-to-First-Final)
	•	Average total
	•	RTT на сетевом уровне (грубая оценка: момент отправки конфига → первый байт rsp)
	•	загрузку очереди (max depth), количество дропа (если есть)
	•	handshake (создание канала+стаба)
	•	кладём всё в JSON-логи + Markdown-отчёт. Цель демо: < 800 ms до первого аудио-чанка — для STT это эквивалентно TTFP.

1) Дерево

project_root/
├─ test_data/
│  └─ example.wav
└─ stt_yandex/
   └─ test/
      └─ manual_test_stt.py     # <-- этот файл

2) Зависимости
	•	Использует stt_yandex/stt_yandex.py (File 1)
	•	wave (stdlib), argparse, asyncio, time, statistics, json, logging, pathlib
	•	python-dotenv, PyYAML

3) Требования к тесту
	•	Резка WAV — без pydub/ffmpeg: стандартный wave:
	•	проверить nchannels, sampwidth, framerate
	•	поддерживаем LINEAR16_PCM (сырые сэмплы): выдёргиваем payload без WAV-заголовка (или читаем фреймы и шлём как есть, если сервер принимает WAV-header — но по v3 нужен сырой PCM → в тесте делаем payload = raw PCM).
	•	chunk_ms=20 по умолчанию → frames_per_chunk = int(framerate*chunk_ms/1000) → bytes_per_chunk = frames_per_chunk * nchannels*sampwidth
	•	логируем wav_info (sr, nch, sampwidth, duration_ms, chunks, total_bytes)
	•	Паттерн очередей как у Оркестратора:
	•	audio_chunk_queue = asyncio.Queue(maxsize=50)
	•	response_queue = await stt.start_recognition(audio_chunk_queue)
	•	продюсер: читает WAV → await queue.put(bytes_chunk); по завершении → await queue.put(None)
	•	потребитель: while True: result, err = await response_queue.get() → лог partial|final; на ошибке — в лог и выход
	•	Метрики:
	•	handshake_ms
	•	ttfp_ms (первый partial)
	•	ttff_ms (первый final)
	•	total_ms (до закрытия стрима)
	•	queue_max_depth
	•	bytes_sent, chunks_sent
	•	partials_count, finals_count
	•	Повтор: --repeats N (дефолт 3) — чтобы посчитать p50/p95.
	•	Отчёт: сохранить reports/stt_probe_YYYYmmdd-HHMM.md + reports/stt_probe_*.json.

4) Формат логов (строго JSON, одна строка)

Примеры:

{"event":"stt_handshake_start","ts":1723200000.123}
{"event":"stt_handshake_finish","ms":37.4}
{"event":"wav_info","sr":16000,"nch":1,"sampwidth":2,"duration_ms":5230,"chunks":262,"total_bytes":167680}
{"event":"send_chunk","i":1,"bytes":640}
{"event":"recv_partial","i":1,"ttfp_ms":612.8,"text":"привет"}
{"event":"recv_final","i":1,"ttff_ms":1288.4,"text":"привет, меня слышно"}
{"event":"stream_end","total_ms":2310.5,"partials":34,"finals":2}
{"event":"report_saved","path_md":"reports/stt_probe_2025-08-09T12-30.md","path_json":"reports/stt_probe_2025-08-09T12-30.json"}

5) CLI

python stt_yandex/test/manual_test_stt.py \
  --wav test_data/example.wav \
  --chunk-ms 20 \
  --repeats 3 \
  --report-dir reports \
  --config configs/stt_config.yml

6) Важные детали реализации
	•	Отправка сырого PCM: для LINEAR16_PCM нужно слать без WAV-хедера. В wave можно читать фреймы readframes(frames_per_chunk) → это уже данные без заголовка → шлём как есть.
	•	TTFP/TTFF: отсчёт от момента успешной отправки config (stt_send_cfg) или от первого send_chunk — выберите один и зафиксируйте (рекомендуем: от stt_send_cfg).
	•	Backpressure: maxsize=50. Если продюсер быстрее — он естественно заблокируется на .put() (это ожидаемо).
	•	Аварийное завершение: при STTConnectionError — запишите stt_grpc_error и корректно вызовите await stt.stop_recognition().

7) Что считаем в отчёте
	•	Для каждой метрики: avg, p50, p95 по repeats.
	•	Сравнение цели: TTFP p50 < 800 ms → OK/FAIL.
	•	Краткий summary: sr/nch/sampwidth, объём данных, пропускная способность (MB/s) по отправке.

8) Мини-скелет песочницы (внутри manual_test_stt.py)

if __name__ == "__main__":
    # 1) argparse: wav, chunk-ms, repeats, report-dir, config
    # 2) загрузка .env (YC_IAM_TOKEN, YC_FOLDER_ID) + YAML-конфиг в STTConfig
    # 3) для k in repeats:
    #       - создать очереди, поднять YandexSTTStreamer
    #       - запустить продюсера WAV (async)
    #       - читать ответы, фиксировать ttfp/ttff
    #       - стопнуть стрим
    # 4) посчитать p50/p95/avg -> сохранить отчёт (md+json)
    # 5) все действия логировать в JSON
    pass

9) Критерии приёмки
	•	Скрипт запускается одной командой, создаёт два отчёта (md+json).
	•	Логи — строго JSON-однострочники.
	•	Есть измерения: handshake, TTFP, TTFF, total, очереди.
	•	Можно регулировать --chunk-ms и видеть влияние на TTFP.

