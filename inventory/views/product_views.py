from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, status, filters, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from django_filters.rest_framework import DjangoFilterBackend

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

    @action(detail=False, methods=["post"])
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

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        """Get products with stock below minimum"""
        products = self.get_queryset().filter(total_stock__lt=F("minimum_stock"))

        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
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

    @action(detail=True, methods=["get"])
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

    @action(detail=True, methods=["get"])
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

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def bulk_create(self, request):
        """
        Bulk create products.
        Useful for importing from Excel.
        """
        products_data = request.data.get("products", [])

        if not products_data:
            raise ValidationError({"error": "products list is required"})

        created_products = []
        errors = []

        with transaction.atomic():
            for index, product_data in enumerate(products_data):
                serializer = ProductSerializer(
                    data=product_data, context={"request": request}
                )

                try:
                    serializer.is_valid(raise_exception=True)
                    product = serializer.save()
                    created_products.append(product)
                except serializers.ValidationError as e:
                    errors.append(
                        {
                            "index": index,
                            "sku": product_data.get("sku"),
                            "errors": e.detail,
                        }
                    )

        return Response(
            {
                "created": len(created_products),
                "errors": errors,
                "products": ProductListSerializer(created_products, many=True).data,
            },
            status=status.HTTP_201_CREATED
            if created_products
            else status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["get"])
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
