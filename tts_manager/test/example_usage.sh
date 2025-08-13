#!/bin/bash

echo "🎵 TTS Audio Playback Examples"
echo "=============================="

# Проверяем наличие конфигурации
if [ ! -f "configs/tts_config.yml" ]; then
    echo "❌ Error: configs/tts_config.yml not found"
    echo "Please make sure you have the TTS configuration file"
    exit 1
fi

echo ""
echo "1. 🚀 Quick test with audio playback:"
echo "python3 tts_manager/test/test_audio_playback.py --save-audio --play-audio"
echo ""

echo "2. 📊 Full benchmark with audio:"
echo "python3 tts_manager/test/manual_test_tts.py --save-audio --play-audio --repeats 2"
echo ""

echo "3. 🎯 Custom text test:"
echo "python3 tts_manager/test/test_audio_playback.py --save-audio --play-audio --text 'Привет! Это тест ElevenLabs TTS.'"
echo ""

echo "4. 📁 Save audio only (no playback):"
echo "python3 tts_manager/test/manual_test_tts.py --save-audio --repeats 1"
echo ""

echo "5. 🔊 Play audio only (no saving):"
echo "python3 tts_manager/test/manual_test_tts.py --play-audio --repeats 1"
echo ""

echo "📖 For more information, see: tts_manager/test/README_audio_playback.md"
echo ""
echo "💡 Tip: Use --repeats 1 for quick testing"
