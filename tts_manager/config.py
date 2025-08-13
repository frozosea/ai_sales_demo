from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import os
import logging
import json
import yaml
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
    http_output_format: str = "pcm_8000"
    optimize_streaming_latency: Optional[int] = 4  # 0..4, 4 = самый быстрый

    # WebSocket streaming
    ws_base_url: str = "wss://api.elevenlabs.io"
    ws_inactivity_timeout: int = 20           # seconds (<=180)
    ws_auto_mode: bool = True                 # снижает задержку
    ws_enable_ssml_parsing: bool = False
    ws_output_format: str = "pcm_8000"        # унификация с http
    ws_keep_alive_sec: float = 15.0
    ws_connect_timeout_sec: float = 10.0

    # Voice settings (передаются при initialize)
    voice_speed: float = 1.0
    voice_stability: float = 0.5
    voice_similarity_boost: float = 0.8
    language_code: Optional[str] = None       # например 'ru'


def _jlog(event: str, **fields):
    """Логирование в JSON формате"""
    log.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


def load_tts_config(yaml_path: str | Path) -> TTSConfig:
    """Загружает конфигурацию TTS из YAML файла с подстановкой переменных окружения"""
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
        http_base_url=data.get("http_base_url", "https://api.elevenlabs.io"),
        http_timeout_sec=float(data.get("http_timeout_sec", 20.0)),
        http_output_format=data.get("http_output_format", "pcm_8000"),
        optimize_streaming_latency=data.get("optimize_streaming_latency", 4),
        ws_base_url=data.get("ws_base_url", "wss://api.elevenlabs.io"),
        ws_inactivity_timeout=int(data.get("ws_inactivity_timeout", 20)),
        ws_auto_mode=bool(data.get("ws_auto_mode", True)),
        ws_enable_ssml_parsing=bool(data.get("ws_enable_ssml_parsing", False)),
        ws_output_format=data.get("ws_output_format", "pcm_8000"),
        ws_keep_alive_sec=float(data.get("ws_keep_alive_sec", 15.0)),
        ws_connect_timeout_sec=float(data.get("ws_connect_timeout_sec", 10.0)),
        voice_speed=float(data.get("voice_speed", 1.0)),
        voice_stability=float(data.get("voice_stability", 0.5)),
        voice_similarity_boost=float(data.get("voice_similarity_boost", 0.8)),
        language_code=data.get("language_code", None),
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
    import logging
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    path = sys.argv[1] if len(sys.argv) > 1 else "configs/tts_config.yml"
    
    try:
        cfg = load_tts_config(path)
        print(f"✅ TTSConfig loaded successfully:")
        print(f"   API Key: {cfg.api_key[:10]}..." if cfg.api_key else "   API Key: NOT SET")
        print(f"   Voice ID: {cfg.voice_id}")
        print(f"   Model ID: {cfg.model_id}")
        print(f"   HTTP Format: {cfg.http_output_format}")
        print(f"   WS Format: {cfg.ws_output_format}")
        print(f"   Language: {cfg.language_code}")
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)
