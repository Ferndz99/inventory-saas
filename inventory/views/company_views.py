from django.db.models import (
    Sum,
    F,
    ExpressionWrapper,
    DecimalField,
)

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action


from inventory.models import (
    Category,
    Company,
    Product,
    StockRecord,
    Template,
    Warehouse,
)
from inventory.serializers import CompanySerializer
from inventory.permissions import IsCompanyMember


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Company viewset - read-only for users.
    Users can only see their own company.
    """

    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get_queryset(self):
        """Users can only see their own company"""
        if hasattr(self.request.user, "company"):
            return Company.objects.filter(id=self.request.user.company.id)
        return Company.objects.none()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get company statistics"""
        company = request.user.company

        stats = {
            "total_products": Product.objects.filter(
                company=company, is_active=True
            ).count(),
            "total_categories": Category.objects.filter(
                company=company, is_active=True
            ).count(),
            "total_warehouses": Warehouse.objects.filter(
                company=company, is_active=True
            ).count(),
            "total_templates": Template.objects.filter(
                company=company, is_active=True
            ).count(),
            "low_stock_products": Product.objects.filter(
                company=company, is_active=True
            )
            .annotate(total_stock=Sum("stock_records__current_quantity"))
            .filter(total_stock__lt=F("minimum_stock"))
            .count(),
            "total_stock_value": StockRecord.objects.filter(
                product__company=company, is_active=True
            ).aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("current_quantity") * F("product__cost"),
                        output_field=DecimalField(),
                    )
                )
            )["total"]
            or 0,
        }

        return Response(stats)
