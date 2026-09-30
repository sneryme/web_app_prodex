from rest_framework import serializers

from .models import ConsentRecord


class CreateSessionSerializer(serializers.Serializer):
    entry_code = serializers.CharField(max_length=32)


class ConsentSerializer(serializers.Serializer):
    consent_type = serializers.ChoiceField(
        choices=[ConsentRecord.TYPE_DATA_PROCESSING, ConsentRecord.TYPE_INFORMED_NOTICE]
    )
    text_version = serializers.CharField(max_length=32)
    accepted = serializers.BooleanField()


class AnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    option_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    raw_value = serializers.CharField(required=False, allow_blank=True, default="")
