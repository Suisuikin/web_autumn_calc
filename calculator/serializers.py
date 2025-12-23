from rest_framework import serializers
from .models import ChronoCalculation

class ChronoRequestSerializer(serializers.Serializer):
    research_request_id = serializers.IntegerField()
    auth_token = serializers.CharField()
    text_for_analysis = serializers.CharField(required=False, allow_blank=True)
    purpose = serializers.CharField(required=False, allow_blank=True)

class ChronoResultSerializer(serializers.Serializer):
    status = serializers.CharField()
    year = serializers.IntegerField(required=False, allow_null=True)
    matched_layers = serializers.IntegerField(required=False, allow_null=True)
    error = serializers.CharField(required=False, allow_blank=True)
