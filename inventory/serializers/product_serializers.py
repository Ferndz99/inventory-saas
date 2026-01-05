from datetime import datetime
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field, inline_serializer

from inventory.models import Product


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

    @extend_schema_field(
        inline_serializer(
            name="TemplateStructure",
            many=True,
            fields={
                "slug": serializers.CharField(),
                "name": serializers.CharField(),
                "data_type": serializers.CharField(),
                "unit_of_measure": serializers.CharField(allow_null=True),
                "description": serializers.CharField(allow_null=True),
                "is_required": serializers.BooleanField(),
                "order": serializers.IntegerField(),
                "value": serializers.JSONField(
                    allow_null=True
                ),  # Puede ser de cualquier tipo
                "default_value": serializers.CharField(allow_null=True),
            },
        )
    )
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

    @extend_schema_field(
        inline_serializer(
            name="StockByWarehouse",
            many=True,
            fields={
                "warehouse_id": serializers.IntegerField(),
                "warehouse_name": serializers.CharField(),
                "quantity": serializers.DecimalField(max_digits=12, decimal_places=2),
                "is_main": serializers.BooleanField(),
            },
        )
    )
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

    @extend_schema_field(
        inline_serializer(
            name="FormattedSpecification",
            many=True,
            fields={
                "label": serializers.CharField(),
                "value": serializers.JSONField(),  # Usamos JSONField si el valor puede ser núm o string
                "unit": serializers.CharField(allow_null=True),
                "formatted": serializers.CharField(),
            },
        )
    )
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
