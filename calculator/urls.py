from django.urls import path
from . import views

urlpatterns = [
    path('calculate/', views.calculate_chrono, name='calculate_chrono'),
    path('health/', views.health_check, name='health'),
]
