#!/usr/bin/env python3
"""
Модуль транскрипции и генерации субтитров
Использует OpenAI Whisper для распознавания русской речи
"""

import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict


class Transcriber:
    """Класс для транскрипции аудио в текст"""

    def __init__(self, model_size: str = "base", language: str = "ru"):
        """
        Args:
            model_size: Размер модели Whisper (tiny, base, small, medium, large)
            language: Код языка (ru для русского)
        """
        self.model_size = model_size
        self.language = language

    def check_whisper_installed(self) -> bool:
        """Проверяет установлен ли Whisper"""
        try:
            result = subprocess.run(
                ['whisper', '--help'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def transcribe(self, video_path: str, output_format: str = "srt") -> str:
        """
        Транскрибирует видео и создает субтитры

        Args:
            video_path: Путь к видео файлу
            output_format: Формат субтитров (srt, vtt, txt, json)

        Returns:
            Путь к файлу с субтитрами
        """
        print(f"🎤 Транскрибирую аудио (модель: {self.model_size}, язык: {self.language})...")

        if not self.check_whisper_installed():
            raise RuntimeError(
                "Whisper не установлен. Установите командой:\n"
                "pip install openai-whisper"
            )

        video_path = os.path.abspath(video_path)
        output_dir = os.path.dirname(video_path)

        # Запускаем Whisper
        cmd = [
            'whisper',
            video_path,
            '--model', self.model_size,
            '--language', self.language,
            '--output_format', output_format,
            '--output_dir', output_dir
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Ошибка транскрипции: {result.stderr}")

        # Определяем путь к созданному файлу субтитров
        base_name = Path(video_path).stem
        subtitle_path = os.path.join(output_dir, f"{base_name}.{output_format}")

        if os.path.exists(subtitle_path):
            print(f"✅ Субтитры созданы: {subtitle_path}")
            return subtitle_path
        else:
            raise FileNotFoundError(f"Файл субтитров не найден: {subtitle_path}")

    def transcribe_segments(self, video_path: str, segments: List) -> List[Dict]:
        """
        Транскрибирует конкретные сегменты видео

        Args:
            video_path: Путь к видео
            segments: Список сегментов (из video_processor)

        Returns:
            Список субтитров с временными метками
        """
        # Сначала получаем полную транскрипцию
        subtitle_path = self.transcribe(video_path, output_format="json")

        # Читаем JSON с транскрипцией
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            transcription_data = json.load(f)

        # Whisper JSON содержит сегменты с временными метками
        whisper_segments = transcription_data.get('segments', [])

        subtitles = []
        for seg in whisper_segments:
            subtitles.append({
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text'].strip()
            })

        return subtitles


class SubtitleGenerator:
    """Генератор субтитров в различных форматах"""

    @staticmethod
    def format_time_srt(seconds: float) -> str:
        """Форматирует время для SRT формата"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def generate_srt(subtitles: List[Dict], output_path: str):
        """
        Генерирует SRT файл

        Args:
            subtitles: Список словарей с ключами start, end, text
            output_path: Путь для сохранения SRT файла
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitles, 1):
                start_time = SubtitleGenerator.format_time_srt(sub['start'])
                end_time = SubtitleGenerator.format_time_srt(sub['end'])

                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{sub['text']}\n")
                f.write("\n")

        print(f"✅ SRT субтитры сохранены: {output_path}")

    @staticmethod
    def adjust_subtitles_for_edited_video(
        subtitles: List[Dict],
        segments: List,
        output_path: str
    ):
        """
        Корректирует временные метки субтитров для отредактированного видео
        (после удаления пауз)

        Args:
            subtitles: Оригинальные субтитры
            segments: Сегменты из video_processor
            output_path: Путь для сохранения скорректированных субтитров
        """
        # Создаем маппинг старого времени на новое
        speech_segments = [s for s in segments if s.is_speech]

        adjusted_subtitles = []
        accumulated_time = 0

        for sub in subtitles:
            sub_start = sub['start']
            sub_end = sub['end']

            # Находим в каком сегменте находится этот субтитр
            for seg in speech_segments:
                if seg.start <= sub_start <= seg.end:
                    # Вычисляем смещение внутри сегмента
                    offset_in_segment = sub_start - seg.start
                    new_start = accumulated_time + offset_in_segment

                    # Вычисляем новое время окончания
                    duration = sub_end - sub_start
                    new_end = new_start + duration

                    adjusted_subtitles.append({
                        'start': new_start,
                        'end': new_end,
                        'text': sub['text']
                    })
                    break

            # Обновляем накопленное время после каждого сегмента
            for seg in speech_segments:
                if seg.end <= sub_start:
                    accumulated_time = seg.end - seg.start

        # Сохраняем скорректированные субтитры
        SubtitleGenerator.generate_srt(adjusted_subtitles, output_path)

        return adjusted_subtitles


if __name__ == '__main__':
    # Тестовый запуск
    import sys

    if len(sys.argv) < 2:
        print("Использование: python transcription.py <путь_к_видео>")
        sys.exit(1)

    video_path = sys.argv[1]
    transcriber = Transcriber(model_size="base", language="ru")

    # Транскрибируем
    subtitle_path = transcriber.transcribe(video_path, output_format="srt")
    print(f"\n✅ Готово! Субтитры: {subtitle_path}")
