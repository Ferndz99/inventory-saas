from django.db.models import (
    Q,
    Count,
)

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from inventory.models import Category
from inventory.serializers import CategorySerializer, ProductListSerializer
from inventory.permissions import IsCompanyMember, IsAdminOrReadOnly

from drf_spectacular.utils import extend_schema, extend_schema_view

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


@extend_schema(tags=["Categorias del Sistema"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(CategorySerializer, many=True),
            **error_401("category"),
            **error_403("category"),
            **error_500("category"),
        },
    ),
    create=extend_schema(
        summary="Create (Admin)",
        request=CategorySerializer,
        responses={
            **success_201(CategorySerializer),
            **error_400("category"),
            **error_401("category"),
            **error_403("category"),
            **error_500("category"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(CategorySerializer),
            **error_401("category", is_detail=True),
            **error_403("category", is_detail=True),
            **error_404("category", is_detail=True),
            **error_500("category", is_detail=True),
        },
    ),
    update=extend_schema(
        summary="Edit (Admin)",
        request=CategorySerializer,
        responses={
            **success_200(CategorySerializer),
            **error_400("category", is_detail=True),
            **error_401("category", is_detail=True),
            **error_403("category", is_detail=True),
            **error_404("category", is_detail=True),
            **error_500("category", is_detail=True),
        },
    ),
    partial_update=extend_schema(
        summary="Edit partial (Admin)",
        request=CategorySerializer,
        responses={
            **success_200(CategorySerializer),
            **error_400("category", is_detail=True),
            **error_401("category", is_detail=True),
            **error_403("category", is_detail=True),
            **error_404("category", is_detail=True),
            **error_500("category", is_detail=True),
        },
    ),
    destroy=extend_schema(
        summary="Delete (Admin)",
        responses={
            **success_204(),
            **error_401("category", is_detail=True),
            **error_403("category", is_detail=True),
            **error_404("category", is_detail=True),
            **error_500("category", is_detail=True),
        },
    ),
)
class CategoryViewSet(viewsets.ModelViewSet):
    """
    Category management.
    Admin can create/update/delete, others can only read.
    """

    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsCompanyMember, IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Filter by user's company"""
        return Category.objects.filter(
            company=self.request.user.company, is_active=True
        ).annotate(product_count=Count("products", filter=Q(products__is_active=True)))

    @extend_schema(
        summary="Listar productos por categoría",
        description="Obtiene todos los productos activos asociados a una categoría específica con paginación.",
        responses={
            **success_200(ProductListSerializer, many=True),
            **error_401("category", action="products", is_detail=True),
            **error_403("category", action="products", is_detail=True),
            **error_404("category", action="products", is_detail=True),
            **error_500("category", action="products", is_detail=True),
        },
    )
    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Get all products in this category"""
        category = self.get_object()
        products = category.products.filter(is_active=True)

        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Soft delete - set is_active to False"""
        instance = self.get_object()

        # Check if category has active products
        if instance.products.filter(is_active=True).exists():
            return Response(
                {"error": "Cannot delete category with active products"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
