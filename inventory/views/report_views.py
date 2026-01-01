from django.utils import timezone
from django.db.models import Q, Sum, F, Count, ExpressionWrapper, DecimalField, QuerySet

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from inventory.models import Category, StockMovement, StockRecord, Product
from inventory.permissions import IsCompanyMember
from inventory.serializers import ProductListSerializer



class ReportViewSet(viewsets.ViewSet):
    """
    Various reports for the inventory system.
    """

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @action(detail=False, methods=["get"])
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

    @action(detail=False, methods=["get"])
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

    @action(detail=False, methods=["get"])
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

    @action(detail=False, methods=["get"])
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

    @action(detail=False, methods=["get"])
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
