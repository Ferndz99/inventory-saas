from rest_framework import serializers

from inventory.models import Category

class CategorySerializer(serializers.ModelSerializer):
    """Category serializer with automatic company assignment"""

    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "company", "is_active", "product_count", "created_at"]
        read_only_fields = ["company", "created_at"]

    def get_product_count(self, obj):
        """Count active products in this category"""
        return obj.products.filter(is_active=True).count()

    def create(self, validated_data):
        """Auto-assign company from request user"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            validated_data["company"] = request.user.company
        return super().create(validated_data)
