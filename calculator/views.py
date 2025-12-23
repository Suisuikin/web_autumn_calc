import logging
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import ChronoRequestSerializer, ChronoResultSerializer
from .tasks import calculate_chrono_async
from .models import ChronoCalculation

logger = logging.getLogger(__name__)

@api_view(['POST'])
def calculate_chrono(request):
    """
    Запуск асинхронного расчета Celery задачи

    POST /api/chrono/calculate/
    {
        "research_request_id": 7,
        "auth_token": "111517",
        "text_for_analysis": "thou hath dost",
        "purpose": "test"
    }
    """
    serializer = ChronoRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Валидация токена
    if serializer.validated_data.get('auth_token') != settings.AUTH_TOKEN:
        logger.warning(f"❌ Неверный токен: {serializer.validated_data.get('auth_token')}")
        return Response(
            {"error": "Invalid auth token"},
            status=status.HTTP_403_FORBIDDEN
        )

    request_id = serializer.validated_data['research_request_id']
    text = serializer.validated_data.get('text_for_analysis', '')
    purpose = serializer.validated_data.get('purpose')

    if not text or not text.strip():
        logger.warning(f"⚠️ Пустой текст для ID={request_id}")
        return Response(
            {"status": "skipped", "error": "no text"},
            status=status.HTTP_400_BAD_REQUEST
        )

    logger.info(f"🚀 Запуск Celery задачи для ID={request_id}")

    task = calculate_chrono_async.delay(request_id, text, purpose)

    logger.info(f"📤 Task ID: {task.id}")

    return Response({
        "status": "processing",
        "research_request_id": request_id,
        "task_id": task.id
    }, status=status.HTTP_202_ACCEPTED)

@api_view(['GET'])
def health_check(request):
    """Health check"""
    return Response({
        "status": "healthy",
        "main_service": settings.MAIN_SERVICE_URL,
        "token": settings.AUTH_TOKEN[:4] + "..."
    })
