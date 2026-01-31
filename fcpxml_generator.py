#!/usr/bin/env python3
"""
Генератор FCPXML для импорта в Final Cut Pro
Создает timeline с видео и субтитрами
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
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

    def _parse_rate(self, rate: str) -> tuple[int, int]:
        """Парсит строку FPS вида '30000/1001'."""
        if "/" in rate:
            num, den = rate.split("/", 1)
            return int(num), int(den)
        return int(rate), 1

    def _format_name(self, width: int, height: int, framerate: str) -> str:
        """Возвращает имя формата, совместимое с FCP."""
        num, den = self._parse_rate(framerate)
        fps = num / den
        # Common FCP naming: 2398, 2997, 5994
        if abs(fps - 23.976) < 0.01:
            fps_tag = "2398"
        elif abs(fps - 29.97) < 0.01:
            fps_tag = "2997"
        elif abs(fps - 59.94) < 0.01:
            fps_tag = "5994"
        else:
            fps_tag = str(int(round(fps * 100)))
        return f"FFVideoFormat{height}p{fps_tag}"

    def seconds_to_frames(self, seconds: float) -> str:
        """Конвертирует секунды в frames для FCPXML"""
        num, den = self._parse_rate(self.framerate)
        fps = num / den
        frames = int(seconds * fps)
        return f"{frames}s"

    def _seconds_to_time(self, seconds: float) -> str:
        """Конвертирует секунды в рациональный формат времени для FCPXML"""
        millis = int(round(seconds * 1000))
        return f"{millis}/1000s"

    def _seconds_to_frame_time(self, seconds: float, framerate: Optional[str] = None) -> str:
        """Конвертирует секунды в тайминг, кратный frameDuration для FCP (720000 timebase)."""
        rate = framerate or self.framerate
        num, den = self._parse_rate(rate)
        fps = num / den
        # FCP использует timebase 720000 для 23.976fps
        # frameDuration = 15015/360000s, поэтому используем 720000 как базу
        timebase = 720000
        frame_duration_ticks = int(timebase / fps)
        total_frames = int(round(seconds * fps))
        duration_ticks = total_frames * frame_duration_ticks
        return f"{duration_ticks}/{timebase}s"

    def _get_fcp_frame_duration(self, framerate: str) -> str:
        """Возвращает frameDuration в формате FCP (15015/360000s для 23.976fps)."""
        num, den = self._parse_rate(framerate)
        fps = num / den
        # FCP использует 360000 как базу для frameDuration
        timebase = 360000
        frame_ticks = int(round(timebase / fps))
        return f"{frame_ticks}/{timebase}s"
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

    def _get_video_info(self, video_path: str) -> dict:
        """Получает ширину/высоту/фпс/длительность через ffprobe."""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        info = {
            "width": 1920,
            "height": 1080,
            "framerate": self.framerate,
            "duration": 0.0
        }
        try:
            import json
            data = json.loads(result.stdout)
            stream = data.get("streams", [{}])[0]
            info["width"] = int(stream.get("width") or info["width"])
            info["height"] = int(stream.get("height") or info["height"])
            rate = stream.get("r_frame_rate") or info["framerate"]
            info["framerate"] = rate
            fmt = data.get("format", {})
            if fmt.get("duration"):
                info["duration"] = float(fmt["duration"])
        except Exception:
            pass
        return info

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
        video_path_abs = Path(video_path).resolve().as_uri()
        video_info = self._get_video_info(video_path)
        duration_seconds = subtitles[-1]['end'] if subtitles else (video_info["duration"] or self._get_video_duration(video_path))
        framerate = video_info["framerate"]

        # Создаем корневой элемент
        fcpxml = ET.Element('fcpxml', version="1.11")

        # Добавляем ресурсы
        resources = ET.SubElement(fcpxml, 'resources')

        # Формат
        format_name = self._format_name(video_info["width"], video_info["height"], framerate)
        frame_duration_str = self._get_fcp_frame_duration(framerate)
        format_elem = ET.SubElement(
            resources,
            'format',
            id="r1",
            name=format_name,
            frameDuration=frame_duration_str,
            width=str(video_info["width"]),
            height=str(video_info["height"]),
            colorSpace="1-1-1 (Rec. 709)"
        )

        # Ресурс видео
        asset = ET.SubElement(
            resources,
            'asset',
            id="r2",
            name=video_name,
            duration=self._seconds_to_frame_time(duration_seconds if duration_seconds else 60, framerate),
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
            src=video_path_abs
        )

        # Создаем библиотеку и событие
        library = ET.SubElement(fcpxml, 'library')
        event = ET.SubElement(library, 'event', name="Projects")
        project = ET.SubElement(event, 'project', name=project_name)

        # Создаем последовательность (timeline)
        sequence = ET.SubElement(
            project,
            'sequence',
            format="r1",
            duration=self._seconds_to_frame_time(duration_seconds if duration_seconds else 60, framerate),
            tcStart="0s",
            tcFormat="NDF",
            audioLayout="stereo",
            audioRate="48k"
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
            duration=self._seconds_to_frame_time(duration_seconds if duration_seconds else 60, framerate),
            format="r1",
            tcFormat="NDF"
        )

        # Добавляем субтитры как титры
        for i, sub in enumerate(subtitles):
            start_frames = self._seconds_to_frame_time(sub['start'], framerate)
            duration_frames = self._seconds_to_frame_time(sub['end'] - sub['start'], framerate)

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
        srt_path: Optional[str],
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
        video_path_abs = Path(video_path).resolve().as_uri()
        video_info = self._get_video_info(video_path)
        duration_seconds = video_info["duration"] or self._get_video_duration(video_path)
        framerate = video_info["framerate"]

        # Минимальный FCPXML
        fcpxml = ET.Element('fcpxml', version="1.11")

        resources = ET.SubElement(fcpxml, 'resources')

        format_name = self._format_name(video_info["width"], video_info["height"], framerate)
        frame_duration_str = self._get_fcp_frame_duration(framerate)
        format_elem = ET.SubElement(
            resources,
            'format',
            id="r1",
            name=format_name,
            frameDuration=frame_duration_str,
            width=str(video_info["width"]),
            height=str(video_info["height"]),
            colorSpace="1-1-1 (Rec. 709)"
        )

        # Generate unique ID for asset based on file path
        import hashlib
        uid_hash = hashlib.md5(video_path_abs.encode()).hexdigest().upper()
        asset_uid = f"{uid_hash[:8]}{uid_hash[8:16]}{uid_hash[16:24]}{uid_hash[24:32]}"

        duration_str = self._seconds_to_frame_time(duration_seconds if duration_seconds else 60, framerate)

        asset = ET.SubElement(
            resources,
            'asset',
            id="r2",
            name=video_name,
            uid=asset_uid,
            start="0s",
            duration=duration_str,
            hasVideo="1",
            format="r1",
            hasAudio="1",
            videoSources="1",
            audioSources="1",
            audioChannels="2",
            audioRate="48000"
        )
        ET.SubElement(
            asset,
            'media-rep',
            kind="original-media",
            src=video_path_abs
        )

        library = ET.SubElement(fcpxml, 'library')
        event = ET.SubElement(library, 'event', name=project_name)
        project = ET.SubElement(event, 'project', name=project_name)

        sequence = ET.SubElement(
            project,
            'sequence',
            format="r1",
            duration=duration_str,
            tcStart="0s",
            tcFormat="NDF",
            audioLayout="stereo",
            audioRate="48k"
        )
        spine = ET.SubElement(sequence, 'spine')

        asset_clip = ET.SubElement(
            spine,
            'asset-clip',
            ref="r2",
            offset="0s",
            name=Path(video_path).stem,
            start="0s",
            duration=duration_str,
            tcFormat="NDF",
            audioRole="dialogue"
        )
        # Add audio channel source
        ET.SubElement(
            asset_clip,
            'audio-channel-source',
            srcCh="1, 2",
            role="dialogue.dialogue-1"
        )

        xml_string = self._prettify_xml(fcpxml)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_string)

        print(f"✅ FCPXML создан: {output_path}")
        if srt_path:
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
