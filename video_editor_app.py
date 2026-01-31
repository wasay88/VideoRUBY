#!/usr/bin/env python3
"""
VideoRUBY - Локальная система обработки видео
GUI приложение для удаления пауз и генерации субтитров
"""

import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from video_processor import VideoProcessor
from transcription import Transcriber, SubtitleGenerator
from fcpxml_generator import FCPXMLGenerator


class VideoEditorApp:
    """GUI приложение для обработки видео"""

    def __init__(self, root):
        self.root = root
        self.root.title("VideoRUBY - Обработка видео для Final Cut Pro")
        self.root.geometry("800x700")

        # Переменные
        self.video_path = tk.StringVar()
        self.silence_threshold = tk.DoubleVar(value=-35)
        self.min_silence_duration = tk.DoubleVar(value=0.5)
        self.whisper_model = tk.StringVar(value="base")
        self.crf = tk.IntVar(value=16)
        self.video_bitrate = tk.StringVar(value="")
        self.output_edited_video = tk.BooleanVar(value=True)
        self.output_subtitles = tk.BooleanVar(value=True)
        self.output_fcpxml = tk.BooleanVar(value=True)
        self.processing = False

        self.setup_ui()
        self.root.after(150, self._bring_to_front)

    def _bring_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    def setup_ui(self):
        """Создает интерфейс"""

        # Заголовок
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)

        title_label = ttk.Label(
            title_frame,
            text="🎬 VideoRUBY",
            font=("Arial", 18, "bold")
        )
        title_label.pack()

        subtitle_label = ttk.Label(
            title_frame,
            text="Локальная обработка видео: удаление пауз + русские субтитры",
            font=("Arial", 10)
        )
        subtitle_label.pack()

        # Основной контейнер
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === 1. Выбор файла ===
        file_frame = ttk.LabelFrame(main_frame, text="1. Выберите видео", padding="10")
        file_frame.pack(fill=tk.X, pady=5)

        file_entry = ttk.Entry(file_frame, textvariable=self.video_path, width=60)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        browse_btn = ttk.Button(
            file_frame,
            text="Обзор...",
            command=self.browse_file
        )
        browse_btn.pack(side=tk.LEFT)

        # === 2. Настройки ===
        settings_frame = ttk.LabelFrame(main_frame, text="2. Настройки обработки", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)

        # Порог тишины
        silence_frame = ttk.Frame(settings_frame)
        silence_frame.pack(fill=tk.X, pady=3)

        ttk.Label(silence_frame, text="Порог тишины (dB):").pack(side=tk.LEFT)
        silence_scale = ttk.Scale(
            silence_frame,
            from_=-50,
            to=-20,
            variable=self.silence_threshold,
            orient=tk.HORIZONTAL,
            length=200
        )
        silence_scale.pack(side=tk.LEFT, padx=5)
        silence_value = ttk.Label(silence_frame, textvariable=self.silence_threshold)
        silence_value.pack(side=tk.LEFT)
        ttk.Label(silence_frame, text="(ниже = больше пауз)").pack(side=tk.LEFT, padx=5)

        # Минимальная длительность паузы
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.pack(fill=tk.X, pady=3)

        ttk.Label(duration_frame, text="Мин. длительность паузы (сек):").pack(side=tk.LEFT)
        duration_scale = ttk.Scale(
            duration_frame,
            from_=0.3,
            to=2.0,
            variable=self.min_silence_duration,
            orient=tk.HORIZONTAL,
            length=200
        )
        duration_scale.pack(side=tk.LEFT, padx=5)
        duration_value = ttk.Label(duration_frame, textvariable=self.min_silence_duration)
        duration_value.pack(side=tk.LEFT)

        # Модель Whisper
        model_frame = ttk.Frame(settings_frame)
        model_frame.pack(fill=tk.X, pady=3)

        ttk.Label(model_frame, text="Модель Whisper:").pack(side=tk.LEFT)
        model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.whisper_model,
            values=["tiny", "base", "small", "medium", "large"],
            state="readonly",
            width=15
        )
        model_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(model_frame, text="(base = оптимально)").pack(side=tk.LEFT)

        # Качество кодирования
        quality_frame = ttk.Frame(settings_frame)
        quality_frame.pack(fill=tk.X, pady=3)

        ttk.Label(quality_frame, text="CRF (качество, меньше = лучше):").pack(side=tk.LEFT)
        crf_spin = ttk.Spinbox(
            quality_frame,
            from_=0,
            to=30,
            textvariable=self.crf,
            width=5
        )
        crf_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(quality_frame, text="(рекомендуется 16)").pack(side=tk.LEFT, padx=5)

        bitrate_frame = ttk.Frame(settings_frame)
        bitrate_frame.pack(fill=tk.X, pady=3)
        ttk.Label(bitrate_frame, text="Битрейт видео (например 20M):").pack(side=tk.LEFT)
        bitrate_entry = ttk.Entry(bitrate_frame, textvariable=self.video_bitrate, width=10)
        bitrate_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(bitrate_frame, text="(если задан, CRF игнорируется)").pack(side=tk.LEFT, padx=5)

        # Выходные файлы
        outputs_frame = ttk.LabelFrame(main_frame, text="3. Выходные файлы", padding="10")
        outputs_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(
            outputs_frame,
            text="Смонтированное видео (без пауз)",
            variable=self.output_edited_video
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            outputs_frame,
            text="Субтитры (SRT)",
            variable=self.output_subtitles
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            outputs_frame,
            text="Проект Final Cut Pro (FCPXML)",
            variable=self.output_fcpxml
        ).pack(anchor=tk.W)

        # === 3. Кнопка запуска ===
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)

        self.process_btn = ttk.Button(
            action_frame,
            text="▶️  ОБРАБОТАТЬ ВИДЕО",
            command=self.process_video,
            style="Accent.TButton"
        )
        self.process_btn.pack(pady=5)

        # Прогресс бар
        self.progress = ttk.Progressbar(
            action_frame,
            mode='indeterminate',
            length=300
        )
        self.progress.pack(pady=5)

        # === 4. Лог ===
        log_frame = ttk.LabelFrame(main_frame, text="Лог обработки", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            wrap=tk.WORD,
            font=("Courier", 10)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # === 5. Информация ===
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=5)

        info_text = (
            "ℹ️  Что делает программа:\n"
            "1. Анализирует видео и находит паузы\n"
            "2. Создает отредактированную версию без пауз\n"
            "3. Транскрибирует речь (русский язык)\n"
            "4. Создает субтитры (SRT + FCPXML)\n"
            "5. Готовый проект можно импортировать в Final Cut Pro"
        )

        info_label = ttk.Label(
            info_frame,
            text=info_text,
            font=("Arial", 9),
            foreground="gray"
        )
        info_label.pack()

    def browse_file(self):
        """Открывает диалог выбора файла"""
        filename = filedialog.askopenfilename(
            title="Выберите видео",
            filetypes=[
                ("Видео файлы", "*.mp4 *.mov *.avi *.mkv"),
                ("Все файлы", "*.*")
            ]
        )
        if filename:
            self.video_path.set(filename)

    def log(self, message):
        """Добавляет сообщение в лог"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()

    def process_video(self):
        """Основная функция обработки видео"""
        if self.processing:
            messagebox.showwarning("Предупреждение", "Обработка уже идет!")
            return

        video_path = self.video_path.get()

        if not video_path or not os.path.exists(video_path):
            messagebox.showerror("Ошибка", "Выберите видео файл!")
            return

        if not (self.output_edited_video.get() or self.output_subtitles.get() or self.output_fcpxml.get()):
            messagebox.showwarning("Предупреждение", "Выберите хотя бы один выходной файл!")
            return

        # Запускаем в отдельном потоке
        self.processing = True
        self.process_btn.config(state=tk.DISABLED)
        self.progress.start()
        self.log_text.delete(1.0, tk.END)

        thread = threading.Thread(target=self._process_video_thread, args=(video_path,))
        thread.daemon = True
        thread.start()

    def _process_video_thread(self, video_path):
        """Поток обработки видео"""
        try:
            self.log("=" * 60)
            self.log("🚀 НАЧИНАЕМ ОБРАБОТКУ")
            self.log("=" * 60)
            self.log(f"📹 Файл: {Path(video_path).name}\n")

            edited_video = None
            result = None

            if self.output_edited_video.get():
                # Шаг 1: Удаление пауз
                self.log("🔧 ШАГ 1: АНАЛИЗ И УДАЛЕНИЕ ПАУЗ")
                self.log("-" * 60)

                processor = VideoProcessor(
                    silence_threshold_db=self.silence_threshold.get(),
                    min_silence_duration=self.min_silence_duration.get(),
                    crf=self.crf.get(),
                    video_bitrate=self.video_bitrate.get().strip() or None
                )

                result = processor.process_video(video_path)
                edited_video = result['edited_video']

                self.log(f"✅ Видео обработано!")
                self.log(f"   Оригинал: {result['statistics']['original_duration']:.1f}с")
                self.log(f"   После обработки: {result['statistics']['speech_duration']:.1f}с")
                self.log(f"   Удалено пауз: {result['statistics']['silences_removed']}")
                self.log(f"   Сэкономлено: {result['statistics']['silence_duration']:.1f}с\n")

            # Шаг 2: Транскрипция
            subtitle_path = None
            if self.output_subtitles.get():
                self.log("🔧 ШАГ 2: ТРАНСКРИПЦИЯ И СУБТИТРЫ")
                self.log("-" * 60)

                transcriber = Transcriber(
                    model_size=self.whisper_model.get(),
                    language="ru"
                )

                # Транскрибируем отредактированное или оригинальное видео
                video_for_subs = edited_video if edited_video else video_path
                subtitle_path = transcriber.transcribe(video_for_subs, output_format="srt")

                self.log(f"✅ Субтитры созданы: {Path(subtitle_path).name}\n")

            # Шаг 3: Генерация FCPXML
            if self.output_fcpxml.get():
                self.log("🔧 ШАГ 3: СОЗДАНИЕ FCPXML ДЛЯ FINAL CUT PRO")
                self.log("-" * 60)

                video_for_fcpxml = edited_video if edited_video else video_path
                fcpxml_path = Path(video_for_fcpxml).with_suffix('.fcpxml')
                generator = FCPXMLGenerator()

                generator.create_simple_fcpxml_with_srt(
                    str(video_for_fcpxml),
                    subtitle_path,
                    str(fcpxml_path),
                    project_name=f"Edited - {Path(video_path).stem}"
                )

                self.log(f"✅ FCPXML создан: {Path(fcpxml_path).name}\n")

            # Итоги
            self.log("=" * 60)
            self.log("🎉 ОБРАБОТКА ЗАВЕРШЕНА!")
            self.log("=" * 60)
            self.log("\n📦 РЕЗУЛЬТАТЫ:")
            idx = 1
            if edited_video:
                self.log(f"  {idx}. Отредактированное видео: {Path(edited_video).name}")
                idx += 1
            if subtitle_path:
                self.log(f"  {idx}. Субтитры (SRT): {Path(subtitle_path).name}")
                idx += 1
            if self.output_fcpxml.get():
                self.log(f"  {idx}. Проект FCPXML: {Path(fcpxml_path).name}")
            self.log("\n📌 КАК ИМПОРТИРОВАТЬ В FINAL CUT PRO:")
            self.log("  1. File → Import → Files...")
            if self.output_fcpxml.get():
                self.log(f"  2. Выберите: {Path(fcpxml_path).name}")
                self.log("  3. Откроется готовый проект с видео")
                if subtitle_path:
                    self.log("  4. File → Import → Captions...")
                    self.log(f"  5. Выберите: {Path(subtitle_path).name}")
            self.log("\n✨ Готово! Можно работать в Final Cut Pro.")

            # Показываем диалог
            self.root.after(0, lambda: messagebox.showinfo(
                "Успех!",
                f"Обработка завершена!\n\n"
                f"Файлы сохранены в:\n{os.path.dirname(edited_video or video_path)}"
            ))

        except Exception as e:
            self.log(f"\n❌ ОШИБКА: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror(
                "Ошибка",
                f"Произошла ошибка:\n{str(e)}"
            ))

        finally:
            self.processing = False
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, self.progress.stop)


def main():
    """Запуск приложения"""

    # Проверяем зависимости
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        if result.returncode != 0:
            raise Exception()
    except:
        messagebox.showerror(
            "Ошибка",
            "ffmpeg не установлен!\n\n"
            "Установите через Homebrew:\n"
            "brew install ffmpeg"
        )
        sys.exit(1)

    try:
        result = subprocess.run(['whisper', '--help'], capture_output=True)
        if result.returncode != 0:
            raise Exception()
    except:
        messagebox.showerror(
            "Ошибка",
            "OpenAI Whisper не установлен!\n\n"
            "Установите командой:\n"
            "pip install openai-whisper"
        )
        sys.exit(1)

    # Запускаем GUI
    root = tk.Tk()
    app = VideoEditorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
