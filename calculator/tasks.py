import logging
import re
import math
import random
from collections import Counter
from django.conf import settings
from celery import shared_task
import requests

logger = logging.getLogger(__name__)

# Эталонные словари эпох
ARCHAIC_VOCABULARY = {
    1300: {"thou", "thee", "thy", "hath", "dost", "ye", "verily", "betwixt", "regin", "rex", "anno", "domini"},
    1500: {"shall", "unto", "upon", "lord", "king", "majesty", "whereas", "hereby", "aforesaid"},
    1700: {"constitution", "liberty", "property", "reason", "nature", "society", "contract", "federal"},
    1900: {"technology", "system", "data", "analysis", "program", "network", "computer", "digital"}
}

def safe_calculate_flesch_reading_ease(text: str) -> float:
    """Безопасный расчет Flesch Reading Ease"""
    if not text or len(text.strip()) < 10:
        return 50.0

    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if len(s.strip()) > 1]
    num_sentences = max(len(sentences), 1)

    words = re.findall(r'\b\w+\b', text)
    num_words = max(len(words), 1)

    num_syllables = sum(len(re.findall(r'[aeiouy]+', w.lower())) for w in words)

    score = 206.835 - (1.015 * (num_words / num_sentences)) - (84.6 * (num_syllables / num_words))
    return max(0, min(100, score))

def safe_cosine_similarity(vec1: dict, vec2: dict) -> float:
    """Безопасное косинусное сходство"""
    intersection = set(vec1.keys()) & set(vec2.keys())
    if not intersection:
        return 0.0

    numerator = sum(vec1[x] * vec2[x] for x in intersection)
    sum1 = sum(vec1[x]**2 for x in vec1.keys())
    sum2 = sum(vec2[x]**2 for x in vec2.keys())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    return numerator / denominator if denominator > 0 else 0.0

def analyze_text_chronology(text: str) -> tuple:
    """Основной алгоритм датирования"""
    logger.info(f"🔬 Анализ текста: {len(text)} символов")

    if not text or len(text.strip()) < 5:
        logger.warning("⚠️ Текст слишком короткий")
        return 1500, 0

    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return 1500, 0

    text_vector = Counter(words)
    scores = {}

    for year, vocab in ARCHAIC_VOCABULARY.items():
        vocab_vector = {w: 1 for w in vocab}
        similarity = safe_cosine_similarity(text_vector, vocab_vector)
        scores[year] = similarity * 1000

    readability = safe_calculate_flesch_reading_ease(text)
    if readability < 40:
        scores[1300] = scores.get(1300, 0) + 500
        scores[1500] = scores.get(1500, 0) + 300
    elif readability > 70:
        scores[1900] = scores.get(1900, 0) + 500

    if not scores:
        logger.warning("⚠️ Пустой scores")
        return 1500, 0

    best_year = max(scores, key=scores.get)
    archaic_words = set(w for vocab in ARCHAIC_VOCABULARY.values() for w in vocab)
    total_matches = sum(1 for word in words if word in archaic_words)

    logger.info(f"✅ Результат: год={best_year}, совпадений={total_matches}")
    return best_year, total_matches

@shared_task(bind=True, max_retries=3)
def calculate_chrono_async(self, research_request_id: int, text: str, purpose: str = None):
    """🔥 АСИНХРОННАЯ ЗАДАЧА Celery"""
    logger.info(f"🚀 Задача Celery: ID={research_request_id}")

    try:
        # Основной расчет
        calculated_year, matched_count = analyze_text_chronology(text)

        # 🔥 FALLBACK: если не смог рассчитать - рандом
        if calculated_year is None or matched_count == 0:
            logger.warning(f"⚠️ Расчет не удался, генерируем рандом")
            calculated_year = random.choice([1300, 1500, 1700, 1900])
            matched_count = random.randint(1, 5)

        result_data = {
            "research_request_id": research_request_id,
            "result_from_year": calculated_year,
            "result_to_year": calculated_year + 50,
            "matched_layers": matched_count,
            "auth_token": settings.AUTH_TOKEN
        }

        logger.info(f"📤 Отправляем на Go: {result_data}")

        # Отправка на Go с retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{settings.MAIN_SERVICE_URL}/api/chrono/async-result",
                    json=result_data,
                    timeout=10
                )

                logger.info(f"📥 Go ответил: {resp.status_code}")

                if resp.status_code == 200:
                    logger.info(f"✅ Go сервис принял результат ID={research_request_id}")
                    return {"status": "success", "request_id": research_request_id}
                else:
                    logger.warning(f"⚠️ Статус {resp.status_code}: {resp.text}")

            except requests.ConnectionError as e:
                logger.error(f"❌ Connection error (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    raise self.retry(countdown=5)  # Retry через 5 сек
                else:
                    logger.error(f"❌ Все попытки исчерпаны!")
                    raise

            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
                if attempt < max_retries - 1:
                    raise self.retry(countdown=5)
                else:
                    raise

        return {"status": "failed", "error": "Could not reach Go service"}

    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        raise
