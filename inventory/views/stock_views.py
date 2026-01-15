from datetime import timedelta

from django.utils import timezone
from django.db.models import (
    Sum,
)

from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    inline_serializer,
    OpenApiParameter,
)
from drf_spectacular.types import OpenApiTypes

from inventory.models import StockRecord, StockMovement
from inventory.permissions import IsCompanyMember, IsAdminUser
from inventory.filters import StockMovementFilter

from inventory.serializers import (
    StockRecordSerializer,
    StockMovementCreateSerializer,
    StockMovementSerializer,
    StockAdjustmentSerializer,
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


@extend_schema(tags=["Stock record"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(StockRecordSerializer, many=True),
            **error_401("stock-record"),
            **error_403("stock-record"),
            **error_500("stock-record"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(StockRecordSerializer),
            **error_401("stock-record", is_detail=True),
            **error_403("stock-record", is_detail=True),
            **error_404("stock-record", is_detail=True),
            **error_500("stock-record", is_detail=True),
        },
    ),
)
class StockRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Stock records - read-only.
    Updated through StockMovements.
    """

    serializer_class = StockRecordSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["product__name", "product__sku", "warehouse__name"]
    ordering_fields = ["current_quantity", "product__name", "warehouse__name"]
    ordering = ["product__name"]

    def get_queryset(self):
        """Filter by user's company"""
        return StockRecord.objects.filter(
            product__company=self.request.user.company, is_active=True
        ).select_related("product", "warehouse")

    @extend_schema(
        summary="Conciliar inventario",
        description=(
            "Audita y corrige discrepancias entre el stock actual y el historial de movimientos. "
            "Recalcula la cantidad actual basándose exclusivamente en la suma de entradas y salidas. "
            "Requiere permisos de administrador."
        ),
        responses={
            200: inline_serializer(
                name="ReconcileResponse",
                fields={
                    "reconciled": serializers.BooleanField(
                        help_text="Indica si se realizaron ajustes"
                    ),
                    "old_quantity": serializers.DecimalField(
                        max_digits=12, decimal_places=2, required=False
                    ),
                    "new_quantity": serializers.DecimalField(
                        max_digits=12, decimal_places=2, required=False
                    ),
                    "difference": serializers.DecimalField(
                        max_digits=12, decimal_places=2, required=False
                    ),
                    "message": serializers.CharField(
                        required=False,
                        help_text="Mensaje informativo si no hubo cambios",
                    ),
                },
            ),
            **error_401("stock-record", action="reconcile", is_detail=True),
            **error_403("stock-record", action="reconcile", is_detail=True),
            **error_404("stock-record", action="reconcile", is_detail=True),
            **error_500("stock-record", action="reconcile", is_detail=True),
        },
    )
    @action(
        detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsAdminUser]
    )
    def reconcile(self, request, pk=None):
        """
        Reconcile stock record with movement history.
        Useful for fixing discrepancies.
        """
        stock_record = self.get_object()

        old_quantity = stock_record.current_quantity
        was_reconciled = stock_record.reconcile()
        new_quantity = stock_record.current_quantity

        if was_reconciled:
            return Response(
                {
                    "reconciled": True,
                    "old_quantity": old_quantity,
                    "new_quantity": new_quantity,
                    "difference": new_quantity - old_quantity,
                }
            )

        return Response(
            {"reconciled": False, "message": "Stock record was already correct"}
        )


@extend_schema(tags=["Stock movement"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(StockMovementSerializer, many=True),
            **error_401("stock-movement"),
            **error_403("stock-movement"),
            **error_500("stock-movement"),
        },
    ),
    create=extend_schema(
        summary="Create (Admin)",
        request=StockMovementCreateSerializer,
        responses={
            **success_201(StockMovementSerializer),
            **error_400("stock-movement"),
            **error_401("stock-movement"),
            **error_403("stock-movement"),
            **error_500("stock-movement"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(StockMovementSerializer),
            **error_401("stock-movement", is_detail=True),
            **error_403("stock-movement", is_detail=True),
            **error_404("stock-movement", is_detail=True),
            **error_500("stock-movement", is_detail=True),
        },
    ),
    update=extend_schema(
        summary="Edit (Admin)",
        request=StockMovementSerializer,
        responses={
            **success_200(StockMovementSerializer),
            **error_400("stock-movement", is_detail=True),
            **error_401("stock-movement", is_detail=True),
            **error_403("stock-movement", is_detail=True),
            **error_404("stock-movement", is_detail=True),
            **error_500("stock-movement", is_detail=True),
        },
    ),
    partial_update=extend_schema(
        summary="Edit partial (Admin)",
        request=StockMovementSerializer,
        responses={
            **success_200(StockMovementSerializer),
            **error_400("stock-movement", is_detail=True),
            **error_401("stock-movement", is_detail=True),
            **error_403("stock-movement", is_detail=True),
            **error_404("stock-movement", is_detail=True),
            **error_500("stock-movement", is_detail=True),
        },
    ),
    destroy=extend_schema(
        summary="Delete (Admin)",
        responses={
            **success_204(),
            **error_401("stock-movement", is_detail=True),
            **error_403("stock-movement", is_detail=True),
            **error_404("stock-movement", is_detail=True),
            **error_500("stock-movement", is_detail=True),
        },
    ),
)
class StockMovementViewSet(viewsets.ModelViewSet):
    """
    Stock movement management.
    Create movements for purchases, sales, adjustments, and transfers.
    """

    permission_classes = [IsAuthenticated, IsCompanyMember]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = StockMovementFilter
    search_fields = [
        "stock_record__product__name",
        "stock_record__product__sku",
        "reference_document",
    ]
    ordering_fields = ["created_at", "movement_type", "quantity"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return StockMovementCreateSerializer
        return StockMovementSerializer

    def get_queryset(self):
        """Filter by user's company"""
        return StockMovement.objects.filter(
            stock_record__product__company=self.request.user.company
        ).select_related(
            "stock_record__product",
            "stock_record__warehouse",
            "account",
            "from_warehouse",
            "to_warehouse",
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        movement = serializer.save()

        read_serializer = StockMovementSerializer(
            movement, context={"request": request}
        )

        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Ajuste manual de stock",
        description=(
            "Establece la cantidad de stock de un producto en un almacén a un valor específico. "
            "A diferencia de una entrada o salida simple, este proceso calcula automáticamente "
            "la diferencia necesaria y genera un movimiento de tipo 'ADJUSTMENT' para auditoría."
        ),
        request=StockAdjustmentSerializer,
        responses={
            201: StockMovementSerializer,
            **error_400("stock-movement", action="adjustment"),
            **error_401("stock-movement", action="adjustment"),
            **error_403("stock-movement", action="adjustment"),
            **error_404("stock-movement", action="adjustment"),
            **error_500("stock-movement", action="adjustment"),
        },
    )
    @action(detail=False, methods=["post"])
    def adjustment(self, request):
        """
        Create stock adjustment.
        Sets stock to a specific quantity.
        """
        serializer = StockAdjustmentSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        movement = serializer.save()

        return Response(
            StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Resumen ejecutivo de movimientos",
        description=(
            "Calcula métricas agregadas de movimientos de stock para un rango de fechas. "
            "Incluye totales por tipo (IN/OUT/TRANSFER), por motivo y sumatorias de unidades físicas."
        ),
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha inicio (YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="date_to",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha fin (YYYY-MM-DD)",
            ),
        ],
        responses={
            **success_200(
                inline_serializer(
                    name="MovementSummaryResponse",
                    fields={
                        "total_movements": serializers.IntegerField(),
                        "total_in": serializers.DecimalField(
                            max_digits=12, decimal_places=2
                        ),
                        "total_out": serializers.DecimalField(
                            max_digits=12, decimal_places=2
                        ),
                        "total_transfers": serializers.IntegerField(),
                        "by_type": serializers.DictField(
                            child=serializers.IntegerField(),
                            help_text="Conteo de movimientos agrupados por tipo (IN, OUT, TRANSFER, ADJUSTMENT)",
                        ),
                        "by_reason": serializers.DictField(
                            child=serializers.IntegerField(),
                            help_text="Conteo de movimientos agrupados por motivo (PURCHASE, SALE, RETURN, etc.)",
                        ),
                    },
                )
            ),
            **error_401("stock-movement", action="summary"),
            **error_403("stock-movement", action="summary"),
            **error_500("stock-movement", action="summary"),
        },
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        Get movement summary for a date range.
        Useful for reports.
        """
        # Get date range from query params
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        movements = self.get_queryset()

        if date_from:
            movements = movements.filter(created_at__gte=date_from)
        if date_to:
            movements = movements.filter(created_at__lte=date_to)

        summary = {
            "total_movements": movements.count(),
            "by_type": {},
            "by_reason": {},
            "total_in": movements.filter(movement_type="IN").aggregate(
                total=Sum("quantity")
            )["total"]
            or 0,
            "total_out": movements.filter(movement_type="OUT").aggregate(
                total=Sum("quantity")
            )["total"]
            or 0,
            "total_transfers": movements.filter(movement_type="TRANSFER").count(),
        }

        # Group by type
        for choice in StockMovement.MOVEMENT_TYPE_CHOICES:
            movement_type = choice[0]
            count = movements.filter(movement_type=movement_type).count()
            summary["by_type"][movement_type] = count

        # Group by reason
        for choice in StockMovement.REASON_CHOICES:
            reason = choice[0]
            count = movements.filter(reason=reason).count()
            summary["by_reason"][reason] = count

        return Response(summary)

    @extend_schema(
        summary="Movimientos recientes (últimas horas)",
        description=(
            "Obtiene un listado de los movimientos realizados en un periodo reciente de tiempo. "
            "Por defecto recupera la actividad de las últimas 24 horas y limita el resultado a "
            "los 50 registros más recientes para optimizar el rendimiento."
        ),
        parameters=[
            OpenApiParameter(
                name="hours",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Número de horas hacia atrás desde el momento actual",
                default=24,
            ),
        ],
        responses={
            **success_200(StockMovementSerializer, many=True),
            **error_401("stock-movement", action="recent"),
            **error_403("stock-movement", action="recent"),
            **error_500("stock-movement", action="recent"),
        },
    )
    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recent movements (last 24 hours by default)"""
        hours = int(request.query_params.get("hours", 24))
        cutoff = timezone.now() - timedelta(hours=hours)

        movements = self.get_queryset().filter(created_at__gte=cutoff)[:50]

        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Movements cannot be deleted, only marked as inactive.
        This maintains audit trail.
        """
        return Response(
            {
                "error": "Stock movements cannot be deleted. Please create an adjustment if needed."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
