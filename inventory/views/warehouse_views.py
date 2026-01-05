from django.db.models import (
    Sum,
    F,
    ExpressionWrapper,
    DecimalField,
)

from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    inline_serializer,
)

from inventory.models import Warehouse, StockMovement
from inventory.permissions import IsCompanyMember, IsAdminOrReadOnly
from inventory.serializers import (
    WarehouseSerializer,
    StockRecordSerializer,
    StockMovementSerializer,
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


@extend_schema(tags=["Warehouse"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(WarehouseSerializer, many=True),
            **error_401("warehouse"),
            **error_403("warehouse"),
            **error_500("warehouse"),
        },
    ),
    create=extend_schema(
        summary="Create",
        request=WarehouseSerializer,
        responses={
            **success_201(WarehouseSerializer),
            **error_400("warehouse"),
            **error_401("warehouse"),
            **error_403("warehouse"),
            **error_500("warehouse"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(WarehouseSerializer),
            **error_401("warehouse", is_detail=True),
            **error_403("warehouse", is_detail=True),
            **error_404("warehouse", is_detail=True),
            **error_500("warehouse", is_detail=True),
        },
    ),
    update=extend_schema(
        summary="Edit (Admin)",
        request=WarehouseSerializer,
        responses={
            **success_200(WarehouseSerializer),
            **error_400("warehouse", is_detail=True),
            **error_401("warehouse", is_detail=True),
            **error_403("warehouse", is_detail=True),
            **error_404("warehouse", is_detail=True),
            **error_500("warehouse", is_detail=True),
        },
    ),
    partial_update=extend_schema(
        summary="Edit partial (Admin)",
        request=WarehouseSerializer,
        responses={
            **success_200(WarehouseSerializer),
            **error_400("warehouse", is_detail=True),
            **error_401("warehouse", is_detail=True),
            **error_403("warehouse", is_detail=True),
            **error_404("warehouse", is_detail=True),
            **error_500("warehouse", is_detail=True),
        },
    ),
    destroy=extend_schema(
        summary="Delete (Admin)",
        responses={
            **success_204(),
            **error_401("warehouse", is_detail=True),
            **error_403("warehouse", is_detail=True),
            **error_404("warehouse", is_detail=True),
            **error_500("warehouse", is_detail=True),
        },
    ),
)
class WarehouseViewSet(viewsets.ModelViewSet):
    """
    Warehouse management.
    Admin can create/update/delete, others can only read.
    """

    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember, IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "address"]
    ordering_fields = ["name", "is_main", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Filter by user's company"""
        return Warehouse.objects.filter(
            company=self.request.user.company, is_active=True
        )

    @extend_schema(
        summary="Inventario del almacén",
        description=(
            "Lista todos los productos que tienen existencias positivas en este almacén específico. "
            "La respuesta está paginada y ordenada alfabéticamente por el nombre del producto."
        ),
        responses={
            **success_200(StockRecordSerializer, many=True),
            **error_401("warehouse", action="inventory", is_detail=True),
            **error_404("warehouse", action="inventory", is_detail=True),
            **error_500("warehouse", action="inventory", is_detail=True),
        },
    )
    @action(detail=True, methods=["get"])
    def inventory(self, request, pk=None):
        """Get complete inventory for this warehouse"""
        warehouse = self.get_object()

        stock_records = (
            warehouse.stock_records.filter(is_active=True, current_quantity__gt=0)
            .select_related("product")
            .order_by("product__name")
        )

        page = self.paginate_queryset(stock_records)
        if page is not None:
            serializer = StockRecordSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StockRecordSerializer(stock_records, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Estadísticas del almacén",
        description=(
            "Calcula métricas clave para el almacén seleccionado, incluyendo el valor total monetario, "
            "conteo de ítems físicos y alertas de stock bajo o agotado."
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="WarehouseStatsResponse",
                    fields={
                        "total_products": serializers.IntegerField(
                            help_text="Productos con stock > 0"
                        ),
                        "total_items": serializers.DecimalField(
                            max_digits=20,
                            decimal_places=2,
                            help_text="Suma total de unidades físicas",
                        ),
                        "total_value": serializers.DecimalField(
                            max_digits=20,
                            decimal_places=2,
                            help_text="Valor total del inventario a precio de costo",
                        ),
                        "low_stock_products": serializers.IntegerField(
                            help_text="Conteo de productos por debajo de su mínimo"
                        ),
                        "out_of_stock_products": serializers.IntegerField(
                            help_text="Conteo de productos con stock en cero"
                        ),
                    },
                )
            ),
            **error_401("warehouse", action="stats", is_detail=True),
            **error_404("warehouse", action="stats", is_detail=True),
            **error_500("warehouse", action="stats", is_detail=True),
        },
    )
    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """Get warehouse statistics"""
        warehouse = self.get_object()

        stock_records = warehouse.stock_records.filter(is_active=True)

        stats = {
            "total_products": stock_records.filter(current_quantity__gt=0).count(),
            "total_items": stock_records.aggregate(total=Sum("current_quantity"))[
                "total"
            ]
            or 0,
            "total_value": stock_records.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("current_quantity") * F("product__cost"),
                        output_field=DecimalField(),
                    )
                )
            )["total"]
            or 0,
            "low_stock_products": stock_records.filter(
                current_quantity__lt=F("product__minimum_stock")
            ).count(),
            "out_of_stock_products": stock_records.filter(current_quantity=0).count(),
        }

        return Response(stats)

    @extend_schema(
        summary="Movimientos recientes del almacén",
        description=(
            "Recupera los últimos 50 movimientos de stock registrados en este almacén. "
            "Incluye información del producto afectado y la cuenta de usuario responsable. "
            "La respuesta está paginada por defecto."
        ),
        responses={
            **success_200(StockMovementSerializer, many=True),
            **error_401("warehouse", action="movements", is_detail=True),
            **error_404("warehouse", action="movements", is_detail=True),
            **error_500("warehouse", action="movements", is_detail=True),
        },
    )
    @action(detail=True, methods=["get"])
    def movements(self, request, pk=None):
        """Get recent movements for this warehouse"""
        warehouse = self.get_object()

        movements = (
            StockMovement.objects.filter(stock_record__warehouse=warehouse)
            .select_related("stock_record__product", "account")
            .order_by("-created_at")[:50]
        )

        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Soft delete"""
        instance = self.get_object()

        # Check if warehouse has stock
        if instance.stock_records.filter(
            is_active=True, current_quantity__gt=0
        ).exists():
            return Response(
                {"error": "Cannot delete warehouse with stock"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
