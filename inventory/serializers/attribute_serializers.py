from rest_framework import serializers

from inventory.models import CustomAttribute, GlobalAttribute


class GlobalAttributeSerializer(serializers.ModelSerializer):
    """Global attributes available for all companies"""

    class Meta:
        model = GlobalAttribute
        fields = [
            "id",
            "name",
            "slug",
            "data_type",
            "unit_of_measure",
            "description",
            "is_active",
        ]
        read_only_fields = ["slug"]


class CustomAttributeSerializer(serializers.ModelSerializer):
    """Company-specific custom attributes"""

    class Meta:
        model = CustomAttribute
        fields = [
            "id",
            "name",
            "slug",
            "data_type",
            "unit_of_measure",
            "description",
            "company",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["company", "slug", "created_at"]

    def create(self, validated_data):
        """Auto-assign company from request user"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            validated_data["company"] = request.user.company
        return super().create(validated_data)
