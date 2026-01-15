from django.db import transaction
from django.db.models import F, Sum, Q
from django.utils import timezone

from rest_framework import viewsets, status, filters, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiParameter,
)
from drf_spectacular.types import OpenApiTypes

from inventory.filters import ProductFilter
from inventory.models import Product, StockMovement
from inventory.permissions import IsCompanyMember, IsAdminUser, IsAdminOrReadOnly

from inventory.serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductSerializer,
    StockRecordSerializer,
    StockMovementSerializer,
)
from inventory.utils import (
    error_400,
    error_401,
    error_403,
    error_404,
    error_500,
    success_200,
    success_201,
    success_204,
)


@extend_schema(tags=["Products"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(ProductListSerializer, many=True),
            **error_401("product"),
            **error_403("product"),
            **error_500("product"),
        },
    ),
    create=extend_schema(
        summary="Create (Admin)",
        request=ProductSerializer,
        responses={
            **success_201(ProductSerializer),
            **error_400("product"),
            **error_401("product"),
            **error_403("product"),
            **error_500("product"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(ProductDetailSerializer),
            **error_401("product", is_detail=True),
            **error_403("product", is_detail=True),
            **error_404("product", is_detail=True),
            **error_500("product", is_detail=True),
        },
    ),
    update=extend_schema(
        summary="Edit",
        request=ProductSerializer,
        responses={
            **success_200(ProductSerializer),
            **error_401("product", is_detail=True),
            **error_403("product", is_detail=True),
            **error_404("product", is_detail=True),
            **error_500("product", is_detail=True),
        },
    ),
    partial_update=extend_schema(
        summary="Edit partial (Admin)",
        request=ProductSerializer,
        responses={
            **success_200(ProductSerializer),
            **error_400("product", is_detail=True),
            **error_401("product", is_detail=True),
            **error_403("product", is_detail=True),
            **error_404("product", is_detail=True),
            **error_500("product", is_detail=True),
        },
    ),
    destroy=extend_schema(
        summary="Delete (Admin)",
        responses={
            **success_204(),
            **error_401("product", is_detail=True),
            **error_403("product", is_detail=True),
            **error_404("product", is_detail=True),
            **error_500("product", is_detail=True),
        },
    ),
)
class ProductViewSet(viewsets.ModelViewSet):
    """
    Product management with dynamic specifications.
    Admin can create/update/delete, others can only read.
    """

    permission_classes = [IsAuthenticated, IsCompanyMember, IsAdminOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ProductFilter
    search_fields = ["name", "sku", "barcode"]
    ordering_fields = ["name", "sku", "price", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductSerializer

    def get_queryset(self):
        """Filter by user's company"""
        queryset = Product.objects.filter(
            company=self.request.user.company, is_active=True
        ).select_related("category", "template", "company")

        # Annotate with stock info
        queryset = queryset.annotate(total_stock=Sum("stock_records__current_quantity"))

        return queryset

    @extend_schema(
        summary="Validar especificaciones",
        description="Permite validar la estructura de las especificaciones contra un template sin crear el producto.",
        request=inline_serializer(
            name="ValidateSpecsRequest",
            fields={
                "template": serializers.UUIDField(),
                "specifications": serializers.JSONField(),
            },
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="ValidateSpecsResponse",
                    fields={
                        "valid": serializers.BooleanField(),
                        "message": serializers.CharField(),
                        "validated_specifications": serializers.DictField(
                            child=serializers.JSONField(),
                            help_text="Diccionario dinámico con formato { 'slug_atributo': 'valor_validado' }",
                        ),
                    },
                ),
                description="La validación se ejecutó (puede ser válida o inválida según el campo 'valid')",
            ),
            **error_400("product", action="validate_specifications"),
            **error_401("product", action="validate_specifications"),
            **error_403("product", action="validate_specifications"),
            **error_500("product", action="validate_specifications"),
        },
    )
    @action(detail=False, methods=["post"], url_path="validate-specifications")
    def validate_specifications(self, request):
        """
        Validate specifications without creating a product.
        Useful for frontend real-time validation.
        """
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            return Response(
                {
                    "valid": True,
                    "message": "Specifications are valid",
                    "validated_specifications": serializer.validated_data.get(
                        "specifications", {}
                    ),
                }
            )
        except serializers.ValidationError as e:
            return Response(
                {"valid": False, "errors": e.detail}, status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Productos con bajo stock",
        description=(
            "Obtiene la lista de productos cuyo stock total actual es estrictamente "
            "menor al stock mínimo configurado en su ficha."
        ),
        responses={
            **success_200(ProductListSerializer, many=True),
            **error_401("product", action="low_stock"),
            **error_403("product", action="low_stock"),
            **error_500("product", action="low_stock"),
        },
    )
    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        """Get products with stock below minimum"""
        products = self.get_queryset().filter(total_stock__lt=F("minimum_stock"))

        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Productos agotados",
        description="Obtiene la lista de productos cuyo stock total es cero o nulo (sin registros de stock).",
        responses={
            **success_200(ProductListSerializer, many=True),
            **error_401("product", action="out_of_stock"),
            **error_403("product", action="out_of_stock"),
            **error_500("product", action="out_of_stock"),
        },
    )
    @action(detail=False, methods=["get"], url_path="out-of-stock")
    def out_of_stock(self, request):
        """Get products with zero stock"""
        products = self.get_queryset().filter(
            Q(total_stock=0) | Q(total_stock__isnull=True)
        )

        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Detalle de stock y movimientos",
        description=(
            "Obtiene información consolidada del stock por almacén y los últimos 10 "
            "movimientos de inventario para un producto específico."
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="ProductStockDetailsResponse",
                    fields={
                        "stock_by_warehouse": StockRecordSerializer(many=True),
                        "recent_movements": StockMovementSerializer(many=True),
                        "total_stock": serializers.DecimalField(
                            max_digits=12, decimal_places=2
                        ),
                        "is_below_minimum": serializers.BooleanField(),
                    },
                )
            ),
            **error_401("product", action="stock_details", is_detail=True),
            **error_404("product", action="stock_details", is_detail=True),
            **error_500("product", action="stock_details", is_detail=True),
        },
    )
    @action(detail=True, methods=["get"], url_path="stock-details")
    def stock_details(self, request, pk=None):
        """Get detailed stock information for a product"""
        product = self.get_object()

        stock_records = product.stock_records.filter(is_active=True).select_related(
            "warehouse"
        )

        recent_movements = (
            StockMovement.objects.filter(stock_record__product=product)
            .select_related("stock_record__warehouse", "account")
            .order_by("-created_at")[:10]
        )

        return Response(
            {
                # "product": ProductDetailSerializer(product).data,
                "stock_by_warehouse": StockRecordSerializer(
                    stock_records, many=True
                ).data,
                "recent_movements": StockMovementSerializer(
                    recent_movements, many=True
                ).data,
                "total_stock": product.get_total_stock(),
                "is_below_minimum": product.is_below_minimum(),
            }
        )

    @extend_schema(
        summary="Historial completo de movimientos",
        description=(
            "Obtiene el historial cronológico de todos los movimientos de stock "
            "(entradas, salidas, transferencias) de un producto específico."
        ),
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filtrar movimientos desde esta fecha (YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="date_to",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filtrar movimientos hasta esta fecha (YYYY-MM-DD)",
            ),
        ],
        responses={
            **success_200(StockMovementSerializer, many=True),
            **error_401("product", action="movement_history", is_detail=True),
            **error_404("product", action="movement_history", is_detail=True),
            **error_500("product", action="movement_history", is_detail=True),
        },
    )
    @action(detail=True, methods=["get"], url_path="movement-history")
    def movement_history(self, request, pk=None):
        """Get complete movement history for a product"""
        product = self.get_object()

        movements = (
            StockMovement.objects.filter(stock_record__product=product)
            .select_related(
                "stock_record__warehouse", "account", "from_warehouse", "to_warehouse"
            )
            .order_by("-created_at")
        )

        # Apply date filters if provided
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if date_from:
            movements = movements.filter(created_at__gte=date_from)
        if date_to:
            movements = movements.filter(created_at__lte=date_to)

        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Creación masiva de productos",
        description="Crea múltiples productos a la vez. Si todos fallan, devuelve un error RFC 9457.",
        request=ProductListSerializer(many=True),
        responses={
            201: inline_serializer(
                name="BulkCreateSuccess",
                fields={
                    "created": serializers.IntegerField(),
                    "products": ProductListSerializer(many=True),
                },
            ),
            **error_400("product", action="bulk_create"),
            **error_401("product", action="bulk_create"),
            **error_403("product", action="bulk_create"),
            **error_500("product", action="bulk_create"),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsAdminUser],
        url_path="bulk-create",
    )
    def bulk_create(self, request):
        """
        Bulk create products.
        Useful for importing from Excel.
        """
        serializer = self.get_serializer(data=request.data, many=True)

        serializer.is_valid(raise_exception=True)

        created_products = serializer.save()

        if not created_products:
            raise ValidationError(
                detail="No products could be created with the provided data.",
                code="empty_bulk",
            )

        return Response(
            {
                "created": len(created_products),
                "products": ProductListSerializer(created_products, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    # products_data = request.data.get("products", [])

    # if not products_data:
    #     raise ValidationError({"error": "products list is required"})

    # created_products = []
    # errors = []

    # with transaction.atomic():
    #     for index, product_data in enumerate(products_data):
    #         serializer = ProductSerializer(
    #             data=product_data, context={"request": request}
    #         )

    #         try:
    #             serializer.is_valid(raise_exception=True)
    #             product = serializer.save()
    #             created_products.append(product)
    #         except serializers.ValidationError as e:
    #             errors.append(
    #                 {
    #                     "index": index,
    #                     "sku": product_data.get("sku"),
    #                     "errors": e.detail,
    #                 }
    #             )

    # return Response(
    #     {
    #         "created": len(created_products),
    #         "errors": errors,
    #         "products": ProductListSerializer(created_products, many=True).data,
    #     },
    #     status=status.HTTP_201_CREATED
    #     if created_products
    #     else status.HTTP_400_BAD_REQUEST,
    # )

    @extend_schema(
        summary="Exportar productos",
        description=(
            "Genera una exportación completa de los productos en formato JSON, "
            "incluyendo detalles técnicos y metadatos de la exportación."
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="ProductExportResponse",
                    fields={
                        "count": serializers.IntegerField(),
                        "exported_at": serializers.DateTimeField(),
                        "products": ProductDetailSerializer(many=True),
                    },
                ),
                description="Exportación generada exitosamente",
            ),
            **error_401("product", action="export"),
            **error_403("product", action="export"),
            **error_500("product", action="export"),
        },
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """
        Export products to JSON.
        Can be imported later or converted to Excel.
        """
        products = self.get_queryset()
        serializer = ProductDetailSerializer(products, many=True)

        return Response(
            {
                "count": products.count(),
                "exported_at": timezone.now(),
                "products": serializer.data,
            }
        )

    def destroy(self, request, *args, **kwargs):
        """Soft delete"""
        instance = self.get_object()

        # Check if product has stock
        if instance.get_total_stock() > 0:
            return Response(
                {
                    "error": "Cannot delete product with stock. Please adjust stock to zero first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
