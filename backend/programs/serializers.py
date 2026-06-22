from rest_framework import serializers
from .models import Program

class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = (
            'id', 'title', 'description', 'thumbnail', 'is_active',
            'created_by', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')
