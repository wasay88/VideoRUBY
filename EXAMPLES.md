# 📚 Примеры использования

## Базовое использование

### 1. GUI приложение (рекомендуется для начинающих)

```bash
python3 video_editor_app.py
```

Откроется окно программы с простым интерфейсом.

## Командная строка (для продвинутых)

### 2. Только удаление пауз

```bash
python3 video_processor.py мой_подкаст.mp4
```

**Результат:**
- `мой_подкаст_edited.mp4` - Видео без пауз

### 3. Только транскрипция и субтитры

```bash
python3 transcription.py мой_подкаст.mp4
```

**Результат:**
- `мой_подкаст.srt` - Субтитры

### 4. Создать FCPXML из готовых файлов

```bash
python3 fcpxml_generator.py видео.mp4 субтитры.srt
```

**Результат:**
- `видео.fcpxml` - Проект для Final Cut Pro

## Продвинутые сценарии

### 5. Обработка с кастомными параметрами

Отредактируйте `video_processor.py`:

```python
processor = VideoProcessor(
    silence_threshold_db=-40,  # Более агрессивное удаление
    min_silence_duration=0.3   # Удалять даже короткие паузы
)
```

### 6. Использование другой модели Whisper

Отредактируйте `transcription.py`:

```python
transcriber = Transcriber(
    model_size="medium",  # Лучшее качество
    language="ru"
)
```

### 7. Пакетная обработка нескольких видео

Создайте скрипт `batch_process.sh`:

```bash
#!/bin/bash

for video in *.mp4; do
    echo "Обрабатываю: $video"
    python3 video_processor.py "$video"
    python3 transcription.py "${video%.mp4}_edited.mp4"
done
```

Запуск:
```bash
chmod +x batch_process.sh
./batch_process.sh
```

## Интеграция в workflow

### 8. Автоматическая обработка при добавлении файла

Создайте LaunchAgent для macOS (автозапуск):

```xml
<!-- ~/Library/LaunchAgents/com.videoruby.watcher.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.videoruby.watcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/путь/к/video_processor.py</string>
        <string>/путь/к/папке/с/видео</string>
    </array>
    <key>WatchPaths</key>
    <array>
        <string>/путь/к/папке/с/видео</string>
    </array>
</dict>
</plist>
```

### 9. API использование (для разработчиков)

```python
from video_processor import VideoProcessor
from transcription import Transcriber
from fcpxml_generator import FCPXMLGenerator

# Настройка
processor = VideoProcessor(silence_threshold_db=-35, min_silence_duration=0.5)
transcriber = Transcriber(model_size="base", language="ru")
generator = FCPXMLGenerator()

# Обработка
video_path = "мое_видео.mp4"

# Шаг 1: Удаление пауз
result = processor.process_video(video_path)
edited_video = result['edited_video']

# Шаг 2: Транскрипция
subtitle_path = transcriber.transcribe(edited_video, output_format="srt")

# Шаг 3: FCPXML
fcpxml_path = edited_video.replace('.mp4', '.fcpxml')
generator.create_simple_fcpxml_with_srt(
    edited_video,
    subtitle_path,
    fcpxml_path,
    project_name="Мой Проект"
)

print(f"✅ Готово! FCPXML: {fcpxml_path}")
```

## Кастомизация

### 10. Изменить формат выходных субтитров

Whisper поддерживает: `srt`, `vtt`, `txt`, `json`, `tsv`

```python
transcriber.transcribe(video_path, output_format="vtt")
```

### 11. Экспорт только аудио с транскрипцией

```bash
# Извлечь аудио
ffmpeg -i видео.mp4 -vn -acodec pcm_s16le аудио.wav

# Транскрибировать
python3 transcription.py аудио.wav
```

### 12. Предпросмотр пауз без обработки

```python
from video_processor import VideoProcessor

processor = VideoProcessor()
silences = processor.detect_silences("видео.mp4")

print("Найденные паузы:")
for start, end in silences:
    duration = end - start
    print(f"  {start:.1f}с - {end:.1f}с (длительность: {duration:.1f}с)")
```

## Troubleshooting примеры

### 13. Проверка установки

```bash
# Проверить ffmpeg
ffmpeg -version

# Проверить Whisper
whisper --help

# Проверить Python модули
python3 -c "import whisper; print('Whisper OK')"
```

### 14. Тест на небольшом фрагменте

```bash
# Вырезать первые 30 секунд для теста
ffmpeg -i длинное_видео.mp4 -t 30 -c copy тест.mp4

# Обработать тестовый фрагмент
python3 video_processor.py тест.mp4
```

## Производительность

### 15. Мониторинг обработки

```bash
# Запуск с выводом времени
time python3 video_processor.py видео.mp4
```

### 16. Оптимизация для больших файлов

Для видео >1 час используйте модель `tiny` или `base`:

```python
transcriber = Transcriber(model_size="tiny", language="ru")
```

---

💡 **Совет**: Всегда тестируйте настройки на небольшом фрагменте видео перед обработкой длинного материала!
