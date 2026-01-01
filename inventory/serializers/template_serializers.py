from rest_framework import serializers

from inventory.models import Template, TemplateAttribute

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
