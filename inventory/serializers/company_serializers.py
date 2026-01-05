from rest_framework import serializers

from inventory.models import Company


class CompanySerializer(serializers.ModelSerializer):
    """Company serializer"""

    class Meta:
        model = Company
        fields = ["id", "name", "rut", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
