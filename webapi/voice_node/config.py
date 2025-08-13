#!/usr/bin/env python3
"""
Конфигурация для Voice Node
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class VoiceNodeConfig:
    """Конфигурация Voice Node с настройками из env"""
    
    def __init__(self):
        # LiveKit
        self.livekit_url: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
        self.livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "devkey")
        self.livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "secret")
        
        # Room/Identity
        self.room: str = os.getenv("LK_ROOM", "demo")
        self.bot_identity: str = os.getenv("LK_BOT_IDENTITY", "ingobot")
        self.user_publish_audio: bool = os.getenv("LK_USER_PUBLISH_AUDIO", "true").lower() == "true"
        
        # Audio settings
        self.audio_target_rate: int = int(os.getenv("AUDIO_TARGET_RATE", "8000"))
        self.audio_frame_ms: int = int(os.getenv("AUDIO_FRAME_MS", "20"))
        self.audio_channels: int = int(os.getenv("AUDIO_CHANNELS", "1"))
        
        # Derived audio settings
        self.samples_per_frame = int(self.audio_target_rate * self.audio_frame_ms / 1000)  # 160 for 8kHz, 20ms
        self.bytes_per_frame = self.samples_per_frame * 2 * self.audio_channels  # 320 for s16le mono
        
        # VAD settings
        self.vad_backend: str = os.getenv("VAD_BACKEND", "webrtc")  # sierra or webrtc
        self.vad_speech_start_frames: int = int(os.getenv("VAD_SPEECH_START_FRAMES", "6"))
        self.vad_speech_end_frames: int = int(os.getenv("VAD_SPEECH_END_FRAMES", "10"))
        
        # LiveKit tracks
        self.publish_track_name: str = os.getenv("PUBLISH_TRACK_NAME", "bot_out")
        
        # Logging
        self.log_file: str = os.getenv("LOG_FILE", "voice_node.log")
        self.metrics_file: str = os.getenv("METRICS_FILE", "metrics.jsonl")
        
        # Debug
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    def validate(self) -> bool:
        """Проверяет корректность конфигурации"""
        if not self.livekit_api_key or not self.livekit_api_secret:
            return False
        
        if self.audio_target_rate not in [8000, 16000, 48000]:
            return False
            
        if self.audio_frame_ms not in [10, 20, 30]:
            return False
            
        return True
    
    def __str__(self) -> str:
        return f"VoiceNodeConfig(room={self.room}, rate={self.audio_target_rate}, frame_ms={self.audio_frame_ms})"


# Global config instance
config = VoiceNodeConfig()
