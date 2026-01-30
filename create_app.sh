#!/bin/bash
# Создание .app для macOS

APP_NAME="VideoRUBY"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "📦 Создаю приложение ${APP_NAME}.app..."

# Создаем структуру .app
APP_DIR="${SCRIPT_DIR}/${APP_NAME}.app"
mkdir -p "${APP_DIR}/Contents/MacOS"
mkdir -p "${APP_DIR}/Contents/Resources"

# Создаем Info.plist
cat > "${APP_DIR}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>run</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.local.videoruby</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
EOF

# Создаем исполняемый скрипт
cat > "${APP_DIR}/Contents/MacOS/run" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd ../../../ && pwd )"
cd "${SCRIPT_DIR}"
python3 video_editor_app.py
EOF

# Даем права на выполнение
chmod +x "${APP_DIR}/Contents/MacOS/run"

echo "✅ Приложение создано: ${APP_NAME}.app"
echo ""
echo "Теперь вы можете запускать программу двойным кликом!"
echo "Если macOS блокирует запуск, откройте:"
echo "Системные настройки → Конфиденциальность и безопасность"
echo "и разрешите запуск приложения."
