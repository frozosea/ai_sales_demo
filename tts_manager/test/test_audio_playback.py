#!/usr/bin/env python3
"""
Простой тест для демонстрации воспроизведения аудио в TTS тестах
"""

import asyncio
import argparse
from pathlib import Path

from tts_manager.test.manual_test_tts import TTSBenchmark


async def test_audio_playback():
    """Тестирует функциональность сохранения и воспроизведения аудио"""
    parser = argparse.ArgumentParser(description="TTS Audio Playback Test")
    parser.add_argument("--config", default="configs/tts_config.yml", help="Path to TTS config")
    parser.add_argument("--out", default="reports", help="Output directory for reports")
    parser.add_argument("--text", default="Привет! Это тест воспроизведения аудио.", help="Text to synthesize")
    parser.add_argument("--save-audio", action="store_true", help="Save generated audio files")
    parser.add_argument("--play-audio", action="store_true", help="Play generated audio files")
    
    args = parser.parse_args()
    
    print(f"🎵 TTS Audio Playback Test")
    print(f"📝 Text: {args.text}")
    print(f"💾 Save audio: {args.save_audio}")
    print(f"🔊 Play audio: {args.play_audio}")
    print(f"📁 Output: {args.out}")
    print("-" * 50)
    
    # Создаем бенчмарк с одним повторением
    benchmark = TTSBenchmark(
        config_path=args.config,
        output_dir=args.out,
        repeats=1,  # Только одно повторение для демонстрации
        save_audio=args.save_audio,
        play_audio=args.play_audio
    )
    
    try:
        await benchmark.setup()
        
        # Тестируем только HTTP для простоты
        print("🚀 Starting HTTP test...")
        results = await benchmark.run_http_case(args.text, "demo_test")
        
        print("✅ Test completed!")
        
        if args.save_audio:
            print(f"📁 Audio files saved to: {benchmark.audio_dir}")
        
        if args.play_audio:
            print("🔊 Audio playback completed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(test_audio_playback())
