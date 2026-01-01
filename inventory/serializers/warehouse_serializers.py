from django.db.models import ExpressionWrapper, DecimalField

from rest_framework import serializers

from inventory.models import Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    """Warehouse serializer"""

    product_count = serializers.SerializerMethodField()
    total_stock_value = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "name",
            "address",
            "is_main",
            "company",
            "product_count",
            "total_stock_value",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["company", "created_at"]

    def get_product_count(self, obj):
        """Count unique products with stock in this warehouse"""
        return obj.stock_records.filter(current_quantity__gt=0, is_active=True).count()

    def get_total_stock_value(self, obj):
        """Calculate total stock value in this warehouse"""
        from django.db.models import Sum, F

        total = obj.stock_records.filter(is_active=True).aggregate(
            total_value=Sum(
                ExpressionWrapper(
                    F("current_quantity") * F("product__cost"),
                    output_field=DecimalField(),
                )
            )
        )

        return total["total_value"] or 0

    def create(self, validated_data):
        """Auto-assign company from request user"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            validated_data["company"] = request.user.company
        return super().create(validated_data)
