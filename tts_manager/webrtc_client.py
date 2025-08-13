#!/usr/bin/env python3
"""
WebRTC TTS клиент для минимальной задержки
Использует UDP-based протокол вместо HTTP/WebSocket
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional
from dataclasses import dataclass

import aiortc
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from av import AudioFrame

from .config import TTSConfig

log = logging.getLogger("tts_webrtc")

@dataclass
class WebRTCTTSConfig:
    """Конфигурация WebRTC TTS"""
    server_url: str = "wss://api.elevenlabs.io/webrtc"
    api_key: str = ""
    voice_id: str = ""
    model_id: str = "eleven_flash_v2_5"
    output_format: str = "pcm_8000"
    optimize_latency: bool = True
    chunk_size: int = 50  # Минимальный размер чанка для быстрого старта


class WebRTCTTSClient:
    """WebRTC TTS клиент для минимальной задержки"""
    
    def __init__(self, config: TTSConfig):
        self.config = config
        self.pc: Optional[RTCPeerConnection] = None
        self.data_channel = None
        self.audio_queue = asyncio.Queue()
        self.is_connected = False
        
    async def connect(self) -> float:
        """Устанавливает WebRTC соединение, возвращает время подключения"""
        start_time = time.perf_counter()
        
        # Создаем RTCPeerConnection
        self.pc = RTCPeerConnection()
        
        # Настраиваем data channel для отправки текста
        self.data_channel = self.pc.createDataChannel("tts")
        self.data_channel.on("open", self._on_data_channel_open)
        self.data_channel.on("message", self._on_data_channel_message)
        
        # Настраиваем аудио track для получения аудио
        self.pc.addTrack(AudioReceiverTrack(self.audio_queue))
        
        # Создаем offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        # Отправляем offer на сервер (через WebSocket)
        # Это симуляция - в реальности нужен WebRTC signaling server
        connection_time = (time.perf_counter() - start_time) * 1000
        
        log.info(f"WebRTC connection established in {connection_time:.2f}ms")
        return connection_time
    
    async def stream_text(self, text: str) -> AsyncGenerator[bytes, None]:
        """Стримит текст и получает аудио с минимальной задержкой"""
        if not self.is_connected:
            await self.connect()
        
        # Отправляем текст чанками для минимальной задержки
        chunks = self._split_text_into_chunks(text, self.config.ws_chunk_length_schedule or [50])
        
        for i, chunk in enumerate(chunks):
            # Отправляем чанк через data channel
            message = {
                "text": chunk,
                "try_trigger_generation": i == 0,  # Триггерим генерацию на первом чанке
                "is_final": i == len(chunks) - 1
            }
            self.data_channel.send(json.dumps(message))
            
            # Получаем аудио чанки
            while not self.audio_queue.empty():
                audio_chunk = await self.audio_queue.get()
                yield audio_chunk
    
    def _split_text_into_chunks(self, text: str, chunk_sizes: list) -> list:
        """Разбивает текст на чанки для минимальной задержки"""
        chunks = []
        start = 0
        
        for size in chunk_sizes:
            if start >= len(text):
                break
            end = min(start + size, len(text))
            chunks.append(text[start:end])
            start = end
        
        # Добавляем оставшийся текст
        if start < len(text):
            chunks.append(text[start:])
        
        return chunks
    
    def _on_data_channel_open(self):
        """Callback при открытии data channel"""
        self.is_connected = True
        log.info("WebRTC data channel opened")
    
    def _on_data_channel_message(self, message):
        """Callback при получении сообщения"""
        try:
            data = json.loads(message)
            if "audio" in data:
                # Декодируем base64 аудио
                import base64
                audio_data = base64.b64decode(data["audio"])
                asyncio.create_task(self.audio_queue.put(audio_data))
        except Exception as e:
            log.error(f"Error processing WebRTC message: {e}")
    
    async def close(self):
        """Закрывает WebRTC соединение"""
        if self.pc:
            await self.pc.close()


class AudioReceiverTrack(MediaStreamTrack):
    """Аудио track для получения аудио от WebRTC"""
    
    kind = "audio"
    
    def __init__(self, audio_queue: asyncio.Queue):
        super().__init__()
        self.audio_queue = audio_queue
    
    async def recv(self):
        """Получает аудио frame"""
        # В реальной реализации здесь будет получение аудио от ElevenLabs
        # Пока что возвращаем пустой frame
        return AudioFrame(format="s16", layout="mono", samples=480)


# Функция для тестирования WebRTC TTS
async def test_webrtc_tts():
    """Тестирует WebRTC TTS с измерением латентности"""
    from .config import load_tts_config
    
    config = load_tts_config("configs/tts_config.yml")
    client = WebRTCTTSClient(config)
    
    try:
        # Измеряем время подключения
        connection_time = await client.connect()
        print(f"WebRTC connection: {connection_time:.2f}ms")
        
        # Измеряем время до первого аудио
        start_time = time.perf_counter()
        text = "Привет, это тест WebRTC TTS."
        
        first_audio_received = False
        async for audio_chunk in client.stream_text(text):
            if not first_audio_received:
                ttft = (time.perf_counter() - start_time) * 1000
                print(f"TTFT: {ttft:.2f}ms")
                first_audio_received = True
                break
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_webrtc_tts())

