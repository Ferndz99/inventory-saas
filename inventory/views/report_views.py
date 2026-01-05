from django.utils import timezone
from django.db.models import Q, Sum, F, Count, ExpressionWrapper, DecimalField, QuerySet

from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from inventory.models import Category, StockMovement, StockRecord, Product
from inventory.permissions import IsCompanyMember
from inventory.serializers import ProductListSerializer
from inventory.utils import error_401, error_403, error_500, success_200


class ReportViewSet(viewsets.ViewSet):
    """
    Various reports for the inventory system.
    """

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @extend_schema(
        tags=["Reports"],
        summary="Valuación de inventario",
        description=(
            "Calcula el valor total del inventario a precio de costo, "
            "desglosado por almacén y consolidado de forma global."
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="InventoryValuationResponse",
                    fields={
                        "total_value": serializers.DecimalField(
                            max_digits=20, decimal_places=2
                        ),
                        "total_items": serializers.DecimalField(
                            max_digits=20, decimal_places=2
                        ),
                        "generated_at": serializers.DateTimeField(),
                        "by_warehouse": serializers.DictField(
                            child=inline_serializer(
                                name="WarehouseValuation",
                                fields={
                                    "warehouse_id": serializers.IntegerField(),
                                    "products": serializers.IntegerField(),
                                    "total_items": serializers.DecimalField(
                                        max_digits=20, decimal_places=2
                                    ),
                                    "total_value": serializers.DecimalField(
                                        max_digits=20, decimal_places=2
                                    ),
                                },
                            ),
                            help_text="Mapa donde la llave es el nombre del almacén",
                        ),
                    },
                )
            ),
            **error_401("report", action="inventory_valuation"),
            **error_403("report", action="inventory_valuation"),
            **error_500("report", action="inventory_valuation"),
        },
    )
    @action(detail=False, methods=["get"], url_path="inventory-valuation")
    def inventory_valuation(self, request):
        """
        Get current inventory valuation.
        Shows total value of stock at cost.
        """
        company = request.user.company

        stock_records = (
            StockRecord.objects.filter(product__company=company, is_active=True)
            .select_related("product", "warehouse")
            .annotate(
                value=ExpressionWrapper(
                    F("current_quantity") * F("product__cost"),
                    output_field=DecimalField(),
                )
            )
        )

        by_warehouse = {}
        total_value = 0
        total_items = 0

        for sr in stock_records:
            warehouse_name = sr.warehouse.name

            if warehouse_name not in by_warehouse:
                by_warehouse[warehouse_name] = {
                    "warehouse_id": sr.warehouse.id,
                    "products": 0,
                    "total_items": 0,
                    "total_value": 0,
                }

            by_warehouse[warehouse_name]["products"] += 1
            by_warehouse[warehouse_name]["total_items"] += sr.current_quantity
            by_warehouse[warehouse_name]["total_value"] += sr.value or 0

            total_value += sr.value or 0
            total_items += sr.current_quantity

        return Response(
            {
                "total_value": total_value,
                "total_items": total_items,
                "by_warehouse": by_warehouse,
                "generated_at": timezone.now(),
            }
        )

    @extend_schema(
        tags=["Reports"],
        summary="Alertas de inventario",
        description=(
            "Consolida productos en estado crítico: aquellos con stock bajo el mínimo "
            "y aquellos que están totalmente agotados."
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="StockAlertsResponse",
                    fields={
                        "low_stock": inline_serializer(
                            name="LowStockAlert",
                            fields={
                                "count": serializers.IntegerField(),
                                "products": ProductListSerializer(many=True),
                            },
                        ),
                        "out_of_stock": inline_serializer(
                            name="OutOfStockAlert",
                            fields={
                                "count": serializers.IntegerField(),
                                "products": ProductListSerializer(many=True),
                            },
                        ),
                        "generated_at": serializers.DateTimeField(),
                    },
                ),
                description="Resumen de alertas generado exitosamente",
            ),
            **error_401("report", action="stock_alerts"),
            **error_403("report", action="stock_alerts"),
            **error_500("report", action="stock_alerts"),
        },
    )
    @action(detail=False, methods=["get"], url_path="stock-alerts")
    def stock_alerts(self, request):
        """
        Get all stock alerts (low stock, out of stock).
        """
        company = request.user.company

        # Low stock products
        low_stock = (
            Product.objects.filter(company=company, is_active=True)
            .annotate(total_stock=Sum("stock_records__current_quantity"))
            .filter(total_stock__lt=F("minimum_stock"), total_stock__gt=0)
        )

        # Out of stock products
        out_of_stock = (
            Product.objects.filter(company=company, is_active=True)
            .annotate(total_stock=Sum("stock_records__current_quantity"))
            .filter(Q(total_stock=0) | Q(total_stock__isnull=True))
        )

        return Response(
            {
                "low_stock": {
                    "count": low_stock.count(),
                    "products": ProductListSerializer(low_stock, many=True).data,
                },
                "out_of_stock": {
                    "count": out_of_stock.count(),
                    "products": ProductListSerializer(out_of_stock, many=True).data,
                },
                "generated_at": timezone.now(),
            }
        )

    @extend_schema(
        tags=["Reports"],
        summary="Reporte analítico de movimientos",
        description=(
            "Genera estadísticas agregadas de los movimientos de inventario en un rango de fechas, "
            "desglosados por tipo de movimiento, motivo y los productos con mayor actividad."
        ),
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha de inicio para el reporte (YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="date_to",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha de fin para el reporte (YYYY-MM-DD)",
            ),
        ],
        responses={
            **success_200(
                inline_serializer(
                    name="MovementReportResponse",
                    fields={
                        "date_from": serializers.CharField(allow_null=True),
                        "date_to": serializers.CharField(allow_null=True),
                        "total_movements": serializers.IntegerField(),
                        "by_type": inline_serializer(
                            name="MovementsByType",
                            many=True,
                            fields={
                                "movement_type": serializers.CharField(),
                                "count": serializers.IntegerField(),
                                "total_quantity": serializers.DecimalField(
                                    max_digits=12, decimal_places=2
                                ),
                            },
                        ),
                        "by_reason": inline_serializer(
                            name="MovementsByReason",
                            many=True,
                            fields={
                                "reason": serializers.CharField(),
                                "count": serializers.IntegerField(),
                                "total_quantity": serializers.DecimalField(
                                    max_digits=12, decimal_places=2
                                ),
                            },
                        ),
                        "top_products": inline_serializer(
                            name="TopProductsMovement",
                            many=True,
                            fields={
                                "product_id": serializers.UUIDField(),
                                "product_name": serializers.CharField(),
                                "product_sku": serializers.CharField(),
                                "total_movements": serializers.IntegerField(),
                                "total_quantity": serializers.DecimalField(
                                    max_digits=12, decimal_places=2
                                ),
                            },
                        ),
                        "generated_at": serializers.DateTimeField(),
                    },
                ),
                description="Reporte generado exitosamente",
            ),
            **error_401("report", action="movement_report"),
            **error_403("report", action="movement_report"),
            **error_500("report", action="movement_report"),
        },
    )
    @action(detail=False, methods=["get"], url_path="movement-report")
    def movement_report(self, request):
        """
        Movement report for a date range.
        Shows all movements grouped by type and reason.
        """
        company = request.user.company
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        movements = StockMovement.objects.filter(stock_record__product__company=company)

        if date_from:
            movements = movements.filter(created_at__gte=date_from)
        if date_to:
            movements = movements.filter(created_at__lte=date_to)

        # Aggregate by movement type
        by_type = movements.values("movement_type").annotate(
            count=Count("id"), total_quantity=Sum("quantity")
        )

        # Aggregate by reason
        by_reason = movements.values("reason").annotate(
            count=Count("id"), total_quantity=Sum("quantity")
        )

        # Top products by movement
        top_products = (
            movements.values(
                product_id=F("stock_record__product__id"),
                product_name=F("stock_record__product__name"),
                product_sku=F("stock_record__product__sku"),
            )
            .annotate(total_movements=Count("id"), total_quantity=Sum("quantity"))
            .order_by("-total_movements")[:10]
        )

        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "total_movements": movements.count(),
                "by_type": list(by_type),
                "by_reason": list(by_reason),
                "top_products": list(top_products),
                "generated_at": timezone.now(),
            }
        )

    @extend_schema(
        tags=["Reports"],
        summary="Análisis por categoría",
        description=(
            "Genera un desglose detallado del inventario agrupado por categorías, "
            "mostrando el conteo de productos, stock físico total y la valuación monetaria "
            "ordenada de mayor a menor valor."
        ),
        responses={
            **success_200(
                inline_serializer(
                    name="CategoryAnalysisResponse",
                    fields={
                        "categories": inline_serializer(
                            name="CategoryAnalysisItem",
                            many=True,
                            fields={
                                "id": serializers.IntegerField(),
                                "name": serializers.CharField(),
                                "total_products": serializers.IntegerField(),
                                "total_stock": serializers.DecimalField(
                                    max_digits=12, decimal_places=2
                                ),
                                "total_value": serializers.DecimalField(
                                    max_digits=20, decimal_places=2
                                ),
                            },
                        ),
                        "generated_at": serializers.DateTimeField(),
                    },
                ),
                description="Análisis de categorías generado exitosamente",
            ),
            **error_401("report", action="category_analysis"),
            **error_403("report", action="category_analysis"),
            **error_500("report", action="category_analysis"),
        },
    )
    @action(detail=False, methods=["get"], url_path="category-analysis")
    def category_analysis(self, request):
        """
        Analysis by category.
        Shows stock and value by category.
        """
        company = request.user.company

        categories: QuerySet[Category] = (
            Category.objects.filter(company=company, is_active=True)
            .annotate(
                total_products=Count("products", filter=Q(products__is_active=True)),
                total_stock=Sum("products__stock_records__current_quantity"),
                total_value=Sum(
                    ExpressionWrapper(
                        F("products__stock_records__current_quantity")
                        * F("products__cost"),
                        output_field=DecimalField(),
                    )
                ),
            )
            .order_by("-total_value")
        )

        return Response(
            {
                "categories": [
                    {
                        "id": cat.id,
                        "name": cat.name,
                        "total_products": cat.total_products or 0,
                        "total_stock": cat.total_stock or 0,
                        "total_value": cat.total_value or 0,
                    }
                    for cat in categories
                ],
                "generated_at": timezone.now(),
            }
        )

    @extend_schema(
        tags=["Reports"],
        summary="Ranking de productos (Top)",
        description=(
            "Obtiene los productos líderes según diferentes métricas: valor de inventario, "
            "cantidad de stock físico o precio de venta."
        ),
        parameters=[
            OpenApiParameter(
                name="metric",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Criterio de ordenamiento para el ranking",
                enum=["stock_value", "stock_quantity", "price"],
                default="stock_value",
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Cantidad de productos a retornar",
                default=10,
            ),
        ],
        responses={
            **success_200(
                inline_serializer(
                    name="TopProductsResponse",
                    fields={
                        "metric": serializers.CharField(),
                        "limit": serializers.IntegerField(),
                        "products": ProductListSerializer(many=True),
                        "generated_at": serializers.DateTimeField(),
                    },
                ),
                description="Ranking generado exitosamente",
            ),
            **error_401("report", action="top_products"),
            **error_403("report", action="top_products"),
            **error_500("report", action="top_products"),
        },
    )
    @action(detail=False, methods=["get"], url_path="top-products")
    def top_products(self, request):
        """
        Top products by different criteria.
        """
        company = request.user.company
        metric = request.query_params.get("metric", "stock_value")
        limit = int(request.query_params.get("limit", 10))

        products = Product.objects.filter(company=company, is_active=True).annotate(
            total_stock=Sum("stock_records__current_quantity"),
            stock_value=Sum(
                ExpressionWrapper(
                    F("stock_records__current_quantity") * F("cost"),
                    output_field=DecimalField(),
                )
            ),
        )

        # Order by metric
        if metric == "stock_value":
            products = products.order_by("-stock_value")
        elif metric == "stock_quantity":
            products = products.order_by("-total_stock")
        elif metric == "price":
            products = products.order_by("-price")

        products = products[:limit]

        return Response(
            {
                "metric": metric,
                "limit": limit,
                "products": ProductListSerializer(products, many=True).data,
                "generated_at": timezone.now(),
            }
        )
