📄 File 1 — SPEC-INFRA-1-Nginx-Gateway.md

Nginx Gateway (TLS, WSS, балансировка, трассировка)

Контекст

Этот слой — входная дверь системы: принимает HTTPS/WSS трафик, делает TLS-терминацию, балансирует на Gunicorn/Uvicorn, прокидывает заголовки для трассировки (включая X-Trace-ID) и корректно апгрейдит WebSocket. Target: /api/v1/call.

Мини-дерево

project_root/
├─ infra/
│  ├─ nginx/
│  │  ├─ nginx.conf
│  │  └─ conf.d/app.conf
│  └─ system/
│     └─ logrotate-nginx.conf
├─ docker-compose.yml           # (ниже шаблон)
└─ .env.example

Зависимости
	•	Nginx 1.24+ (официальный образ)
	•	Certs в infra/nginx/certs/ (или монтируем Let’s Encrypt)
	•	Ничего питоновского.

Требования
	•	TLS (443), редирект с 80 → 443.
	•	Поддержка WS-апгрейда.
	•	Проброс заголовков: X-Trace-ID (генерим, если нет), X-Forwarded-*.
	•	Таймауты: proxy_read_timeout 300s (стримы).
	•	Логи в JSON.

Конфиги

infra/nginx/nginx.conf

user  nginx;
worker_processes auto;
pid /var/run/nginx.pid;

events { worker_connections 4096; }

http {
  include       /etc/nginx/mime.types;
  default_type  application/octet-stream;
  sendfile      on;
  tcp_nopush    on;
  tcp_nodelay   on;
  keepalive_timeout  65;

  log_format json_combined escape=json
    '{'
      '"time":"$time_iso8601",'
      '"remote_addr":"$remote_addr",'
      '"request":"$request",'
      '"status":$status,'
      '"bytes_sent":$bytes_sent,'
      '"request_time":$request_time,'
      '"upstream_response_time":"$upstream_response_time",'
      '"trace_id":"$http_x_trace_id",'
      '"ua":"$http_user_agent"'
    '}';

  access_log /var/log/nginx/access.json json_combined;
  error_log  /var/log/nginx/error.log warn;

  include /etc/nginx/conf.d/*.conf;
}

infra/nginx/conf.d/app.conf

map $http_x_trace_id $trace_id {
  default $http_x_trace_id;
  "" $request_id; # генерим, если не пришёл
}

upstream app_upstream {
  server app:8000;               # docker service "app"
  keepalive 64;
}

server {
  listen 80;
  server_name _;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  server_name _;

  ssl_certificate     /etc/nginx/certs/fullchain.pem;
  ssl_certificate_key /etc/nginx/certs/privkey.pem;

  # WebSocket & API
  location /api/v1/call {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Trace-ID $trace_id;

    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    proxy_connect_timeout 30s;

    proxy_pass http://app_upstream;
  }

  # health
  location /healthz {
    proxy_pass http://app_upstream/healthz;
  }
}

docker-compose.yml (фрагмент с Nginx + App placeholder)

version: "3.9"
services:
  app:
    image: your-app-image:latest
    env_file: .env
    expose:
      - "8000"
    # command задаётся в SPEC-INFRA-2

  nginx:
    image: nginx:1.25
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./infra/nginx/conf.d:/etc/nginx/conf.d:ro
      - ./infra/nginx/certs:/etc/nginx/certs:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - app
    restart: unless-stopped

.env.example (фрагмент)

# App runtime
WORKERS=4
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000

# TLS пути (если монтируешь внутрь контейнера nginx уже готовые certbot)
# infra/nginx/certs/fullchain.pem
# infra/nginx/certs/privkey.pem

Приёмка
	•	docker compose up -d → https://localhost/api/v1/call даёт 101 Switching Protocols при WS.
	•	JSON-логи Nginx создаются в logs/nginx/access.json.
	•	Заголовок X-Trace-ID прокинут в приложение.

⸻

📄 File 2 — SPEC-INFRA-2-Application-Server.md

Application Tier: Gunicorn+Uvicorn (ASGI), WebSocket endpoint, health, запуск

Контекст

Этот слой исполняет наш ASGI-приложение с эндпоинтом /api/v1/call (WS). Gunicorn рулит воркерами, Uvicorn — асинхронный сервер. Тут же — минимальная «песочница» для локальных прогонов без Gunicorn.

Мини-дерево

project_root/
├─ webapi/
│  ├─ __init__.py
│  ├─ main.py               # ASGI-приложение (WS + healthz)
│  └─ gunicorn_conf.py      # Prod-конфиг для gunicorn
├─ scripts/
│  └─ run_app_dev.sh        # локальный запуск (uvicorn)
└─ .env.example

Зависимости
	•	Runtime: uvicorn[standard]>=0.30, gunicorn>=21, orjson, starlette>=0.36
	•	Stdlib: asyncio, json, os, time, logging, uuid

Контракты
	•	WebSocket /api/v1/call — ровно протокол из вашей спецификации (call_start, mediasoup_request, …).
	•	Health: GET /healthz → 200 OK + {"status":"ok"}.

Файлы

webapi/gunicorn_conf.py

import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WORKERS", (multiprocessing.cpu_count() * 2) + 1))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
graceful_timeout = 30
loglevel = "info"
accesslog = "-"
errorlog = "-"

# JSON access лог проксирует Nginx, тут достаточно stdout/stderr

webapi/main.py (минимальный каркас с «песочницей»)

from __future__ import annotations
import os, json, time, uuid, logging
from typing import Any, Dict
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("webapi")

def jlog(event: str, **fields):
    log.info(json.dumps({"event": event, **fields}, ensure_ascii=False))

async def healthz(request):
    return JSONResponse({"status": "ok"})

async def ws_call(websocket: WebSocket):
    await websocket.accept()
    # Trace
    trace_id = websocket.headers.get("x-trace-id") or str(uuid.uuid4())
    jlog("ws_accept", trace_id=trace_id)

    try:
        # Первое сообщение должно быть call_start
        msg = await websocket.receive_json()
        if not (isinstance(msg, dict) and msg.get("event") == "call_start"):
            await websocket.send_json({"event":"error","reason":"first message must be call_start"})
            await websocket.close()
            return

        payload = msg.get("payload") or {}
        call_id = payload.get("call_id") or str(uuid.uuid4())
        initial_vars = payload.get("initial_vars") or {}
        jlog("call_start", trace_id=trace_id, call_id=call_id, vars=initial_vars)

        # Ответ клиенту — accepted
        await websocket.send_json({"event":"call_accepted","payload":{"status":"ok"}})

        # Простейший цикл приёма/эха (заглушка вместо реального Orchestrator)
        while True:
            message = await websocket.receive_json()
            evt = message.get("event")
            if evt == "call_terminated":
                jlog("call_terminated", trace_id=trace_id, call_id=call_id)
                await websocket.close()
                break
            elif evt == "mediasoup_request":
                # эхо назад
                await websocket.send_json({"event":"mediasoup_response","payload":message.get("payload")})
            else:
                # игнор, лог
                jlog("unknown_event", trace_id=trace_id, event=evt)
    except Exception as e:
        jlog("ws_error", error=str(e))
        try:
            await websocket.close()
        except Exception:
            pass

routes = [
    Route("/healthz", endpoint=healthz),
    WebSocketRoute("/api/v1/call", endpoint=ws_call),
]
app = Starlette(routes=routes)

if __name__ == "__main__":
    # Песочница локально без gunicorn
    import uvicorn
    host = os.getenv("UVICORN_HOST", "127.0.0.1")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    uvicorn.run("webapi.main:app", host=host, port=port, reload=False, workers=1)

scripts/run_app_dev.sh

#!/usr/bin/env bash
set -euo pipefail
export UVICORN_HOST=${UVICORN_HOST:-127.0.0.1}
export UVICORN_PORT=${UVICORN_PORT:-8000}
python -m webapi.main

Make executable: chmod +x scripts/run_app_dev.sh

Запуск
	•	Dev: ./scripts/run_app_dev.sh → http://127.0.0.1:8000/healthz
	•	Prod (в контейнере): gunicorn webapi.main:app -c webapi/gunicorn_conf.py

Приёмка
	•	/healthz отвечает 200.
	•	WS-хэндшейк и обмен сообщениями отрабатывают (проверить вручную любым WS-клиентом).
	•	В логах есть события ws_accept, call_start, call_terminated.

⸻

📄 File 3 — SPEC-INFRA-3-Observability-Bench.md

Наблюдаемость, трассировка, health, e2e-проба WebSocket-канала

Контекст

Нужны: сквозная трассировка, метрики латентности (handshake, round-trip), JSON-логи, health-пробы и ручной бенч без pytest. Всё — отдельно от бизнес-логики.

Мини-дерево

project_root/
├─ infra/
│  ├─ logging.py               # JSON-логгер/утилиты
│  ├─ metrics.py               # простая метрика + сериализация
│  └─ probes/
│     └─ wss_probe.py          # e2e бенч WS, JSONL + Markdown отчёт
├─ logs/
│  └─ app/                     # складываем логи и отчёты
└─ .env.example

Зависимости
	•	Runtime: websockets>=12, orjson (опц.), python-dotenv
	•	Stdlib: asyncio, time, uuid, json, statistics, argparse, pathlib, logging

Файлы

infra/logging.py

from __future__ import annotations
import json, logging

def configure_json_logging(level=logging.INFO):
    logging.basicConfig(level=level, format="%(message)s")

def jlog(event: str, **fields):
    logging.getLogger("infra").info(json.dumps({"event": event, **fields}, ensure_ascii=False))

infra/metrics.py

from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import mean

@dataclass(slots=True)
class ProbeStats:
    handshake_ms: list[float]
    rtt_ms: list[float]

    def summary(self):
        def avg(v): return round(mean(v),2) if v else None
        return {"handshake_avg_ms": avg(self.handshake_ms), "rtt_avg_ms": avg(self.rtt_ms)}

infra/probes/wss_probe.py — ручной e2e-бенч

#!/usr/bin/env python3
from __future__ import annotations
import asyncio, websockets, time, json, uuid
from pathlib import Path
from statistics import mean
from argparse import ArgumentParser
from infra.logging import configure_json_logging, jlog

async def bench_once(url: str, trace_id: str):
    t0 = time.perf_counter()
    async with websockets.connect(url, extra_headers=[("X-Trace-ID", trace_id)]) as ws:
        hs_ms = (time.perf_counter() - t0) * 1000
        jlog("ws_handshake_finish", ms=round(hs_ms,2), trace_id=trace_id)

        await ws.send(json.dumps({
          "event":"call_start","payload":{"call_id":str(uuid.uuid4()),"trace_id":trace_id,"initial_vars":{"probe":True}}
        }))
        ack = await ws.recv()  # ожидаем call_accepted
        jlog("probe_ack", data=ack, trace_id=trace_id)

        # простейший round-trip: mediasoup_request -> mediasoup_response
        t1 = time.perf_counter()
        await ws.send(json.dumps({"event":"mediasoup_request","payload":{"echo":"ping"}}))
        resp = await ws.recv()
        rtt_ms = (time.perf_counter() - t1) * 1000
        jlog("probe_rtt", ms=round(rtt_ms,2), trace_id=trace_id)

        await ws.send(json.dumps({"event":"call_terminated"}))
        return hs_ms, rtt_ms

async def main():
    ap = ArgumentParser()
    ap.add_argument("--url", default="wss://localhost/api/v1/call")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--outdir", default="logs/app")
    args = ap.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    configure_json_logging()
    jsonl = Path(args.outdir) / "wss_probe.jsonl"
    md    = Path(args.outdir) / "wss_probe_summary.md"

    results = []
    for i in range(args.repeats):
        trace_id = str(uuid.uuid4())
        try:
            hs, rtt = await bench_once(args.url, trace_id)
            results.append((hs, rtt))
            with jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"handshake_ms":hs,"rtt_ms":rtt})+"\n")
        except Exception as e:
            with jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"error":str(e)})+"\n")

    if results:
        hs_list = [x[0] for x in results]
        rtt_list = [x[1] for x in results]
        summary = {
            "handshake_avg_ms": round(mean(hs_list),2),
            "rtt_avg_ms": round(mean(rtt_list),2),
            "goal_ttft_audio_ms": 800,  # целевой KPI
            "samples": len(results)
        }
        md.write_text("# WS Probe Summary\n\n```\n"+json.dumps(summary, ensure_ascii=False, indent=2)+"\n```\n", encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(main())

Health-checks
	•	Liveness: /healthz (см. File 2 — уже есть).
	•	Readiness: опционально добавить /readyz c проверкой зависимостей (Redis, TTS, STT), но НЕ блокирующее прод-трафик.

Логи/Трассировка
	•	Nginx JSON — уже настроен (File 1).
	•	Приложение — JSON (см. File 2 logging.basicConfig), X-Trace-ID прокидывается.
	•	Проба — JSONL + Markdown summary.

Приёмка
	•	python infra/probes/wss_probe.py --url wss://<host>/api/v1/call --repeats 5 создаёт logs/app/wss_probe.jsonl и wss_probe_summary.md.
	•	Средние значения отображаются; handshake стабилен, rtt предсказуем.
	•	Совместно с TTS/STT бенчами можно сопоставить TTFT аудио против целевого 800ms.