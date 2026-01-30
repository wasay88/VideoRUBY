#!/usr/bin/env python3
"""
Генератор FCPXML для импорта в Final Cut Pro
Создает timeline с видео и субтитрами
"""

import os
from pathlib import Path
from typing import List, Dict
from xml.etree import ElementTree as ET
from xml.dom import minidom
import subprocess


class FCPXMLGenerator:
    """Генератор FCPXML файлов для Final Cut Pro"""

    def __init__(self, framerate: str = "30000/1001"):
        """
        Args:
            framerate: Частота кадров (например, "30000/1001" для 29.97fps)
        """
        self.framerate = framerate

    def seconds_to_frames(self, seconds: float) -> str:
        """Конвертирует секунды в frames для FCPXML"""
        # Для 29.97fps: 30000/1001
        if self.framerate == "30000/1001":
            frames = int(seconds * 29.97)
        else:
            fps = eval(self.framerate)
            frames = int(seconds * fps)
        return f"{frames}s"

    def _seconds_to_time(self, seconds: float) -> str:
        """Конвертирует секунды в рациональный формат времени для FCPXML"""
        millis = int(round(seconds * 1000))
        return f"{millis}/1000s"

    def _get_video_duration(self, video_path: str) -> float:
        """Получает длительность видео через ffprobe"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def create_fcpxml(
        self,
        video_path: str,
        subtitles: List[Dict],
        output_path: str,
        project_name: str = "Edited Project"
    ):
        """
        Создает FCPXML файл с видео и субтитрами

        Args:
            video_path: Путь к отредактированному видео
            subtitles: Список субтитров с временными метками
            output_path: Путь для сохранения FCPXML
            project_name: Название проекта
        """
        print("📝 Генерирую FCPXML для Final Cut Pro...")

        # Получаем информацию о видео
        video_name = Path(video_path).name
        video_path_abs = os.path.abspath(video_path)

        # Создаем корневой элемент
        fcpxml = ET.Element('fcpxml', version="1.11")

        # Добавляем ресурсы
        resources = ET.SubElement(fcpxml, 'resources')

        # Формат
        format_elem = ET.SubElement(
            resources,
            'format',
            id="r1",
            name="FFVideoFormat1080p2997",
            frameDuration=self.framerate,
            width="1920",
            height="1080"
        )

        # Ресурс видео
        asset = ET.SubElement(
            resources,
            'asset',
            id="r2",
            name=video_name,
            start="0s",
            hasVideo="1",
            hasAudio="1",
            format="r1",
            audioSources="1",
            audioChannels="2"
        )
        ET.SubElement(
            asset,
            'media-rep',
            kind="original-media",
            src=f"file://{video_path_abs}"
        )

        # Создаем библиотеку и событие
        library = ET.SubElement(fcpxml, 'library')
        event = ET.SubElement(library, 'event', name="Projects")
        project = ET.SubElement(event, 'project', name=project_name)

        # Создаем последовательность (timeline)
        duration_seconds = subtitles[-1]['end'] if subtitles else self._get_video_duration(video_path)
        sequence = ET.SubElement(
            project,
            'sequence',
            format="r1",
            duration=self._seconds_to_time(duration_seconds if duration_seconds else 60)
        )

        spine = ET.SubElement(sequence, 'spine')

        # Добавляем видео клип
        asset_clip = ET.SubElement(
            spine,
            'asset-clip',
            ref="r2",
            offset="0s",
            name=video_name,
            start="0s",
            duration=self._seconds_to_time(duration_seconds if duration_seconds else 60),
            format="r1",
            tcFormat="NDF"
        )

        # Добавляем субтитры как титры
        for i, sub in enumerate(subtitles):
            start_frames = self.seconds_to_frames(sub['start'])
            duration_frames = self.seconds_to_frames(sub['end'] - sub['start'])

            title = ET.SubElement(
                spine,
                'title',
                ref=f"r{i+100}",
                offset=start_frames,
                name=f"Subtitle {i+1}",
                start=start_frames,
                duration=duration_frames
            )

            # Текст субтитра
            text = ET.SubElement(title, 'text')
            text_style = ET.SubElement(
                text,
                'text-style',
                ref="ts1"
            )
            text_style.text = sub['text']

            # Параметры позиционирования
            param_position = ET.SubElement(
                title,
                'param',
                name="Position",
                key="9999/999166631/999166633/1/100/101",
                value="0 -400"
            )

        # Форматируем XML
        xml_string = self._prettify_xml(fcpxml)

        # Сохраняем
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_string)

        print(f"✅ FCPXML создан: {output_path}")

    def create_simple_fcpxml_with_srt(
        self,
        video_path: str,
        srt_path: str,
        output_path: str,
        project_name: str = "Edited Project"
    ):
        """
        Упрощенный метод: создает FCPXML указывающий на видео и SRT файл

        Final Cut Pro может импортировать SRT отдельно, так что этот метод
        создает проект с видео, а пользователь импортирует SRT вручную

        Args:
            video_path: Путь к видео
            srt_path: Путь к SRT файлу
            output_path: Путь для сохранения FCPXML
            project_name: Название проекта
        """
        print("📝 Создаю упрощенный FCPXML...")

        video_name = Path(video_path).name
        video_path_abs = os.path.abspath(video_path)

        # Минимальный FCPXML
        fcpxml = ET.Element('fcpxml', version="1.11")

        resources = ET.SubElement(fcpxml, 'resources')

        format_elem = ET.SubElement(
            resources,
            'format',
            id="r1",
            name="FFVideoFormat1080p2997",
            frameDuration="1001/30000s",
            width="1920",
            height="1080"
        )

        asset = ET.SubElement(
            resources,
            'asset',
            id="r2",
            name=video_name,
            start="0s",
            hasVideo="1",
            hasAudio="1",
            format="r1"
        )
        ET.SubElement(
            asset,
            'media-rep',
            kind="original-media",
            src=f"file://{video_path_abs}"
        )

        library = ET.SubElement(fcpxml, 'library')
        event = ET.SubElement(library, 'event', name=project_name)
        project = ET.SubElement(event, 'project', name=project_name)

        duration_seconds = self._get_video_duration(video_path)
        sequence = ET.SubElement(
            project,
            'sequence',
            format="r1",
            duration=self._seconds_to_time(duration_seconds if duration_seconds else 60)
        )
        spine = ET.SubElement(sequence, 'spine')

        asset_clip = ET.SubElement(
            spine,
            'asset-clip',
            ref="r2",
            offset="0s",
            name=video_name,
            start="0s",
            duration=self._seconds_to_time(duration_seconds if duration_seconds else 60),
            format="r1"
        )

        xml_string = self._prettify_xml(fcpxml)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_string)

        print(f"✅ FCPXML создан: {output_path}")
        print(f"📌 После импорта FCPXML, импортируйте SRT файл: {srt_path}")
        print(f"   File → Import → Captions → {Path(srt_path).name}")

    def _prettify_xml(self, elem: ET.Element) -> str:
        """Форматирует XML для читаемости"""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


if __name__ == '__main__':
    # Тестовый запуск
    import sys

    if len(sys.argv) < 3:
        print("Использование: python fcpxml_generator.py <видео> <srt_файл>")
        sys.exit(1)

    video_path = sys.argv[1]
    srt_path = sys.argv[2]
    output_path = Path(video_path).stem + ".fcpxml"

    generator = FCPXMLGenerator()
    generator.create_simple_fcpxml_with_srt(
        video_path,
        srt_path,
        output_path
    )

    print(f"\n✅ Готово! FCPXML: {output_path}")
