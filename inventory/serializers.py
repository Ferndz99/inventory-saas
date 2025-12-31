from rest_framework import serializers
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.db import transaction
from django.db.models import ExpressionWrapper, DecimalField
from django.core.exceptions import ValidationError as DjangoValidationError

from inventory.models import (
    Company,
    Category,
    GlobalAttribute,
    CustomAttribute,
    Template,
    TemplateAttribute,
    Product,
    Warehouse,
    StockRecord,
    StockMovement,
)


# ============================================================
# COMPANY & BASIC MODELS
# ============================================================


class CompanySerializer(serializers.ModelSerializer):
    """Company serializer"""

    class Meta:
        model = Company
        fields = ["id", "name", "rut", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


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


# ============================================================
# ATTRIBUTES
# ============================================================


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


# ============================================================
# TEMPLATES
# ============================================================


class TemplateAttributeSerializer(serializers.ModelSerializer):
    """Template attribute with attribute details"""

    attribute_name = serializers.SerializerMethodField()
    attribute_slug = serializers.SerializerMethodField()
    attribute_type = serializers.SerializerMethodField()
    attribute_unit = serializers.SerializerMethodField()
    attribute_description = serializers.SerializerMethodField()

    class Meta:
        model = TemplateAttribute
        fields = [
            "id",
            "custom_attribute",
            "global_attribute",
            "is_required",
            "order",
            "default_value",
            "is_active",
            "attribute_name",
            "attribute_slug",
            "attribute_type",
            "attribute_unit",
            "attribute_description",
        ]

    def get_attribute_name(self, obj):
        attr = obj.custom_attribute or obj.global_attribute
        return attr.name if attr else None

    def get_attribute_slug(self, obj):
        attr = obj.custom_attribute or obj.global_attribute
        return attr.slug if attr else None

    def get_attribute_type(self, obj):
        attr = obj.custom_attribute or obj.global_attribute
        return attr.data_type if attr else None

    def get_attribute_unit(self, obj):
        attr = obj.custom_attribute or obj.global_attribute
        return attr.unit_of_measure if attr else None

    def get_attribute_description(self, obj):
        attr = obj.custom_attribute or obj.global_attribute
        return attr.description if attr else None


class TemplateAttributeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating template attributes"""

    class Meta:
        model = TemplateAttribute
        fields = [
            "custom_attribute",
            "global_attribute",
            "is_required",
            "order",
            "default_value",
        ]

    def validate(self, attrs):
        """Validate that either custom or global attribute is set"""
        if not attrs.get("custom_attribute") and not attrs.get("global_attribute"):
            raise serializers.ValidationError(
                "Either custom_attribute or global_attribute must be provided"
            )
        if attrs.get("custom_attribute") and attrs.get("global_attribute"):
            raise serializers.ValidationError(
                "Only one of custom_attribute or global_attribute can be set"
            )
        return attrs


class TemplateSerializer(serializers.ModelSerializer):
    """Template serializer with attributes"""

    template_attributes = TemplateAttributeSerializer(many=True, read_only=True)
    attribute_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Template
        fields = [
            "id",
            "name",
            "description",
            "company",
            "is_active",
            "template_attributes",
            "attribute_count",
            "product_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["company", "created_at", "updated_at"]

    def get_attribute_count(self, obj):
        return obj.template_attributes.filter(is_active=True).count()

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()

    def create(self, validated_data):
        """Auto-assign company from request user"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            validated_data["company"] = request.user.company
        return super().create(validated_data)


class TemplateDetailSerializer(TemplateSerializer):
    """Detailed template serializer with formatted attribute structure"""

    attribute_structure = serializers.SerializerMethodField()

    class Meta(TemplateSerializer.Meta):
        fields = TemplateSerializer.Meta.fields + ["attribute_structure"]

    def get_attribute_structure(self, obj):
        """
        Return formatted attribute structure for frontend forms.
        This is what the frontend will use to build dynamic forms.
        """
        return obj.get_attribute_structure()


# ============================================================
# PRODUCTS
# ============================================================


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for product list"""

    category_name = serializers.CharField(source="category.name", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    total_stock = serializers.SerializerMethodField()
    below_minimum = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "barcode",
            "price",
            "cost",
            # "category",
            "category_name",
            # "template",
            "template_name",
            "total_stock",
            "below_minimum",
            "is_active",
            "unit_of_measure",
        ]

    def get_total_stock(self, obj):
        """Get total stock across all warehouses"""
        return obj.get_total_stock()

    def get_below_minimum(self, obj):
        """Check if stock is below minimum"""
        return obj.is_below_minimum()


class ProductSerializer(serializers.ModelSerializer):
    """
    Full product serializer with dynamic specification validation
    """

    # category = serializers.PrimaryKeyRelatedField(
    #     queryset=Category.objects.all(), write_only=True
    # )
    # template = serializers.PrimaryKeyRelatedField(
    #     queryset=Template.objects.all(), write_only=True
    # )
    category_name = serializers.CharField(source="category.name", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    total_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "barcode",
            "price",
            "cost",
            "price_includes_tax",
            "category",
            "category_name",
            "template",
            "template_name",
            "specifications",
            "company",
            "minimum_stock",
            "unit_of_measure",
            "total_stock",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["company", "created_at", "updated_at"]

    def get_total_stock(self, obj):
        return obj.get_total_stock()

    def validate_sku(self, value):
        """Validate SKU is unique within company"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            qs = Product.objects.filter(sku=value, company=request.user.company)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "A product with this SKU already exists in your company"
                )
        return value.upper()  # Normalize to uppercase

    def validate_barcode(self, value):
        """Normalize barcode"""
        if value:
            return value.strip()
        return value

    def validate(self, attrs):
        """Validate specifications against template requirements"""
        template = attrs.get("template") or (
            self.instance.template if self.instance else None
        )
        specifications = attrs.get("specifications", {})

        if not template:
            raise serializers.ValidationError({"template": "Template is required"})

        # Get all active template attributes
        template_attrs = template.template_attributes.filter(
            is_active=True
        ).select_related("custom_attribute", "global_attribute")

        errors = {}
        validated_specs = {}

        for template_attr in template_attrs:
            # Get the actual attribute (custom or global)
            attribute = template_attr.custom_attribute or template_attr.global_attribute
            attr_slug = attribute.slug
            attr_value = specifications.get(attr_slug)

            # Check if required attribute is missing
            if (
                template_attr.is_required
                and not attr_value
                and attr_value != 0
                and attr_value != False
            ):
                # Use default value if available
                if template_attr.default_value:
                    attr_value = template_attr.default_value
                else:
                    errors[attr_slug] = f"{attribute.name} is required"
                    continue

            # Skip validation if attribute is not required and not provided
            if attr_value is None or attr_value == "":
                continue

            # Validate based on data type
            try:
                validated_value = self._validate_attribute_value(
                    attr_value, attribute.data_type, attribute.name
                )
                validated_specs[attr_slug] = validated_value
            except serializers.ValidationError as e:
                errors[attr_slug] = (
                    str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
                )

        # Check for unknown attributes not in template
        template_slugs = {
            (ta.custom_attribute or ta.global_attribute).slug for ta in template_attrs
        }
        unknown_attrs = set(specifications.keys()) - template_slugs

        if unknown_attrs:
            errors["specifications"] = (
                f"Unknown attributes not in template: {', '.join(unknown_attrs)}"
            )

        if errors:
            raise serializers.ValidationError(errors)

        # Update specifications with validated values
        attrs["specifications"] = validated_specs

        return attrs

    def _validate_attribute_value(self, value, data_type, attr_name):
        """Validate individual attribute value based on data type"""

        if data_type == "text":
            if not isinstance(value, str):
                raise serializers.ValidationError(f"{attr_name} must be text")
            return value.strip()

        elif data_type == "number":
            try:
                numeric_value = float(value)
                return numeric_value
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"{attr_name} must be a valid number")

        elif data_type == "decimal":
            try:
                decimal_value = Decimal(str(value))
                # Return as string to preserve precision in JSON
                return str(decimal_value)
            except (InvalidOperation, ValueError, TypeError):
                raise serializers.ValidationError(
                    f"{attr_name} must be a valid decimal number"
                )

        elif data_type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                value_lower = value.lower().strip()
                if value_lower in ("true", "1", "yes", "si", "sí"):
                    return True
                if value_lower in ("false", "0", "no"):
                    return False
            raise serializers.ValidationError(f"{attr_name} must be true/false")

        elif data_type == "date":
            if isinstance(value, str):
                # Try multiple date formats (Chilean formats)
                date_formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]
                for date_format in date_formats:
                    try:
                        parsed_date = datetime.strptime(value, date_format)
                        return parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
                raise serializers.ValidationError(
                    f"{attr_name} must be a valid date (YYYY-MM-DD, DD-MM-YYYY, or DD/MM/YYYY)"
                )
            raise serializers.ValidationError(f"{attr_name} must be a date string")

        return value

    def validate_template(self, value):
        """Ensure template belongs to the same company"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            if value.company != request.user.company:
                raise serializers.ValidationError(
                    "Template must belong to your company"
                )
        return value

    def validate_category(self, value):
        """Ensure category belongs to the same company"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            if value.company != request.user.company:
                raise serializers.ValidationError(
                    "Category must belong to your company"
                )
        return value

    def create(self, validated_data):
        """Auto-assign company from request user"""
        request = self.context.get("request")
        if request and hasattr(request.user, "company"):
            validated_data["company"] = request.user.company
        return super().create(validated_data)


class ProductDetailSerializer(ProductSerializer):
    """
    Detailed product serializer with template structure and stock info
    """

    template_structure = serializers.SerializerMethodField()
    stock_by_warehouse = serializers.SerializerMethodField()
    formatted_specifications = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + [
            "template_structure",
            "stock_by_warehouse",
            "formatted_specifications",
        ]

    def get_template_structure(self, obj):
        """Return the template structure with current values"""
        template_attrs = (
            obj.template.template_attributes.filter(is_active=True)
            .select_related("custom_attribute", "global_attribute")
            .order_by("order")
        )

        structure = []
        for template_attr in template_attrs:
            attribute = template_attr.custom_attribute or template_attr.global_attribute

            structure.append(
                {
                    "slug": attribute.slug,
                    "name": attribute.name,
                    "data_type": attribute.data_type,
                    "unit_of_measure": attribute.unit_of_measure,
                    "description": attribute.description,
                    "is_required": template_attr.is_required,
                    "order": template_attr.order,
                    "value": obj.specifications.get(attribute.slug),
                    "default_value": template_attr.default_value,
                }
            )

        return structure

    def get_stock_by_warehouse(self, obj):
        """Get stock information by warehouse"""
        stock_records = obj.stock_records.select_related("warehouse").filter(
            is_active=True, warehouse__is_active=True
        )

        return [
            {
                "warehouse_id": sr.warehouse.id,
                "warehouse_name": sr.warehouse.name,
                "quantity": sr.current_quantity,
                "is_main": sr.warehouse.is_main,
            }
            for sr in stock_records
        ]

    def get_formatted_specifications(self, obj):
        """
        Return specifications formatted with labels and units.
        Useful for display purposes.
        """
        template_attrs = (
            obj.template.template_attributes.filter(is_active=True)
            .select_related("custom_attribute", "global_attribute")
            .order_by("order")
        )

        formatted = []
        for template_attr in template_attrs:
            attribute = template_attr.custom_attribute or template_attr.global_attribute
            value = obj.specifications.get(attribute.slug)

            if value is not None:
                formatted.append(
                    {
                        "label": attribute.name,
                        "value": value,
                        "unit": attribute.unit_of_measure,
                        "formatted": f"{value} {attribute.unit_of_measure}".strip(),
                    }
                )

        return formatted


# ============================================================
# WAREHOUSE
# ============================================================


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


# ============================================================
# STOCK MANAGEMENT
# ============================================================


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
