from django.db.models import (
    Sum,
    F,
    ExpressionWrapper,
    DecimalField,
)

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from inventory.models import Warehouse, StockMovement
from inventory.permissions import IsCompanyMember, IsAdminOrReadOnly
from inventory.serializers import (
    WarehouseSerializer,
    StockRecordSerializer,
    StockMovementSerializer,
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
