#!/bin/bash
# Скрипт установки "VideoRUBY"
# Локальная система обработки видео для Final Cut Pro

echo "=================================="
echo "🎬 VideoRUBY - Установка"
echo "=================================="
echo ""

# Проверка macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ Эта программа работает только на macOS"
    exit 1
fi

echo "📦 Проверяю зависимости..."
echo ""

# Проверка Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew не установлен!"
    echo ""
    echo "Установите Homebrew командой:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

echo "✅ Homebrew установлен"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не установлен!"
    echo "Установите: brew install python3"
    exit 1
fi

echo "✅ Python 3 установлен"

# Установка ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "📥 Устанавливаю ffmpeg..."
    brew install ffmpeg
else
    echo "✅ ffmpeg установлен"
fi

# Установка Python пакетов
echo ""
echo "📥 Устанавливаю Python зависимости..."
echo ""

pip3 install --upgrade pip --break-system-packages 2>/dev/null || pip3 install --upgrade pip
pip3 install openai-whisper --break-system-packages 2>/dev/null || pip3 install openai-whisper
pip3 install setuptools --break-system-packages 2>/dev/null || pip3 install setuptools
pip3 install numpy --break-system-packages 2>/dev/null || pip3 install numpy

echo ""
echo "=================================="
echo "✅ Установка завершена!"
echo "=================================="
echo ""
echo "Для запуска программы используйте:"
echo "  python3 video_editor_app.py"
echo ""
echo "Или создайте приложение двойным кликом:"
echo "  chmod +x create_app.sh"
echo "  ./create_app.sh"
echo ""
