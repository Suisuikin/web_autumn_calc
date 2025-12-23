from django.db import models
from django.core.validators import MinValueValidator

class ChronoCalculation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('processing', 'Обработка'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
    ]

    research_request_id = models.IntegerField(unique=True, db_index=True)
    text_for_analysis = models.TextField()
    purpose = models.TextField(null=True, blank=True)
    user_id = models.IntegerField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_from_year = models.IntegerField(null=True, blank=True)
    result_to_year = models.IntegerField(null=True, blank=True)
    matched_layers = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'chrono_calculations'
        ordering = ['-created_at']

    def __str__(self):
        return f"Calculation #{self.research_request_id}"
