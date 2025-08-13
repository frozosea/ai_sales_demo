# Changelog: Audio Playback Feature

## Добавлено в manual_test_tts.py

### Новые параметры конструктора TTSBenchmark
- `save_audio: bool = False` - включить сохранение аудио файлов
- `play_audio: bool = False` - включить автоматическое воспроизведение

### Новые методы
- `save_audio_file(audio_data: bytes, filename: str) -> Optional[Path]` - сохранение аудио в файл
- `play_audio_file(file_path: Path) -> bool` - воспроизведение аудио файла

### Модифицированные методы
- `run_ws_case()` - добавлено сохранение и воспроизведение аудио чанков
- `run_http_case()` - добавлено сохранение и воспроизведение аудио чанков

### Новые аргументы командной строки
- `--save-audio` - сохранять сгенерированные аудио файлы
- `--play-audio` - воспроизводить сгенерированные аудио файлы

## Новые файлы

### test_audio_playback.py
- Простой тестовый скрипт для демонстрации функциональности
- Одно повторение для быстрого тестирования
- Поддержка кастомного текста

### README_audio_playback.md
- Подробная документация по использованию
- Примеры команд
- Требования для разных ОС

### example_usage.sh
- Скрипт с примерами использования
- Проверка наличия конфигурации

## Структура файлов

```
tts_manager/test/
├── manual_test_tts.py (модифицирован)
├── test_audio_playback.py (новый)
├── README_audio_playback.md (новый)
├── example_usage.sh (новый)
└── CHANGELOG_audio.md (этот файл)
```

## Логирование

### Новые события
- `audio_saved` - аудио файл сохранен
- `audio_play_start` - начало воспроизведения
- `audio_played` - воспроизведение завершено
- `audio_save_error` - ошибка сохранения
- `audio_play_error` - ошибка воспроизведения

## Поддерживаемые ОС

### macOS
- `afplay` (встроенный)

### Linux
- `aplay`, `paplay`, `mpg123`, `ffplay`

### Windows
- Встроенный плеер по умолчанию

## Использование

```bash
# Полный бенчмарк с аудио
python3 tts_manager/test/manual_test_tts.py --save-audio --play-audio

# Быстрый тест
python3 tts_manager/test/test_audio_playback.py --save-audio --play-audio

# Показать примеры
./tts_manager/test/example_usage.sh
```
