from django.db import transaction

from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from inventory.models import Template, TemplateAttribute
from inventory.permissions import IsCompanyMember, IsAdminUser, IsAdminOrReadOnly
from inventory.serializers import (
    TemplateDetailSerializer,
    TemplateSerializer,
    TemplateAttributeCreateSerializer,
    TemplateAttributeSerializer,
    ProductListSerializer,
)


class TemplateViewSet(viewsets.ModelViewSet):
    """
    Product templates with dynamic attributes.
    Admin can create/update/delete, others can only read.
    """

    permission_classes = [IsAuthenticated, IsCompanyMember, IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TemplateDetailSerializer
        return TemplateSerializer

    def get_queryset(self):
        """Filter by user's company"""
        return Template.objects.filter(
            company=self.request.user.company, is_active=True
        ).prefetch_related(
            "template_attributes__custom_attribute",
            "template_attributes__global_attribute",
        )

    @action(detail=True, methods=["get"])
    def structure(self, request, pk=None):
        """
        Get template structure for dynamic forms.
        Returns attribute definitions in order.
        """
        template = self.get_object()
        return Response(
            {
                "template_id": template.id,
                "template_name": template.name,
                "description": template.description,
                "attributes": template.get_attribute_structure(),
            }
        )

    @action(
        detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsAdminUser]
    )
    def add_attribute(self, request, pk=None):
        """Add an attribute to this template"""
        template = self.get_object()

        serializer = TemplateAttributeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate attribute belongs to same company
        custom_attr = serializer.validated_data.get("custom_attribute")
        if custom_attr and custom_attr.company != template.company:
            return Response(
                {"error": "Custom attribute must belong to the same company"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template_attr = TemplateAttribute.objects.create(
            template=template, **serializer.validated_data
        )

        return Response(
            TemplateAttributeSerializer(template_attr).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def remove_attribute(self, request, pk=None):
        """Remove an attribute from this template"""
        template = self.get_object()
        attribute_id = request.data.get("attribute_id")

        if not attribute_id:
            return Response(
                {"error": "attribute_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template_attr = template.template_attributes.get(id=attribute_id)
            template_attr.is_active = False
            template_attr.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TemplateAttribute.DoesNotExist:
            return Response(
                {"error": "Attribute not found in this template"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def reorder_attributes(self, request, pk=None):
        """
        Reorder template attributes.
        Expects: {"attributes": [{"id": 1, "order": 0}, {"id": 2, "order": 1}]}
        """
        template = self.get_object()
        attributes_data = request.data.get("attributes", [])

        if not attributes_data:
            return Response(
                {"error": "attributes list is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for attr_data in attributes_data:
                attr_id = attr_data.get("id")
                order = attr_data.get("order")

                if attr_id is None or order is None:
                    continue

                try:
                    template_attr = template.template_attributes.get(id=attr_id)
                    template_attr.order = order
                    template_attr.save()
                except TemplateAttribute.DoesNotExist:
                    pass

        return Response({"message": "Attributes reordered successfully"})

    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Get all products using this template"""
        template = self.get_object()
        products = template.products.filter(is_active=True)

        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Soft delete"""
        instance = self.get_object()

        # Check if template has active products
        if instance.products.filter(is_active=True).exists():
            return Response(
                {"error": "Cannot delete template with active products"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
