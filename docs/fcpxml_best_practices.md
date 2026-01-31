# FCPXML Best Practices (VideoRUBY)

## 1) Обязательные поля
- `<format>` с корректным `frameDuration`, `width`, `height`
- `<asset>` с `duration`, `hasVideo`, `hasAudio`, `format`
- `<media-rep>` с абсолютным `file://` URL
- `<sequence>` с `format`, `duration`, `tcStart`, `tcFormat`, `audioLayout`, `audioRate`

## 2) Тайминги
- Все `duration/offset/start` должны быть кратны `frameDuration`.
- Используем frame‑aligned значения: `frames * den / num`.

## 3) Импорт в FCP
- Видео должно существовать по пути в `src`.
- Не перемещать видео после генерации XML.
- Импортировать через **File → Import → XML…**

## 4) Рекомендации
- Если FCP ругается: проверять fps/разрешение/путь.
- Для кириллицы лучше использовать путь без русских символов (как fallback).
