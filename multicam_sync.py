#!/usr/bin/env python3
"""
Multicam Synchronizer - Синхронизация нескольких камер

Автоматически синхронизирует видео с нескольких камер по:
1. Аудио-форме волны (waveform matching)
2. Временным меткам
3. Визуальным маркерам (хлопушка)

Идеально для:
- Подкастов
- Интервью
- Многокамерных съемок
"""

import os
import subprocess
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SyncResult:
    """Результат синхронизации"""
    video_path: str
    offset: float  # Смещение относительно референса (секунды)
    confidence: float  # Уверенность в синхронизации (0-1)
    method: str  # Метод синхронизации


class MulticamSync:
    """
    Синхронизация нескольких видео по аудио
    """

    def __init__(self, reference_video: Optional[str] = None):
        """
        Args:
            reference_video: Путь к референсному видео (если None, используется первое)
        """
        self.reference_video = reference_video

    def sync_videos(
        self,
        videos: List[str],
        method: str = 'waveform'
    ) -> List[SyncResult]:
        """
        Синхронизирует список видео

        Args:
            videos: Список путей к видео файлам
            method: Метод синхронизации ('waveform', 'timestamps', 'clap')

        Returns:
            Список результатов синхронизации для каждого видео
        """
        if len(videos) < 2:
            raise ValueError("Нужно минимум 2 видео для синхронизации")

        # Используем первое видео как референс, если не указано
        if self.reference_video is None:
            self.reference_video = videos[0]

        print(f"📹 Синхронизация {len(videos)} видео...")
        print(f"   Референс: {Path(self.reference_video).name}")

        results = []

        # Референсное видео имеет offset = 0
        results.append(SyncResult(
            video_path=self.reference_video,
            offset=0.0,
            confidence=1.0,
            method='reference'
        ))

        # Синхронизируем остальные видео
        for video in videos:
            if video == self.reference_video:
                continue

            print(f"\n🔄 Синхронизирую: {Path(video).name}")

            if method == 'waveform':
                result = self._sync_by_waveform(video)
            elif method == 'timestamps':
                result = self._sync_by_timestamps(video)
            elif method == 'clap':
                result = self._sync_by_clap(video)
            else:
                raise ValueError(f"Неизвестный метод: {method}")

            results.append(result)

        return results

    def _sync_by_waveform(self, video_path: str) -> SyncResult:
        """
        Синхронизация по аудио waveform
        Находит совпадающие паттерны в аудиодорожках
        """
        print("   Метод: waveform matching")

        try:
            # Извлекаем аудио из обоих видео
            ref_audio = self._extract_audio_samples(self.reference_video)
            video_audio = self._extract_audio_samples(video_path)

            # Находим сдвиг через кросс-корреляцию
            offset, confidence = self._find_audio_offset(ref_audio, video_audio)

            print(f"   ✅ Смещение: {offset:.3f}s (уверенность: {confidence:.1%})")

            return SyncResult(
                video_path=video_path,
                offset=offset,
                confidence=confidence,
                method='waveform'
            )

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            # Fallback на временные метки
            return self._sync_by_timestamps(video_path)

    def _extract_audio_samples(
        self,
        video_path: str,
        sample_rate: int = 16000,
        duration: Optional[float] = None
    ) -> np.ndarray:
        """
        Извлекает аудио как numpy массив

        Args:
            video_path: Путь к видео
            sample_rate: Частота дискретизации
            duration: Длительность для извлечения (None = всё видео)

        Returns:
            numpy массив аудио сэмплов
        """
        # Извлекаем аудио через ffmpeg
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # Только аудио
            '-acodec', 'pcm_s16le',
            '-ar', str(sample_rate),
            '-ac', '1',  # Моно
        ]

        if duration:
            cmd.extend(['-t', str(duration)])

        cmd.extend(['-f', 'wav', '-'])

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )

        # Конвертируем WAV в numpy
        # Пропускаем WAV заголовок (44 байта)
        audio_bytes = result.stdout[44:]
        audio_samples = np.frombuffer(audio_bytes, dtype=np.int16)

        # Нормализуем
        audio_samples = audio_samples.astype(np.float32) / 32768.0

        return audio_samples

    def _find_audio_offset(
        self,
        ref_audio: np.ndarray,
        video_audio: np.ndarray,
        max_offset: float = 300.0  # Максимальный сдвиг (секунды)
    ) -> Tuple[float, float]:
        """
        Находит временной сдвиг между двумя аудио через кросс-корреляцию

        Args:
            ref_audio: Референсное аудио
            video_audio: Видео аудио для синхронизации
            max_offset: Максимальный ожидаемый сдвиг

        Returns:
            (offset, confidence) - сдвиг в секундах и уверенность
        """
        # Ограничиваем размер для производительности
        # Используем первые N секунд (достаточно для синхронизации)
        sample_rate = 16000
        max_samples = int(60 * sample_rate)  # Анализируем первую минуту

        ref_clip = ref_audio[:max_samples]
        video_clip = video_audio[:max_samples]

        # Вычисляем кросс-корреляцию
        # Это находит оптимальный сдвиг для максимального совпадения
        correlation = np.correlate(ref_clip, video_clip, mode='full')

        # Находим пик корреляции
        peak_index = np.argmax(correlation)

        # Конвертируем индекс в секунды
        offset = (peak_index - len(ref_clip) + 1) / sample_rate

        # Вычисляем уверенность (нормализованная корреляция)
        max_corr = correlation[peak_index]
        # Нормализуем по энергии сигналов
        ref_energy = np.sum(ref_clip ** 2)
        video_energy = np.sum(video_clip ** 2)
        confidence = max_corr / np.sqrt(ref_energy * video_energy)

        # Ограничиваем confidence в разумных пределах
        confidence = min(abs(confidence), 1.0)

        return offset, confidence

    def _sync_by_timestamps(self, video_path: str) -> SyncResult:
        """
        Синхронизация по временным меткам в метаданных
        Использует creation_time из видеофайла
        """
        print("   Метод: timestamps")

        try:
            # Получаем timestamp референса
            ref_time = self._get_video_timestamp(self.reference_video)
            video_time = self._get_video_timestamp(video_path)

            if ref_time and video_time:
                # Вычисляем разницу
                offset = (video_time - ref_time).total_seconds()
                confidence = 0.9  # Высокая уверенность для timestamp

                print(f"   ✅ Смещение: {offset:.3f}s")

                return SyncResult(
                    video_path=video_path,
                    offset=offset,
                    confidence=confidence,
                    method='timestamps'
                )
            else:
                raise ValueError("Временные метки не найдены")

        except Exception as e:
            print(f"   ⚠️  Не удалось синхронизировать по timestamps: {e}")
            # Возвращаем нулевой offset с низкой уверенностью
            return SyncResult(
                video_path=video_path,
                offset=0.0,
                confidence=0.1,
                method='manual_needed'
            )

    def _get_video_timestamp(self, video_path: str):
        """Извлекает timestamp из видео метаданных"""
        from datetime import datetime

        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-show_entries', 'format_tags=creation_time',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        timestamp_str = result.stdout.strip()

        if timestamp_str:
            # Парсим ISO формат: 2024-01-30T12:34:56.000000Z
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

        return None

    def _sync_by_clap(self, video_path: str) -> SyncResult:
        """
        Синхронизация по звуку хлопушки
        Ищет резкий импульс звука в начале видео
        """
        print("   Метод: clap detection")

        try:
            # Извлекаем первые 10 секунд аудио
            ref_audio = self._extract_audio_samples(self.reference_video, duration=10)
            video_audio = self._extract_audio_samples(video_path, duration=10)

            # Детектируем хлопок (резкий пик амплитуды)
            ref_clap_time = self._detect_clap(ref_audio)
            video_clap_time = self._detect_clap(video_audio)

            if ref_clap_time is not None and video_clap_time is not None:
                offset = video_clap_time - ref_clap_time
                confidence = 0.85

                print(f"   ✅ Хлопок найден. Смещение: {offset:.3f}s")

                return SyncResult(
                    video_path=video_path,
                    offset=offset,
                    confidence=confidence,
                    method='clap'
                )
            else:
                raise ValueError("Хлопок не найден")

        except Exception as e:
            print(f"   ⚠️  Ошибка clap detection: {e}")
            return self._sync_by_waveform(video_path)

    def _detect_clap(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[float]:
        """
        Детектирует первый резкий звуковой импульс (хлопок)

        Returns:
            Время хлопка в секундах или None
        """
        # Вычисляем огибающую (envelope)
        window_size = int(sample_rate * 0.05)  # 50ms окно
        envelope = np.convolve(np.abs(audio), np.ones(window_size) / window_size, mode='same')

        # Находим порог (80% от максимума)
        threshold = 0.8 * np.max(envelope)

        # Ищем первое превышение порога
        clap_indices = np.where(envelope > threshold)[0]

        if len(clap_indices) > 0:
            clap_sample = clap_indices[0]
            clap_time = clap_sample / sample_rate
            return clap_time

        return None

    def export_fcpxml_multicam(
        self,
        sync_results: List[SyncResult],
        output_path: str,
        project_name: str = "Multicam Project"
    ):
        """
        Экспортирует синхронизированный multicam проект в FCPXML

        Args:
            sync_results: Результаты синхронизации
            output_path: Путь для сохранения FCPXML
            project_name: Название проекта
        """
        from fcpxml_generator import FCPXMLGenerator

        print(f"\n📝 Создаю multicam FCPXML...")

        # TODO: Реализовать генерацию multicam FCPXML
        # В стандартном FCPXML нужно:
        # 1. Создать Synchronized Clip
        # 2. Добавить все видео с правильными offsets
        # 3. Установить углы (angles)

        print(f"⚠️  Multicam FCPXML генерация в разработке")
        print(f"   Используйте синхронизированные видео вручную в FCP")

        # Выводим инструкции
        print(f"\n📋 Для ручной синхронизации в Final Cut Pro:")
        for result in sync_results:
            offset_str = f"+{result.offset:.3f}s" if result.offset > 0 else f"{result.offset:.3f}s"
            print(f"   {Path(result.video_path).name}: offset {offset_str}")


# Пример использования
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Использование: python multicam_sync.py видео1.mp4 видео2.mp4 [видео3.mp4 ...]")
        print("\nПример:")
        print("  python multicam_sync.py камера1.mp4 камера2.mp4 камера3.mp4")
        sys.exit(1)

    videos = sys.argv[1:]

    # Проверяем существование файлов
    for video in videos:
        if not os.path.exists(video):
            print(f"❌ Файл не найден: {video}")
            sys.exit(1)

    # Синхронизируем
    syncer = MulticamSync()
    results = syncer.sync_videos(videos, method='waveform')

    # Выводим результаты
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ СИНХРОНИЗАЦИИ")
    print("=" * 60)

    for i, result in enumerate(results, 1):
        status = "📹" if i == 1 else "🎥"
        offset_str = "Референс" if result.offset == 0 else f"{result.offset:+.3f}s"

        print(f"\n{status} {Path(result.video_path).name}")
        print(f"   Смещение: {offset_str}")
        print(f"   Уверенность: {result.confidence:.1%}")
        print(f"   Метод: {result.method}")

    print("\n" + "=" * 60)
    print("✅ Синхронизация завершена!")
    print("\nИмпортируйте видео в Final Cut Pro и создайте Multicam Clip")
    print("с указанными смещениями.")
