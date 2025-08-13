#!/usr/bin/env python3
"""
Мок-оркестратор для демонстрации
"""

import asyncio
import time
from typing import AsyncIterator, Optional, Callable


class OrchestratorMock:
    """
    Очень простой мок:
    - Возвращает "эхо" текста/аудио пользователя через синтетику: sine-бип + паузы,
      либо проксирует заранее подготовленный PCM 8k (если подложим).
    - Умеет "останавливать" текущий стрим по barge-in (через флаг).
    - Логирует t4/t5 события через колбэки (выставляет их наружу).
    """
    
    def __init__(self):
        self._stop_flag = False
        self.on_tts_first_chunk: Optional[Callable[[str, float], None]] = None  # callable(trace_id, ts)
        self.on_llm_request_done: Optional[Callable[[str, float], None]] = None  # callable(trace_id, ts)
    
    def stop_playback(self, trace_id: str):
        """Останавливает текущее воспроизведение"""
        print(f"🛑 OrchestratorMock: stop_playback called for {trace_id}")
        self._stop_flag = True
    
    async def get_audio_reply(self, trace_id: str, user_pcm8k: bytes) -> AsyncIterator[bytes]:
        """
        Генерирует 8к PCM монотоны. Для демо: сначала короткий сигнал, потом "эхо".
        Чанк ~20мс = 160 сэмплов = 320 байт (s16le mono).
        """
        print(f"🎵 OrchestratorMock: generating audio reply for {trace_id}, input size: {len(user_pcm8k)} bytes")
        
        # Имитация "LLM готовит ответ"
        await asyncio.sleep(0.12)
        if self.on_llm_request_done:
            self.on_llm_request_done(trace_id, time.monotonic())
        
        # Сброс флага остановки для нового запроса
        self._stop_flag = False
        
        frame = b"\x00\x00" * 160  # тишина 20мс
        beep = (b"\x7f\x00" * 80) + (b"\x00\x00" * 80)  # простой "бип" ~20мс
        
        # Первый "бип" как признак tts first chunk
        if self.on_tts_first_chunk:
            self.on_tts_first_chunk(trace_id, time.monotonic())
        
        print(f"🔊 OrchestratorMock: sending first beep for {trace_id}")
        yield beep
        
        # Затем 40 фреймов "тихой речи"
        for i in range(40):
            if self._stop_flag:
                print(f"⛔ OrchestratorMock: stopping playback for {trace_id} at frame {i}")
                self._stop_flag = False
                return
            
            await asyncio.sleep(0.02)  # 20ms delay
            yield frame
        
        print(f"✅ OrchestratorMock: finished audio reply for {trace_id}")
    
    async def on_speech_started(self, trace_id: str, ts_monotonic: float):
        """Обработка начала речи"""
        print(f"🗣️  OrchestratorMock: speech started {trace_id} at {ts_monotonic}")
    
    async def on_partial_audio(self, trace_id: str, pcm8k_chunk: bytes):
        """Обработка частичного аудио (пока не используется)"""
        pass
    
    async def on_speech_ended(self, trace_id: str, utterance_pcm8k: bytes, t_first_byte: float, t_last_byte: float):
        """Обработка конца речи"""
        duration_ms = (t_last_byte - t_first_byte) * 1000
        print(f"🏁 OrchestratorMock: speech ended {trace_id}, duration: {duration_ms:.1f}ms, size: {len(utterance_pcm8k)} bytes")
    
    async def on_barge_in_detected(self, trace_id: str):
        """Обработка barge-in"""
        print(f"⚡ OrchestratorMock: barge-in detected for {trace_id}")
        self.stop_playback(trace_id)
    
    async def play_filler(self, trace_id: str, key: str):
        """Воспроизведение заполнителя (на будущее)"""
        print(f"🎶 OrchestratorMock: play_filler {key} for {trace_id} (not implemented)")
        pass
