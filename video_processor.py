#!/usr/bin/env python3
"""
Локальная система обработки видео для Final Cut Pro
Аналог Gling.ai - удаление пауз + автоматические субтитры
"""

import os
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
import tempfile


@dataclass
class Segment:
    """Сегмент видео с временными метками"""
    start: float  # секунды
    end: float    # секунды
    is_speech: bool  # True если речь, False если пауза


class VideoProcessor:
    """Основной класс для обработки видео"""

    def __init__(self, silence_threshold_db: float = -35, min_silence_duration: float = 0.5):
        """
        Args:
            silence_threshold_db: Порог тишины в dB (по умолчанию -35)
            min_silence_duration: Минимальная длительность паузы для удаления (секунды)
        """
        self.silence_threshold = silence_threshold_db
        self.min_silence_duration = min_silence_duration

    def detect_silences(self, video_path: str) -> List[Tuple[float, float]]:
        """
        Определяет паузы в видео используя ffmpeg

        Returns:
            Список кортежей (start_time, end_time) для каждой паузы
        """
        print("🔍 Анализирую аудио для поиска пауз...")

        # Используем ffmpeg silencedetect фильтр
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-af', f'silencedetect=noise={self.silence_threshold}dB:d={self.min_silence_duration}',
            '-f', 'null',
            '-'
        ]

        result = subprocess.run(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )

        # Парсим вывод ffmpeg
        silences = []
        silence_start = None

        for line in result.stderr.split('\n'):
            if 'silence_start:' in line:
                silence_start = float(line.split('silence_start:')[1].strip())
            elif 'silence_end:' in line and silence_start is not None:
                silence_end = float(line.split('silence_end:')[1].split('|')[0].strip())
                silences.append((silence_start, silence_end))
                silence_start = None

        print(f"✅ Найдено пауз: {len(silences)}")
        return silences

    def get_video_duration(self, video_path: str) -> float:
        """Получает длительность видео"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())

    def create_segments(self, video_duration: float, silences: List[Tuple[float, float]]) -> List[Segment]:
        """
        Создает сегменты речи и пауз

        Args:
            video_duration: Общая длительность видео
            silences: Список пауз

        Returns:
            Список сегментов
        """
        segments = []
        current_time = 0

        for silence_start, silence_end in silences:
            # Добавляем речевой сегмент перед паузой
            if silence_start > current_time:
                segments.append(Segment(
                    start=current_time,
                    end=silence_start,
                    is_speech=True
                ))

            # Добавляем паузу
            segments.append(Segment(
                start=silence_start,
                end=silence_end,
                is_speech=False
            ))

            current_time = silence_end

        # Добавляем последний речевой сегмент
        if current_time < video_duration:
            segments.append(Segment(
                start=current_time,
                end=video_duration,
                is_speech=True
            ))

        return segments

    def remove_silences(self, video_path: str, output_path: str, segments: List[Segment]) -> str:
        """
        Удаляет паузы из видео и создает новый файл

        Args:
            video_path: Путь к исходному видео
            output_path: Путь для сохранения обработанного видео
            segments: Список сегментов

        Returns:
            Путь к обработанному видео
        """
        print("✂️  Удаляю паузы из видео...")

        # Фильтруем только речевые сегменты
        speech_segments = [s for s in segments if s.is_speech]

        if not speech_segments:
            print("⚠️  Не найдено речевых сегментов!")
            return video_path

        # Создаем временный файл для конкатенации
        temp_dir = tempfile.mkdtemp()
        concat_file = os.path.join(temp_dir, 'concat_list.txt')
        segment_files = []

        # Вырезаем каждый речевой сегмент
        for i, seg in enumerate(speech_segments):
            segment_path = os.path.join(temp_dir, f'segment_{i:04d}.mp4')
            segment_files.append(segment_path)

            duration = seg.end - seg.start

            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(seg.start),
                '-t', str(duration),
                '-c', 'copy',
                '-y',
                segment_path
            ]

            subprocess.run(cmd, capture_output=True)

        # Создаем файл для конкатенации
        with open(concat_file, 'w') as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file}'\n")

        # Объединяем все сегменты
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            '-y',
            output_path
        ]

        subprocess.run(cmd, capture_output=True)

        # Очищаем временные файлы
        for seg_file in segment_files:
            try:
                os.remove(seg_file)
            except:
                pass
        try:
            os.remove(concat_file)
            os.rmdir(temp_dir)
        except:
            pass

        print(f"✅ Видео обработано: {output_path}")
        return output_path

    def process_video(self, video_path: str, output_dir: str = None) -> dict:
        """
        Полная обработка видео: анализ пауз и создание отредактированной версии

        Args:
            video_path: Путь к исходному видео
            output_dir: Директория для сохранения (по умолчанию - та же что и исходное видео)

        Returns:
            Словарь с результатами обработки
        """
        video_path = os.path.abspath(video_path)

        if output_dir is None:
            output_dir = os.path.dirname(video_path)

        # Создаем имя для выходного файла
        base_name = Path(video_path).stem
        output_video = os.path.join(output_dir, f"{base_name}_edited.mp4")

        # Получаем длительность
        duration = self.get_video_duration(video_path)

        # Находим паузы
        silences = self.detect_silences(video_path)

        # Создаем сегменты
        segments = self.create_segments(duration, silences)

        # Считаем статистику
        total_silence = sum(s.end - s.start for s in segments if not s.is_speech)
        total_speech = sum(s.end - s.start for s in segments if s.is_speech)

        print(f"\n📊 Статистика:")
        print(f"   Исходная длительность: {duration:.1f}с")
        print(f"   Речь: {total_speech:.1f}с ({total_speech/duration*100:.1f}%)")
        print(f"   Паузы: {total_silence:.1f}с ({total_silence/duration*100:.1f}%)")
        print(f"   Новая длительность: {total_speech:.1f}с")
        print(f"   Экономия времени: {total_silence:.1f}с\n")

        # Удаляем паузы
        edited_video = self.remove_silences(video_path, output_video, segments)

        return {
            'original_video': video_path,
            'edited_video': edited_video,
            'segments': segments,
            'statistics': {
                'original_duration': duration,
                'speech_duration': total_speech,
                'silence_duration': total_silence,
                'silences_removed': len([s for s in segments if not s.is_speech])
            }
        }


if __name__ == '__main__':
    # Тестовый запуск
    import sys

    if len(sys.argv) < 2:
        print("Использование: python video_processor.py <путь_к_видео>")
        sys.exit(1)

    video_path = sys.argv[1]
    processor = VideoProcessor(silence_threshold_db=-35, min_silence_duration=0.5)
    result = processor.process_video(video_path)

    print(f"\n✅ Готово! Обработанное видео: {result['edited_video']}")
