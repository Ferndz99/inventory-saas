from django.db.models import (
    Sum,
    F,
    ExpressionWrapper,
    DecimalField,
)

from rest_framework import viewsets, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer

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
from inventory.utils import error_401, error_403, error_404, error_500, success_200


@extend_schema(tags=["Company"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(CompanySerializer, many=True),
            **error_401("company"),
            **error_403("company"),
            **error_500("company"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(CompanySerializer),
            **error_401("company", is_detail=True),
            **error_403("company", is_detail=True),
            **error_404("company", is_detail=True),
            **error_500("company", is_detail=True),
        },
    ),
)
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

    @extend_schema(
        summary="Company stats",
        description="get stats ",
        responses={
            **success_200(
                inline_serializer(
                    name="CompanyStatsResponse",
                    fields={
                        "total_products": serializers.IntegerField(),
                        "total_categories": serializers.IntegerField(),
                        "total_warehouses": serializers.IntegerField(),
                        "total_templates": serializers.IntegerField(),
                        "low_stock_products": serializers.IntegerField(),
                        "total_stock_value": serializers.DecimalField(
                            max_digits=12, decimal_places=2
                        ),
                    },
                )
            ),
            **error_401("company", action="stats"),
            **error_403("company", action="stats"),
            **error_500("company", action="stats"),
        },
    )
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
