📄 File 1 — SPEC-TTS-1-Config.md

TTS (ElevenLabs) — конфигурация, загрузка env, валидация

Контекст

Этот файл описывает минимальный, но достаточный конфиг-слой для ElevenLabs TTS: API-ключ, voice_id, model_id, параметры HTTP/WS и таймауты. Конфиг загружается из configs/tts_config.yml с подстановкой значений из .env. Используется и в tts_manager.connection_manager.WebSocketConnectionManager, и в tts_manager.manager.TTSManager.

Дерево проекта (фрагмент)

project_root/
├─ .env.example
├─ configs/
│  └─ tts_config.yml
├─ tts_manager/
│  ├─ __init__.py
│  ├─ config.py                # <-- здесь dataclass + loader
│  ├─ connection_manager.py    # (см. File 2)
│  └─ manager.py               # (см. File 2)
└─ tts_manager/test/
   └─ manual_test_tts.py       # (см. File 3)

Зависимости
	•	Runtime: python-dotenv>=1.0, PyYAML>=6.0
	•	Stdlib: dataclasses, typing, pathlib, os, logging

Контракты и требования

1) tts_manager/config.py
	•	Dataclass TTSConfig (строгие поля, значения по умолчанию разумные).
	•	Функция load_tts_config(yaml_path: str | Path) -> TTSConfig:
	•	Загружает YAML, применяет .env.
	•	Валидирует ключевые поля (не пустые).
	•	Логирует JSON-события tts_config_loaded и предупреждения, если включены «агрессивные» оптимизации задержки (см. optimize_streaming_latency=4).
	•	Никаких внешних вызовов сети/SDK.

# tts_manager/config.py (скелет)

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import os, logging, json, yaml
from dotenv import load_dotenv

log = logging.getLogger("tts_config")

@dataclass(slots=True)
class TTSConfig:
    # Auth
    api_key: str
    voice_id: str
    model_id: str

    # HTTP streaming
    http_base_url: str = "https://api.elevenlabs.io"
    http_timeout_sec: float = 20.0
    http_output_format: str = "mp3_44100_128"
    optimize_streaming_latency: Optional[int] = 4  # 0..4, 4 = самый быстрый

    # WebSocket streaming
    ws_base_url: str = "wss://api.elevenlabs.io"
    ws_inactivity_timeout: int = 20           # seconds (<=180)
    ws_auto_mode: bool = True                 # снижает задержку
    ws_enable_ssml_parsing: bool = False
    ws_output_format: str = "mp3_44100_128"   # унификация с http
    ws_keep_alive_sec: float = 15.0
    ws_connect_timeout_sec: float = 10.0

    # Voice settings (передаются при initialize)
    voice_speed: float = 1.0
    voice_stability: float = 0.5
    voice_similarity_boost: float = 0.8
    language_code: Optional[str] = None       # например 'ru'

def _jlog(event: str, **fields):
    log.info(json.dumps({"event": event, **fields}, ensure_ascii=False))

def load_tts_config(yaml_path: str | Path) -> TTSConfig:
    load_dotenv(override=False)
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Подмешиваем ENV (если есть)
    api_key = os.getenv("ELEVEN_API_KEY") or data.get("api_key") or ""
    voice_id = os.getenv("ELEVEN_VOICE_ID") or data.get("voice_id") or ""
    model_id = os.getenv("ELEVEN_MODEL_ID") or data.get("model_id") or ""

    cfg = TTSConfig(
        api_key=api_key,
        voice_id=voice_id,
        model_id=model_id,
        http_base_url=data.get("http_base_url", TTSConfig.http_base_url),
        http_timeout_sec=float(data.get("http_timeout_sec", TTSConfig.http_timeout_sec)),
        http_output_format=data.get("http_output_format", TTSConfig.http_output_format),
        optimize_streaming_latency=data.get("optimize_streaming_latency", TTSConfig.optimize_streaming_latency),
        ws_base_url=data.get("ws_base_url", TTSConfig.ws_base_url),
        ws_inactivity_timeout=int(data.get("ws_inactivity_timeout", TTSConfig.ws_inactivity_timeout)),
        ws_auto_mode=bool(data.get("ws_auto_mode", TTSConfig.ws_auto_mode)),
        ws_enable_ssml_parsing=bool(data.get("ws_enable_ssml_parsing", TTSConfig.ws_enable_ssml_parsing)),
        ws_output_format=data.get("ws_output_format", TTSConfig.ws_output_format),
        ws_keep_alive_sec=float(data.get("ws_keep_alive_sec", TTSConfig.ws_keep_alive_sec)),
        ws_connect_timeout_sec=float(data.get("ws_connect_timeout_sec", TTSConfig.ws_connect_timeout_sec)),
        voice_speed=float(data.get("voice_speed", TTSConfig.voice_speed)),
        voice_stability=float(data.get("voice_stability", TTSConfig.voice_stability)),
        voice_similarity_boost=float(data.get("voice_similarity_boost", TTSConfig.voice_similarity_boost)),
        language_code=data.get("language_code", TTSConfig.language_code),
    )

    # Валидация
    missing = [k for k, v in {"api_key": cfg.api_key, "voice_id": cfg.voice_id, "model_id": cfg.model_id}.items() if not v]
    if missing:
        raise ValueError(f"Missing required TTS config fields: {missing}")

    _jlog("tts_config_loaded",
          http_base_url=cfg.http_base_url,
          ws_base_url=cfg.ws_base_url,
          voice_id=cfg.voice_id,
          model_id=cfg.model_id,
          osl=cfg.optimize_streaming_latency,
          ws_auto_mode=cfg.ws_auto_mode)

    if cfg.optimize_streaming_latency == 4:
        _jlog("tts_latency_mode_warning", note="Using optimize_streaming_latency=4 may reduce quality, but fastest")

    return cfg

if __name__ == "__main__":
    import logging, sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    path = sys.argv[1] if len(sys.argv) > 1 else "configs/tts_config.yml"
    cfg = load_tts_config(path)
    print(cfg)

2) configs/tts_config.yml (пример)

api_key: "${ELEVEN_API_KEY}"
voice_id: "${ELEVEN_VOICE_ID}"
model_id: "${ELEVEN_MODEL_ID}"

http_base_url: "https://api.elevenlabs.io"
http_timeout_sec: 20
http_output_format: "mp3_44100_128"
optimize_streaming_latency: 4

ws_base_url: "wss://api.elevenlabs.io"
ws_inactivity_timeout: 20
ws_auto_mode: true
ws_enable_ssml_parsing: false
ws_output_format: "mp3_44100_128"
ws_keep_alive_sec: 15
ws_connect_timeout_sec: 10

voice_speed: 1.0
voice_stability: 0.5
voice_similarity_boost: 0.8
language_code: "ru"

3) .env.example

# ElevenLabs
ELEVEN_API_KEY=xi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ELEVEN_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
ELEVEN_MODEL_ID=eleven_turbo_v2_5

Критерии приёмки
	•	python -m tts_manager.config configs/tts_config.yml выводит корректный объект и JSON-логи.
	•	Ошибка при отсутствии ключевых полей (api_key, voice_id, model_id).

⸻

📄 File 2 — SPEC-TTS-2-Core.md

TTSManager v2 + WebSocketConnectionManager (гибрид HTTP/WS, минимальная задержка)

Контекст

Модуль отдаёт аудио-чанки как для статических фраз (HTTP streaming), так и для LLM-стрима (WebSocket). Отдельный WebSocketConnectionManager держит тёплое соединение (keep-alive), чтобы срезать 100–300 мс на каждом ответе. Все сетевые операции логируются в JSON-формате: handshake, TTFT (time-to-first-token/first audio chunk), средняя латентность, ошибки.

Дерево проекта (фрагмент)

project_root/
├─ tts_manager/
│  ├─ config.py                 # из File 1
│  ├─ connection_manager.py     # <-- этот файл
│  └─ manager.py                # <-- этот файл
└─ tts_manager/test/
   └─ manual_test_tts.py        # File 3

Зависимости
	•	Runtime: httpx>=0.27, websockets>=12.0, anyio>=4, python-dotenv, PyYAML
	•	Stdlib: asyncio, time, json, logging, typing, collections

Контракты и интерфейсы

Ошибки

class TTSConnectionError(RuntimeError): ...
class TTSProtocolError(RuntimeError): ...

tts_manager/connection_manager.py

Класс: WebSocketConnectionManager

Назначение: установить и держать одно WS-соединение для конкретного звонка, отдать соединение полностью прогретым. Но держатть его всегда прогретым, дополнительно к этому классу можно создать класс, который бы прогревал модель, то есть делал хэндшейк, затем слал пустые чанки на синтез, чтоб модель активировалась. Нужно чтоб операция по прогреву выполнялась если мы не использовали наш TTS более чем N секунд, тогда он в фоне активирует прогрев чтобы вернуть новое соедение, с уже активированной моделью. Все это делается в фоне, в асинцио потоке. 

Публичные методы:
	•	__init__(self, cfg: TTSConfig)
	•	async connect(self) -> websockets.WebSocketClientProtocol
Шаги и метрики:
	•	ws_handshake_start → создаёт URL вида:

wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input
  ?model_id={model_id}
  &output_format={ws_output_format}
  &inactivity_timeout={ws_inactivity_timeout}
  &auto_mode={true|false}
  &enable_ssml_parsing={true|false}
  &language_code={optional}


	•	Заголовки: {"xi-api-key": cfg.api_key}
	•	Устанавливает соединение (таймаут cfg.ws_connect_timeout_sec)
	•	После апгрейда отправляет initializeConnection:

{
  "initializeConnection":{
    "voice_settings":{
      "stability": 0.5,
      "similarity_boost": 0.8,
      "style": 0,
      "use_speaker_boost": false,
      "speed": 1.0
    }
  }
}

(допустимая форма по доке; если нужен ключ — добавляем {"xi_api_key":"..."} в отдельном сообщении — поддержать оба варианта)

	•	Замеряет ws_handshake_ms и логирует.
	•	Запускает self._keep_alive_task() каждые cfg.ws_keep_alive_sec: шлёт мягкий ping:
	•	вариант А (совместимый): {"sendText":{"text":" "}}
	•	вариант Б (простой): {"text":" "}

	•	async close(self):
	•	Останавливает keep-alive.
	•	Пытается отправить {"closeConnection":{}} и потом закрывает сокет.

Приватные:
	•	_keep_alive_task(self): while True: sleep; try: send ping; except: break

Логи (JSON):
	•	ws_handshake_start, ws_handshake_finish (ms)
	•	ws_keepalive_ping, ws_keepalive_error
	•	ws_closed

tts_manager/manager.py

Класс: TTSManager

Публичные методы:
	•	__init__(self, cfg: TTSConfig, conn_mgr: WebSocketConnectionManager)
	•	async stream_static_text(self, text: str) -> typing.AsyncGenerator[bytes, None]
HTTP streaming:
	•	URL: POST {http_base_url}/v1/text-to-speech/{voice_id}/stream
	•	Query: output_format, optimize_streaming_latency
	•	Headers: xi-api-key, Content-Type: application/json
	•	JSON body: {"text": text, "model_id": cfg.model_id, "voice_settings": {...}, "language_code": cfg.language_code}
	•	Метрики:
	•	http_request_start (ts)
	•	http_first_byte_ms — до первого aiter_bytes() чанка
	•	http_total_ms
	•	Ошибки: лог http_error (status, text)
	•	async start_llm_stream(self) -> tuple[asyncio.Queue[str], asyncio.Queue[bytes]]
WebSocket streaming (для LLM):
	•	Получает активный ws = await conn_mgr.connect()
	•	Создаёт text_input_q: Queue[str] и audio_output_q: Queue[bytes]
	•	Поднимает две фоновые задачи:
	•	_ws_send_task(ws, text_input_q):
	•	Первый отправленный юзером кусок текста помечается {"sendText":{"text": "...", "try_trigger_generation": true}}
	•	Остальные: {"sendText":{"text": "..."}}
	•	_ws_recv_task(ws, audio_output_q):
	•	TTFT (WS): фиксируем время от ws_handshake_finish до первого входящего audioOutput (или finalOutput)
	•	Сообщения вида:

{"audio":"<base64>", "isFinal": false}
{"finalOutput": true}

Декодим audio (base64 → bytes), кладём в очередь

	•	Возвращает (text_input_q, audio_output_q)

Логи (JSON):
	•	http_request_start, http_first_byte, http_stream_end
	•	ws_send_text, ws_recv_audio, ws_first_audio_ms, ws_final_received
	•	tts_protocol_error, tts_ws_error, tts_http_error

Песочница
В обоих модулях предусмотреть:

if __name__ == "__main__":
    # Прочитать configs/tts_config.yml
    # Выполнить простой connect()/close() для WS (замер handshake)
    # Выполнить короткий HTTP streaming "тестовая фраза"
    # Всё логировать JSON-строками

Критерии приёмки
	•	Отдельно запускаются оба файла, без падений.
	•	WS-handshake измеряется и логируется.
	•	HTTP-стрим выдаёт чанки и метрики по первому байту/тоталу.
	•	Очереди WS-стрима создаются, фоновые таски запускаются, TTFT замеряется.

⸻

📄 File 3 — SPEC-TTS-3-Manual-Test.md

Ручной e2e-бенч TTS (HTTP+WS): короткие/длинные фразы, TTFT, handshake, устойчивость

Контекст

Скрипт без pytest. Гоняем реальные запросы к ElevenLabs:
	1.	HTTP streaming для статических фраз.
	2.	WebSocket для LLM-стрима (скармливаем текст порциями).
Собираем метрики: время установки WS-соединения (handshake), TTFT (до первого аудио-чанка), сетевые задержки (HTTP: до первого байта; WS: после первой отправки текста), средняя скорость и устойчивость под повторными прогонами. Логи — JSON-однострочники + агрегированный Markdown-отчёт.

Дерево

project_root/
├─ configs/tts_config.yml
├─ .env
├─ tts_manager/
│  ├─ config.py
│  ├─ connection_manager.py
│  └─ manager.py
└─ tts_manager/test/
   └─ manual_test_tts.py   # <-- этот файл

Зависимости
	•	Использует модули из File 1 и File 2.
	•	Runtime: httpx, websockets, python-dotenv, PyYAML
	•	Stdlib: asyncio, time, json, statistics, argparse, pathlib, logging, base64, os

Что тестируем
	1.	Handshake WS: сколько мс.
	2.	TTFT (WS): от момента первой отправки текста sendText(..., try_trigger_generation=True) до первого аудио-чанка.
	3.	TTFA (HTTP): от http_request_start до первого байта стрима.
	4.	Короткие vs длинные реплики:
	•	Короткая: "Стоимость 12000 рублей."
	•	Длинная: абзац 300–500 знаков (с числами и пунктуацией).
	5.	Устойчивость:
	•	Повторить тест --repeats N (по умолчанию 3).
	•	Отдельный кейс reconnect: закрыть и снова поднять WS в рамках одного запуска.
	6.	Логи и отчёт:
	•	JSONL файл с детальными событиями.
	•	Markdown-отчёт с p50/p95/avg по TTF* и handshake.

Формат логов (обязательные события)

{"event":"ws_handshake_start","ts":...}
{"event":"ws_handshake_finish","ms":...}
{"event":"ws_send_text","seq":1,"chars":27,"try_trigger_generation":true}
{"event":"ws_first_audio","ms":...,"bytes":1234}
{"event":"ws_stream_end","total_ms":...,"chunks":12,"bytes":54321}

{"event":"http_request_start","ts":...}
{"event":"http_first_byte","ms":...}
{"event":"http_stream_end","total_ms":...,"chunks":9,"bytes":32100}

{"event":"bench_case_done","mode":"ws|http","length":"short|long","ttf_ms":...,"total_ms":...}
{"event":"report_saved","path_md":"...","path_json":"..."}

CLI

python tts_manager/test/manual_test_tts.py \
  --config configs/tts_config.yml \
  --repeats 3 \
  --out reports \
  --ws-chunk "Стоимость 12000 рублей." \
  --ws-long "..." \
  --http-chunk "Стоимость 12000 рублей." \
  --http-long "..."

Если тексты не переданы, использовать дефолт из скрипта.

Логика теста (вкратце)
	•	Загрузка TTSConfig.
	•	WS-часть:
	•	conn = WebSocketConnectionManager(cfg)
	•	t0=time.perf_counter() → await conn.connect() → handshake_ms
	•	mgr = TTSManager(cfg, conn)
	•	text_q, audio_q = await mgr.start_llm_stream()
	•	Засекаем t_send0 = perf_counter(); кладём short с try_trigger_generation=True.
	•	Читаем первый чанк аудио → ttft_ws_ms = (now - t_send0); собираем все чанки → total_ws_ms.
	•	Закрываем стрим/соединение → повторить N раз, затем кейс с длинным текстом.
	•	HTTP-часть:
	•	Засекаем http_request_start; итерируем async for chunk in mgr.stream_static_text(text):
	•	Первый чанк → ttfa_http_ms
	•	На каждом повторе логируем итог.
	•	Агрегация: p50/p95/avg по: ws_handshake_ms, ttft_ws_ms, ttfa_http_ms, total_ws_ms, total_http_ms.
	•	Сохранить:
	•	reports/tts_probe_YYYYmmdd-HHMM.jsonl — сырые логи
	•	reports/tts_summary_YYYYmmdd-HHMM.md — сводка с таблицей.

Мини-скелет manual_test_tts.py

# tts_manager/test/manual_test_tts.py (скелет)

import asyncio, time, json, logging, argparse
from pathlib import Path
from statistics import mean
from tts_manager.config import load_tts_config
from tts_manager.connection_manager import WebSocketConnectionManager
from tts_manager.manager import TTSManager

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("tts_bench")
def jlog(event, **kw): log.info(json.dumps({"event": event, **kw}, ensure_ascii=False))

async def run_ws_case(cfg, text, repeats):
    res = {"handshake_ms":[], "ttft_ms":[], "total_ms":[]}
    for i in range(repeats):
        conn = WebSocketConnectionManager(cfg)
        t0 = time.perf_counter()
        ws = await conn.connect()
        t_handshake = (time.perf_counter() - t0) * 1000
        jlog("ws_handshake_finish", ms=round(t_handshake,2))

        mgr = TTSManager(cfg, conn)
        text_q, audio_q = await mgr.start_llm_stream()

        t_send0 = time.perf_counter()
        await text_q.put({"text": text, "try_trigger_generation": True})
        first = None; total_bytes=0; chunks=0
        t_first=None
        while True:
            data = await audio_q.get()
            if data is None: break
            if first is None:
                t_first = (time.perf_counter() - t_send0)*1000
                jlog("ws_first_audio", ms=round(t_first,2), bytes=len(data))
                first = True
            total_bytes += len(data); chunks+=1
        total_ms = (time.perf_counter() - t_send0)*1000
        jlog("ws_stream_end", total_ms=round(total_ms,2), chunks=chunks, bytes=total_bytes)
        res["handshake_ms"].append(t_handshake)
        res["ttft_ms"].append(t_first or total_ms)
        res["total_ms"].append(total_ms)
        await conn.close()
    return res

async def run_http_case(cfg, text, repeats):
    import anyio
    res = {"ttfa_ms":[], "total_ms":[]}
    for i in range(repeats):
        mgr = TTSManager(cfg, None)
        t0 = time.perf_counter()
        first=None; total_bytes=0; chunks=0
        async for ch in mgr.stream_static_text(text):
            if first is None:
                first = (time.perf_counter() - t0)*1000
                jlog("http_first_byte", ms=round(first,2))
            total_bytes+=len(ch); chunks+=1
        total_ms = (time.perf_counter() - t0)*1000
        jlog("http_stream_end", total_ms=round(total_ms,2), chunks=chunks, bytes=total_bytes)
        res["ttfa_ms"].append(first or total_ms)
        res["total_ms"].append(total_ms)
    return res

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/tts_config.yml")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default="reports")
    ap.add_argument("--ws-chunk", default="Стоимость 12000 рублей.")
    ap.add_argument("--ws-long", default="Это длинная проверочная реплика ... (300+ знаков)")
    ap.add_argument("--http-chunk", default="Стоимость 12000 рублей.")
    ap.add_argument("--http-long", default="Это длинная проверочная реплика ... (300+ знаков)")
    args = ap.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    cfg = load_tts_config(args.config)

    ws_short = await run_ws_case(cfg, args.ws_chunk, args.repeats)
    ws_long  = await run_ws_case(cfg, args.ws_long,  args.repeats)
    http_short = await run_http_case(cfg, args.http_chunk, args.repeats)
    http_long  = await run_http_case(cfg, args.http_long,  args.repeats)

    # Сводка (p50/p95 можно добавить при желании)
    def avg(a): return round(mean(a),2) if a else None
    summary = {
        "ws_short_avg": {k: avg(v) for k,v in ws_short.items()},
        "ws_long_avg":  {k: avg(v) for k,v in ws_long.items()},
        "http_short_avg": {k: avg(v) for k,v in http_short.items()},
        "http_long_avg":  {k: avg(v) for k,v in http_long.items()},
        "goal_ttft_ms": 800
    }
    json_path = Path(args.out) / "tts_summary.json"
    md_path   = Path(args.out) / "tts_summary.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(f"# TTS Bench Summary\n\n```\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n", encoding="utf-8")
    jlog("report_saved", path_json=str(json_path), path_md=str(md_path))

if __name__ == "__main__":
    asyncio.run(main())

Критерии приёмки
	•	Скрипт запускается одной командой, создаёт JSON и Markdown отчёты.
	•	В логах присутствуют ws_handshake_finish, ws_first_audio, http_first_byte.
	•	TTFT (WS) и TTFA (HTTP) считаются и усредняются. Есть сравнение с целью < 800 ms (в отчёте — goal_ttft_ms).



