import asyncio
import re
import math
import logging
import os
from collections import Counter
from typing import Optional, Dict

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('chrono_calc.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chrono Scientific Calculator")

MAIN_SERVICE_URL = os.getenv("MAIN_SERVICE_URL", "http://127.0.0.1:8080")
AUTH_TOKEN_EXPECTED = os.getenv("AUTH_TOKEN", "111517")

# Эталонные словари эпох
ARCHAIC_VOCABULARY = {
    1300: {"thou", "thee", "thy", "hath", "dost", "ye", "verily", "betwixt", "regin", "rex", "anno", "domini"},
    1500: {"shall", "unto", "upon", "lord", "king", "majesty", "whereas", "hereby", "aforesaid"},
    1700: {"constitution", "liberty", "property", "reason", "nature", "society", "contract", "federal"},
    1900: {"technology", "system", "data", "analysis", "program", "network", "computer", "digital"}
}

class ChronoRequest(BaseModel):
    research_request_id: int
    auth_token: str
    text_for_analysis: Optional[str] = None
    purpose: Optional[str] = None

class ChronoResult(BaseModel):
    status: str
    year: Optional[int] = None
    matched_layers: Optional[int] = None
    error: Optional[str] = None

def safe_calculate_flesch_reading_ease(text: str) -> float:
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

def safe_cosine_similarity(vec1: Dict[str, int], vec2: Dict[str, int]) -> float:
    intersection = set(vec1.keys()) & set(vec2.keys())
    if not intersection:
        return 0.0

    numerator = sum(vec1[x] * vec2[x] for x in intersection)
    sum1 = sum(vec1[x]**2 for x in vec1.keys())
    sum2 = sum(vec2[x]**2 for x in vec2.keys())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    return numerator / denominator if denominator > 0 else 0.0

def analyze_text_chronology(text: str) -> tuple[int, int]:
    logger.info(f"Анализ текста: {len(text)} символов")

    if not text or len(text.strip()) < 5:
        logger.warning("Текст слишком короткий, возвращаем дефолт")
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
        logger.warning("Пустой scores, возвращаем дефолт")
        return 1500, 0

    best_year = max(scores, key=scores.get)

    archaic_words = set(w for vocab in ARCHAIC_VOCABULARY.values() for w in vocab)
    total_matches = sum(1 for word in words if word in archaic_words)

    logger.info(f"Результат: год={best_year}, совпадений={total_matches}, readability={readability:.1f}")
    return best_year, total_matches

@app.post("/calculate-chrono", response_model=ChronoResult)
async def calculate_chrono(request: ChronoRequest):
    logger.info(f"Запрос: ID={request.research_request_id}, текст={len(request.text_for_analysis or '')} символов")

    if request.auth_token != AUTH_TOKEN_EXPECTED:
        logger.warning(f"❌ Неверный токен: {request.auth_token}")
        raise HTTPException(status_code=403, detail="Invalid auth token")

    if not request.text_for_analysis or not request.text_for_analysis.strip():
        logger.warning(f"Пустой текст для ID={request.research_request_id}")
        return ChronoResult(status="skipped", error="no text")

    try:
        logger.info(f"Начинаем расчет для ID={request.research_request_id}...")
        await asyncio.sleep(5)

        calculated_year, matched_count = analyze_text_chronology(request.text_for_analysis)

        result_data = {
            "research_request_id": request.research_request_id,
            "result_from_year": calculated_year,
            "result_to_year": calculated_year + 50,
            "matched_layers": matched_count,
            "auth_token": AUTH_TOKEN_EXPECTED
        }

        logger.info(f"Отправляем в Go: {result_data}")

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.post(
                    f"http://0.0.0.0:8080/api/chrono/async-result",
                    json=result_data
                )
                resp.raise_for_status()
                logger.info(f"✅ Go сервис принял результат ID={request.research_request_id}")
        except httpx.HTTPError as e:
            logger.error(f"Сетевая ошибка Go: {e} (но расчет успешен!)")
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при отправке: {e}")

        logger.info(f"🎉 Расчет завершен успешно ID={request.research_request_id}")
        return ChronoResult(
            status="success",
            year=calculated_year,
            matched_layers=matched_count
        )

    except Exception as e:
        logger.error(f"Критическая ошибка ID={request.research_request_id}: {str(e)}")
        return ChronoResult(status="error", error=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "main_service": MAIN_SERVICE_URL,
        "token": AUTH_TOKEN_EXPECTED[:4] + "..."
    }

@app.get("/")
async def root():
    return {"message": "Chrono Calculator готов к работе", "port": 9001}

if __name__ == "__main__":
    logger.info(f"🚀 Запуск Chrono Calculator на {MAIN_SERVICE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=9001, log_level="info")
