from django.db import transaction
from django.core.exceptions import ValidationError

from rest_framework import viewsets, status, filters, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer

from inventory.models import Template, TemplateAttribute
from inventory.permissions import IsCompanyMember, IsAdminUser, IsAdminOrReadOnly
from inventory.serializers import (
    TemplateDetailSerializer,
    TemplateSerializer,
    TemplateAttributeCreateSerializer,
    TemplateAttributeSerializer,
    ProductListSerializer,
)

from inventory.utils import (
    error_401,
    error_400,
    error_403,
    error_404,
    error_500,
    success_200,
    success_201,
    success_204,
)


@extend_schema(tags=["Templates"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(TemplateSerializer, many=True),
            **error_401("template"),
            **error_403("template"),
            **error_500("template"),
        },
    ),
    create=extend_schema(
        summary="Create",
        request=TemplateSerializer,
        responses={
            **success_201(TemplateSerializer),
            **error_400("template"),
            **error_401("template"),
            **error_403("template"),
            **error_500("template"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(TemplateSerializer),
            **error_401("template", is_detail=True),
            **error_403("template", is_detail=True),
            **error_404("template", is_detail=True),
            **error_500("template", is_detail=True),
        },
    ),
    update=extend_schema(
        summary="Edit (Admin)",
        request=TemplateSerializer,
        responses={
            **success_200(TemplateSerializer),
            **error_400("template", is_detail=True),
            **error_401("template", is_detail=True),
            **error_403("template", is_detail=True),
            **error_404("template", is_detail=True),
            **error_500("template", is_detail=True),
        },
    ),
    partial_update=extend_schema(
        summary="Edit partial (Admin)",
        request=TemplateSerializer,
        responses={
            **success_200(TemplateSerializer),
            **error_400("template", is_detail=True),
            **error_401("template", is_detail=True),
            **error_403("template", is_detail=True),
            **error_404("template", is_detail=True),
            **error_500("template", is_detail=True),
        },
    ),
    destroy=extend_schema(
        summary="Delete (Admin)",
        responses={
            **success_204(),
            **error_401("template", is_detail=True),
            **error_403("template", is_detail=True),
            **error_404("template", is_detail=True),
            **error_500("template", is_detail=True),
        },
    ),
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

    @extend_schema(
        summary="Estructura de la plantilla para formularios",
        description=(
            "Devuelve la definición técnica de todos los atributos asociados a esta plantilla. "
            "Es ideal para que el Frontend genere formularios dinámicos, ya que incluye tipos de datos, "
            "etiquetas, validaciones y orden de visualización."
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="TemplateStructureResponse",
                    fields={
                        "template_id": serializers.UUIDField(),
                        "template_name": serializers.CharField(),
                        "description": serializers.CharField(),
                        "attributes": inline_serializer(
                            name="AttributeDefinition",
                            many=True,
                            fields={
                                "slug": serializers.CharField(
                                    help_text="Identificador único del atributo"
                                ),
                                "name": serializers.CharField(
                                    help_text="Etiqueta visible para el usuario"
                                ),
                                "data_type": serializers.ChoiceField(
                                    choices=[
                                        "text",
                                        "number",
                                        "boolean",
                                        "date",
                                        "select",
                                    ],
                                    help_text="Tipo de dato esperado",
                                ),
                                "unit_of_measure": serializers.CharField(
                                    allow_blank=True
                                ),
                                "description": serializers.CharField(allow_blank=True),
                                "is_required": serializers.BooleanField(),
                                "order": serializers.IntegerField(
                                    help_text="Posición en el formulario"
                                ),
                                "default_value": serializers.CharField(
                                    allow_blank=True
                                ),
                            },
                        ),
                    },
                )
            ),
            **error_401("template", action="structure", is_detail=True),
            **error_404("template", action="structure", is_detail=True),
            **error_500("template", action="structure", is_detail=True),
        },
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

    @extend_schema(
        summary="Añadir atributo a la plantilla",
        description=(
            "Asocia un nuevo atributo dinámico a la plantilla. "
            "Requiere permisos de administrador y que el atributo pertenezca a la misma empresa que la plantilla."
        ),
        request=TemplateAttributeCreateSerializer,
        responses={
            201: TemplateAttributeSerializer,
            **error_400("template", action="add_attribute", is_detail=True),
            **error_401("template", action="add_attribute", is_detail=True),
            **error_403("template", action="add_attribute", is_detail=True),
            **error_404("template", action="add_attribute", is_detail=True),
            **error_500("template", action="add_attribute", is_detail=True),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsAdminUser],
        url_path="add-attribute",
    )
    def add_attribute(self, request, pk=None):
        """Add an attribute to this template"""
        template = self.get_object()

        serializer = TemplateAttributeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate attribute belongs to same company
        custom_attr = serializer.validated_data.get("custom_attribute")
        if custom_attr and custom_attr.company != template.company:
            raise ValidationError(
                {"custom_attribute": "Custom attribute must belong to the same company"}
            )

        template_attr = TemplateAttribute.objects.create(
            template=template, **serializer.validated_data
        )

        return Response(
            TemplateAttributeSerializer(template_attr).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Eliminar atributo de la plantilla",
        description=(
            "Desactiva (soft-delete) la relación entre un atributo y la plantilla. "
            "Requiere el ID de la relación TemplateAttribute en el cuerpo de la petición."
        ),
        request=inline_serializer(
            name="RemoveAttributeRequest",
            fields={
                "attribute_id": serializers.UUIDField(
                    help_text="ID de la relación TemplateAttribute a eliminar"
                )
            },
        ),
        responses={
            204: None,
            **error_400("template", action="remove_attribute", is_detail=True),
            **error_401("template", action="remove_attribute", is_detail=True),
            **error_403("template", action="remove_attribute", is_detail=True),
            **error_404("template", action="remove_attribute", is_detail=True),
            **error_500("template", action="remove_attribute", is_detail=True),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsAdminUser],
        url_path="remove-attribute",
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

    @extend_schema(
        summary="Reordenar atributos de la plantilla",
        description=(
            "Actualiza la posición (orden) de múltiples atributos asociados a la plantilla en una sola operación atómica. "
            "Se espera una lista de objetos que contengan el ID de la relación y el nuevo índice de orden."
        ),
        request=inline_serializer(
            name="ReorderAttributesRequest",
            fields={
                "attributes": inline_serializer(
                    name="AttributeOrderItem",
                    many=True,
                    fields={
                        "id": serializers.UUIDField(
                            help_text="ID de la relación TemplateAttribute"
                        ),
                        "order": serializers.IntegerField(
                            help_text="Nuevo índice de posición (0-N)"
                        ),
                    },
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="ReorderSuccessResponse",
                fields={"message": serializers.CharField()},
            ),
            **error_400("template", action="reorder_attributes", is_detail=True),
            **error_401("template", action="reorder_attributes", is_detail=True),
            **error_403("template", action="reorder_attributes", is_detail=True),
            **error_404("template", action="reorder_attributes", is_detail=True),
        },
    )
    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[IsAuthenticated, IsAdminUser],
        url_path="reorder-attributes"
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

    @extend_schema(
        summary="Listar productos por plantilla",
        description=(
            "Recupera todos los productos activos que utilizan esta plantilla de atributos. "
            "La respuesta está paginada y utiliza el formato simplificado de lista de productos."
        ),
        responses={
            **success_200(ProductListSerializer, many=True),
            **error_401("template", action="products", is_detail=True),
            **error_404("template", action="products", is_detail=True),
        },
    )
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
