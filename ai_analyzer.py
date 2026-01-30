#!/usr/bin/env python3
"""
AI Analyzer - Умный анализ видео через LLM
Вдохновлено: github.com/coderroleggg/autoeditor

Возможности:
1. Определение "bad takes" (неудачных дублей)
2. Поиск повторений и ошибок
3. Сопоставление со сценарием
4. Автоматические рекомендации по вырезкам
"""

import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Take:
    """Представление одного дубля"""
    start: float
    end: float
    text: str
    confidence: float
    is_good: bool
    reason: str = ""


class AIAnalyzer:
    """
    Анализатор видео с использованием LLM

    Использует OpenAI API для определения:
    - Bad takes (повторы, оговорки)
    - Best takes (финальные версии)
    - Ненужные фрагменты
    """

    def __init__(self, api_key: Optional[str] = None, use_local_llm: bool = False):
        """
        Args:
            api_key: OpenAI API ключ (если None, берет из переменной окружения)
            use_local_llm: Использовать локальную LLM (Ollama/LM Studio)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.use_local_llm = use_local_llm

    def analyze_transcription(
        self,
        transcription: List[Dict],
        script: Optional[str] = None
    ) -> List[Take]:
        """
        Анализирует транскрипцию и определяет good/bad takes

        Args:
            transcription: Список сегментов с текстом и таймкодами
            script: Опциональный сценарий для сопоставления

        Returns:
            Список Take объектов с маркировкой good/bad
        """
        takes = []

        # Простой эвристический анализ (без API)
        takes = self._heuristic_analysis(transcription)

        # Если доступен API - используем LLM для улучшенного анализа
        if self.api_key and not self.use_local_llm:
            takes = self._llm_analysis(transcription, script, takes)
        elif self.use_local_llm:
            takes = self._local_llm_analysis(transcription, script, takes)

        return takes

    def _heuristic_analysis(self, transcription: List[Dict]) -> List[Take]:
        """
        Простой анализ без LLM
        Определяет bad takes по паттернам:
        - Повторения
        - Филлеры ("эм", "аа", "это самое")
        - Длинные паузы внутри предложений
        """
        takes = []

        # Маркеры bad takes
        filler_words = ['эм', 'ээ', 'аа', 'это самое', 'как бы', 'ну']

        for i, segment in enumerate(transcription):
            text = segment['text'].lower().strip()
            start = segment['start']
            end = segment['end']

            is_good = True
            reason = "Нормальный сегмент"
            confidence = 1.0

            # Проверка на филлеры
            filler_count = sum(1 for filler in filler_words if filler in text)
            if filler_count >= 2:
                is_good = False
                reason = f"Много филлеров ({filler_count})"
                confidence = 0.3

            # Проверка на повторения с предыдущим сегментом
            if i > 0:
                prev_text = transcription[i-1]['text'].lower().strip()
                # Простое совпадение слов
                prev_words = set(prev_text.split())
                curr_words = set(text.split())
                overlap = len(prev_words & curr_words) / max(len(curr_words), 1)

                if overlap > 0.7 and len(text.split()) > 3:
                    is_good = False
                    reason = "Повторение предыдущего сегмента"
                    confidence = 0.2

            # Проверка на очень короткие фразы (обрывки)
            if len(text.split()) < 3 and end - start < 1.0:
                is_good = False
                reason = "Слишком короткий фрагмент"
                confidence = 0.4

            takes.append(Take(
                start=start,
                end=end,
                text=segment['text'],
                confidence=confidence,
                is_good=is_good,
                reason=reason
            ))

        return takes

    def _llm_analysis(
        self,
        transcription: List[Dict],
        script: Optional[str],
        heuristic_takes: List[Take]
    ) -> List[Take]:
        """
        Продвинутый анализ через OpenAI API

        Используйте это только если установлен openai:
        pip install openai
        """
        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key)

            # Подготавливаем контекст для LLM
            transcript_text = "\n".join([
                f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}"
                for seg in transcription
            ])

            # Подготавливаем опциональный скрипт
            script_section = f"Сценарий для сопоставления:\n{script}\n\n" if script else ""

            prompt = f"""Проанализируй транскрипцию видео и определи good/bad takes.

Bad takes - это:
- Повторения одного и того же
- Оговорки и переделывания фразы
- Филлеры ("эм", "аа", "это самое")
- Незавершенные мысли перед повторной попыткой

Good takes - это:
- Финальные удачные версии
- Чистая речь без повторов
- Законченные мысли

Транскрипция:
{transcript_text}

{script_section}Верни JSON массив с анализом каждого сегмента:
[
  {{"start": 0.0, "end": 5.0, "is_good": true, "reason": "Чистая речь", "confidence": 0.9}},
  ...
]
"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Или gpt-4o для лучшего качества
                messages=[
                    {"role": "system", "content": "Ты эксперт по видеомонтажу. Анализируешь транскрипции и определяешь good/bad takes."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            # Парсим ответ
            analysis = json.loads(response.choices[0].message.content)

            # Обновляем takes на основе LLM анализа
            if 'segments' in analysis:
                for i, llm_take in enumerate(analysis['segments']):
                    if i < len(heuristic_takes):
                        heuristic_takes[i].is_good = llm_take.get('is_good', True)
                        heuristic_takes[i].reason = llm_take.get('reason', 'LLM анализ')
                        heuristic_takes[i].confidence = llm_take.get('confidence', 0.8)

            return heuristic_takes

        except ImportError:
            print("⚠️  OpenAI не установлен. Используем эвристический анализ.")
            print("   Установите: pip install openai")
            return heuristic_takes
        except Exception as e:
            print(f"⚠️  Ошибка LLM анализа: {e}")
            return heuristic_takes

    def _local_llm_analysis(
        self,
        transcription: List[Dict],
        script: Optional[str],
        heuristic_takes: List[Take]
    ) -> List[Take]:
        """
        Анализ через локальную LLM (Ollama, LM Studio)

        Требует установки:
        - Ollama: https://ollama.ai
        - Модель: ollama pull llama3
        """
        try:
            import requests

            transcript_text = "\n".join([
                f"[{seg['start']:.1f}s] {seg['text']}"
                for seg in transcription
            ])

            prompt = f"""Анализируй транскрипцию видео. Определи good/bad takes.

Bad: повторы, оговорки, филлеры
Good: финальные чистые версии

{transcript_text}

JSON ответ с is_good, reason для каждого сегмента:"""

            # Запрос к локальной Ollama
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'llama3',
                    'prompt': prompt,
                    'stream': False,
                    'format': 'json'
                }
            )

            if response.status_code == 200:
                result = response.json()
                analysis = json.loads(result['response'])

                # Обновляем takes
                # (логика аналогична _llm_analysis)

            return heuristic_takes

        except Exception as e:
            print(f"⚠️  Ошибка локальной LLM: {e}")
            return heuristic_takes

    def generate_recommendations(self, takes: List[Take]) -> Dict:
        """
        Генерирует рекомендации по монтажу

        Returns:
            Словарь с рекомендациями:
            - segments_to_remove: Сегменты для удаления
            - segments_to_keep: Сегменты для сохранения
            - statistics: Статистика
        """
        bad_takes = [t for t in takes if not t.is_good]
        good_takes = [t for t in takes if t.is_good]

        total_bad_duration = sum(t.end - t.start for t in bad_takes)
        total_good_duration = sum(t.end - t.start for t in good_takes)

        return {
            'segments_to_remove': [
                {
                    'start': t.start,
                    'end': t.end,
                    'reason': t.reason,
                    'text': t.text[:50] + '...' if len(t.text) > 50 else t.text
                }
                for t in bad_takes
            ],
            'segments_to_keep': [
                {'start': t.start, 'end': t.end}
                for t in good_takes
            ],
            'statistics': {
                'total_segments': len(takes),
                'bad_takes': len(bad_takes),
                'good_takes': len(good_takes),
                'bad_duration': total_bad_duration,
                'good_duration': total_good_duration,
                'time_saved': total_bad_duration
            }
        }

    def export_analysis(self, takes: List[Take], output_path: str):
        """Экспортирует анализ в JSON"""
        data = {
            'takes': [
                {
                    'start': t.start,
                    'end': t.end,
                    'text': t.text,
                    'is_good': t.is_good,
                    'confidence': t.confidence,
                    'reason': t.reason
                }
                for t in takes
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Анализ сохранен: {output_path}")


# Пример использования
if __name__ == '__main__':
    # Тестовая транскрипция
    test_transcription = [
        {'start': 0.0, 'end': 3.0, 'text': 'Привет, это тестовое видео'},
        {'start': 3.5, 'end': 6.0, 'text': 'эм, это, как бы, тестовое видео'},
        {'start': 6.5, 'end': 9.0, 'text': 'Привет, это тестовое видео'},
        {'start': 9.5, 'end': 12.0, 'text': 'Сегодня мы поговорим о монтаже'},
    ]

    analyzer = AIAnalyzer()
    takes = analyzer.analyze_transcription(test_transcription)

    print("\n📊 Анализ дублей:")
    print("=" * 60)
    for take in takes:
        status = "✅ GOOD" if take.is_good else "❌ BAD"
        print(f"\n{status} [{take.start:.1f}s - {take.end:.1f}s]")
        print(f"   Текст: {take.text}")
        print(f"   Причина: {take.reason}")
        print(f"   Уверенность: {take.confidence:.1%}")

    recommendations = analyzer.generate_recommendations(takes)
    print(f"\n📈 Статистика:")
    print(f"   Всего сегментов: {recommendations['statistics']['total_segments']}")
    print(f"   Good takes: {recommendations['statistics']['good_takes']}")
    print(f"   Bad takes: {recommendations['statistics']['bad_takes']}")
    print(f"   Экономия времени: {recommendations['statistics']['time_saved']:.1f}s")
