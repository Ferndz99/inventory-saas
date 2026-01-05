from django.db import transaction

from rest_framework import serializers

from inventory.models import Product, StockMovement, StockRecord, Warehouse


class StockRecordSerializer(serializers.ModelSerializer):
    """Stock record serializer"""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = StockRecord
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "warehouse",
            "warehouse_name",
            "current_quantity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class StockMovementSerializer(serializers.ModelSerializer):
    """Stock movement serializer with validation"""

    product_name = serializers.CharField(
        source="stock_record.product.name", read_only=True
    )
    warehouse_name = serializers.CharField(
        source="stock_record.warehouse.name", read_only=True
    )
    account_email = serializers.CharField(source="account.email", read_only=True)
    from_warehouse_name = serializers.CharField(
        source="from_warehouse.name", read_only=True, allow_null=True
    )
    to_warehouse_name = serializers.CharField(
        source="to_warehouse.name", read_only=True, allow_null=True
    )

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "stock_record",
            "product_name",
            "warehouse_name",
            "movement_type",
            "quantity",
            "resulting_balance",
            "reason",
            "account",
            "account_email",
            "notes",
            "reference_document",
            "unit_cost",
            "from_warehouse",
            "from_warehouse_name",
            "to_warehouse",
            "to_warehouse_name",
            "created_at",
        ]
        read_only_fields = ["account", "resulting_balance", "created_at"]

    def validate(self, attrs):
        """Validate movement"""
        stock_record = attrs.get("stock_record")
        movement_type = attrs.get("movement_type")
        quantity = attrs.get("quantity")

        # Validate OUT movements
        if movement_type == "OUT":
            if quantity > stock_record.current_quantity:
                raise serializers.ValidationError(
                    {
                        "quantity": f"Insufficient stock. Available: {stock_record.current_quantity}"
                    }
                )

        # Validate TRANSFER movements
        if movement_type == "TRANSFER":
            if not attrs.get("from_warehouse") or not attrs.get("to_warehouse"):
                raise serializers.ValidationError(
                    {
                        "movement_type": "Transfer movements require both from_warehouse and to_warehouse"
                    }
                )
            if attrs.get("from_warehouse") == attrs.get("to_warehouse"):
                raise serializers.ValidationError(
                    {
                        "to_warehouse": "Destination warehouse must be different from origin"
                    }
                )

        return attrs

    def create(self, validated_data):
        """Auto-assign account from request user"""
        request = self.context.get("request")
        if request:
            validated_data["account"] = request.user
        return super().create(validated_data)


class StockMovementCreateSerializer(serializers.Serializer):
    """
    Simplified serializer for creating stock movements.
    Handles common operations like purchases, sales, and adjustments.
    """

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True
    )
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    movement_type = serializers.ChoiceField(choices=StockMovement.MOVEMENT_TYPE_CHOICES)
    quantity = serializers.FloatField(min_value=0.01)
    reason = serializers.ChoiceField(choices=StockMovement.REASON_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    reference_document = serializers.CharField(required=False, allow_blank=True)
    unit_cost = serializers.DecimalField(
        max_digits=10, decimal_places=0, required=True, allow_null=True
    )

    # For transfers
    to_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), required=False, allow_null=True
    )

    def validate(self, attrs):
        """Validate and prepare movement"""
        request = self.context.get("request")
        product = attrs["product"]
        warehouse = attrs["warehouse"]
        movement_type = attrs["movement_type"]
        quantity = attrs["quantity"]

        # Validate product and warehouse belong to same company
        if request and hasattr(request.user, "company"):
            if product.company != request.user.company:
                raise serializers.ValidationError(
                    {"product": "Product must belong to your company"}
                )
            if warehouse.company != request.user.company:
                raise serializers.ValidationError(
                    {"warehouse": "Warehouse must belong to your company"}
                )

        # Get or create stock record
        stock_record, created = StockRecord.objects.get_or_create(
            product=product, warehouse=warehouse, defaults={"current_quantity": 0}
        )

        # Validate OUT movements
        if movement_type == "OUT" and quantity > stock_record.current_quantity:
            raise serializers.ValidationError(
                {
                    "quantity": f"Insufficient stock. Available: {stock_record.current_quantity}"
                }
            )

        # Validate transfers
        if movement_type == "TRANSFER":
            to_warehouse = attrs.get("to_warehouse")
            if not to_warehouse:
                raise serializers.ValidationError(
                    {"to_warehouse": "Transfer movements require destination warehouse"}
                )
            if warehouse == to_warehouse:
                raise serializers.ValidationError(
                    {"to_warehouse": "Destination must be different from origin"}
                )
            if to_warehouse.company != request.user.company:
                raise serializers.ValidationError(
                    {
                        "to_warehouse": "Destination warehouse must belong to your company"
                    }
                )

        attrs["stock_record"] = stock_record
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create movement and update stock"""
        request = self.context.get("request")

        stock_record = validated_data.pop("stock_record")
        product = validated_data.pop("product")
        warehouse = validated_data.pop("warehouse")
        to_warehouse = validated_data.pop("to_warehouse", None)

        movement_type = validated_data["movement_type"]
        quantity = validated_data["quantity"]

        # Create the movement
        movement = StockMovement.objects.create(
            stock_record=stock_record,
            account=request.user,
            from_warehouse=warehouse if movement_type == "TRANSFER" else None,
            to_warehouse=to_warehouse,
            **validated_data,
        )

        # If it's a transfer, create the corresponding IN movement
        if movement_type == "TRANSFER" and to_warehouse:
            # Get or create stock record for destination

            stock_record.current_quantity -= quantity
            stock_record.save(update_fields=["current_quantity"])

            dest_stock_record, _ = StockRecord.objects.get_or_create(
                product=product,
                warehouse=to_warehouse,
                defaults={"current_quantity": 0},
            )

            # Create IN movement at destination
            StockMovement.objects.create(
                stock_record=dest_stock_record,
                movement_type="IN",
                quantity=quantity,
                resulting_balance=dest_stock_record.current_quantity + quantity,
                reason="transfer",
                account=request.user,
                notes=f"Transfer from {warehouse.name}",
                reference_document=validated_data.get("reference_document", ""),
                unit_cost=validated_data.get("unit_cost", ""),
                from_warehouse=warehouse,
                to_warehouse=to_warehouse,
            )

        return movement


class StockAdjustmentSerializer(serializers.Serializer):
    """
    Serializer for stock adjustments (reconciliation).
    Sets the stock to a specific quantity.
    """

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    new_quantity = serializers.FloatField(min_value=0)
    notes = serializers.CharField(required=True)

    def validate(self, attrs):
        """Validate adjustment"""
        request = self.context.get("request")
        product = attrs["product"]
        warehouse = attrs["warehouse"]

        if request and hasattr(request.user, "company"):
            if product.company != request.user.company:
                raise serializers.ValidationError(
                    {"product": "Product must belong to your company"}
                )
            if warehouse.company != request.user.company:
                raise serializers.ValidationError(
                    {"warehouse": "Warehouse must belong to your company"}
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create adjustment movement"""
        request = self.context.get("request")
        product = validated_data["product"]
        warehouse = validated_data["warehouse"]
        new_quantity = validated_data["new_quantity"]
        notes = validated_data["notes"]

        # Get or create stock record
        stock_record, created = StockRecord.objects.get_or_create(
            product=product, warehouse=warehouse, defaults={"current_quantity": 0}
        )

        current_quantity = stock_record.current_quantity
        difference = new_quantity - current_quantity

        if difference == 0:
            raise serializers.ValidationError(
                {"new_quantity": "New quantity is the same as current quantity"}
            )

        # Determine movement type
        movement_type = "IN" if difference > 0 else "OUT"
        quantity = abs(difference)

        # Create adjustment movement
        movement = StockMovement.objects.create(
            stock_record=stock_record,
            movement_type=movement_type,
            quantity=quantity,
            resulting_balance=new_quantity,
            reason="adjustment",
            account=request.user,
            notes=f"Adjustment: {notes} (from {current_quantity} to {new_quantity})",
        )

        return movement
