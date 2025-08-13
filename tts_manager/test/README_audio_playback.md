# TTS Audio Playback Functionality

Добавлена возможность сохранения и воспроизведения аудио, сгенерированного в тестах TTS.

## Новые возможности

### 1. Сохранение аудио файлов
- Аудио файлы сохраняются в формате MP3
- Файлы сохраняются в папку `reports/audio_samples/`
- Имена файлов включают ID звонка и временную метку

### 2. Автоматическое воспроизведение
- Поддержка macOS (afplay)
- Поддержка Linux (aplay, paplay, mpg123, ffplay)
- Поддержка Windows (start command)

## Использование

### Полный бенчмарк с аудио

```bash
# Сохранять и воспроизводить аудио
python3 tts_manager/test/manual_test_tts.py --save-audio --play-audio

# Только сохранять аудио
python3 tts_manager/test/manual_test_tts.py --save-audio

# Только воспроизводить аудио (без сохранения)
python3 tts_manager/test/manual_test_tts.py --play-audio

# Кастомный текст
python3 tts_manager/test/manual_test_tts.py --save-audio --play-audio \
  --ws-chunk "Привет! Это тест." \
  --http-chunk "Привет! Это тест."
```

### Простой тест воспроизведения

```bash
# Быстрый тест с одним повторением
python3 tts_manager/test/test_audio_playback.py --save-audio --play-audio

# Кастомный текст
python3 tts_manager/test/test_audio_playback.py --save-audio --play-audio \
  --text "Это кастомный текст для тестирования TTS."
```

## Структура файлов

```
reports/
├── audio_samples/
│   ├── ws_short_1_143022.mp3
│   ├── ws_long_1_143025.mp3
│   ├── http_short_1_143028.mp3
│   └── http_long_1_143031.mp3
├── tts_summary_20240810-143000.json
└── tts_summary_20240810-143000.md
```

## Логирование

В логах появляются новые события:

```json
{"event": "audio_saved", "path": "reports/audio_samples/ws_short_1_143022.mp3", "size_bytes": 45678}
{"event": "audio_play_start", "call_id": "ws_short_1", "filename": "ws_short_1_143022.mp3"}
{"event": "audio_played", "path": "reports/audio_samples/ws_short_1_143022.mp3"}
```

## Требования

### macOS
- Встроенный `afplay` (уже установлен)

### Linux
- Один из: `aplay`, `paplay`, `mpg123`, `ffplay`
- Установка: `sudo apt install mpg123` или `sudo apt install ffmpeg`

### Windows
- Встроенный плеер по умолчанию

## Примеры использования

### 1. Тестирование качества речи
```bash
python3 tts_manager/test/manual_test_tts.py --save-audio --play-audio \
  --ws-chunk "Стоимость 12000 рублей." \
  --http-chunk "Стоимость 12000 рублей."
```

### 2. Тестирование длинных фраз
```bash
python3 tts_manager/test/manual_test_tts.py --save-audio --play-audio \
  --ws-long "Это очень длинная фраза для тестирования стабильности системы..." \
  --http-long "Это очень длинная фраза для тестирования стабильности системы..."
```

### 3. Быстрая проверка
```bash
python3 tts_manager/test/test_audio_playback.py --save-audio --play-audio \
  --text "Привет! Как дела?"
```

## Примечания

- Аудио воспроизводится сразу после генерации каждого теста
- Файлы сохраняются только если включена опция `--save-audio`
- Воспроизведение работает только если включена опция `--play-audio`
- При ошибках воспроизведения в логах появляются соответствующие сообщения
