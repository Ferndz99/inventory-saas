from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser as DjangoAdmin
from rest_framework.exceptions import ValidationError

from inventory.models import CustomAttribute, GlobalAttribute
from inventory.permissions import IsCompanyMember, IsAdminUser, IsAdminOrReadOnly
from inventory.serializers import GlobalAttributeSerializer, CustomAttributeSerializer

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

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


@extend_schema(tags=["Atributos del Sistema"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(GlobalAttributeSerializer, many=True),
            **error_401("global-attribute"),
            **error_403("global-attribute"),
            **error_500("global-attribute"),
        },
    ),
    create=extend_schema(
        summary="Create (Admin)",
        request=GlobalAttributeSerializer,
        responses={
            **success_201(GlobalAttributeSerializer),
            **error_400("global-attribute"),
            **error_401("global-attribute"),
            **error_403("global-attribute"),
            **error_500("global-attribute"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(GlobalAttributeSerializer),
            **error_401("global-attribute", is_detail=True),
            **error_403("global-attribute", is_detail=True),
            **error_404("global-attribute", is_detail=True),
            **error_500("global-attribute", is_detail=True),
        },
    ),
    update=extend_schema(
        summary="Edit (Admin)",
        request=GlobalAttributeSerializer,
        responses={
            **success_200(GlobalAttributeSerializer),
            **error_400("global-attribute", is_detail=True),
            **error_401("global-attribute", is_detail=True),
            **error_403("global-attribute", is_detail=True),
            **error_404("global-attribute", is_detail=True),
            **error_500("global-attribute", is_detail=True),
        },
    ),
    partial_update=extend_schema(
        summary="Edit partial (Admin)",
        request=GlobalAttributeSerializer,
        responses={
            **success_200(GlobalAttributeSerializer),
            **error_400("global-attribute", is_detail=True),
            **error_401("global-attribute", is_detail=True),
            **error_403("global-attribute", is_detail=True),
            **error_404("global-attribute", is_detail=True),
            **error_500("global-attribute", is_detail=True),
        },
    ),
    destroy=extend_schema(
        summary="Delete (Admin)",
        responses={
            **success_204(),
            **error_401("global-attribute", is_detail=True),
            **error_403("global-attribute", is_detail=True),
            **error_404("global-attribute", is_detail=True),
            **error_500("global-attribute", is_detail=True),
        },
    ),
)
class GlobalAttributeViewSet(viewsets.ModelViewSet):
    """
    Global attributes - read-only for all users.
    These are managed by system admins.
    """

    serializer_class = GlobalAttributeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "data_type"]
    ordering = ["name"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return GlobalAttribute.objects.none()
        return GlobalAttribute.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [DjangoAdmin()]
        return super().get_permissions()


@extend_schema(tags=["Atributos del Sistema"])
@extend_schema_view(
    list=extend_schema(
        summary="List",
        responses={
            **success_200(CustomAttributeSerializer, many=True),
            **error_401("custom-attribute"),
            **error_403("custom-attribute"),
            **error_500("custom-attribute"),
        },
    ),
    create=extend_schema(
        summary="Create (Admin)",
        request=CustomAttributeSerializer,
        responses={
            **success_201(CustomAttributeSerializer),
            **error_400("custom-attribute"),
            **error_401("custom-attribute"),
            **error_403("custom-attribute"),
            **error_500("custom-attribute"),
        },
    ),
    retrieve=extend_schema(
        summary="Retrieve",
        responses={
            **success_200(CustomAttributeSerializer),
            **error_401("custom-attribute", is_detail=True),
            **error_403("custom-attribute", is_detail=True),
            **error_404("custom-attribute", is_detail=True),
            **error_500("custom-attribute", is_detail=True),
        },
    ),
    update=extend_schema(
        summary="Edit (Admin)",
        request=CustomAttributeSerializer,
        responses={
            **success_200(CustomAttributeSerializer),
            **error_400("custom-attribute", is_detail=True),
            **error_401("custom-attribute", is_detail=True),
            **error_403("custom-attribute", is_detail=True),
            **error_404("custom-attribute", is_detail=True),
            **error_500("custom-attribute", is_detail=True),
        },
    ),
    partial_update=extend_schema(
        summary="Edit partial (Admin)",
        request=CustomAttributeSerializer,
        responses={
            **success_200(CustomAttributeSerializer),
            **error_400("custom-attribute", is_detail=True),
            **error_401("custom-attribute", is_detail=True),
            **error_403("custom-attribute", is_detail=True),
            **error_404("custom-attribute", is_detail=True),
            **error_500("custom-attribute", is_detail=True),
        },
    ),
    destroy=extend_schema(
        summary="Delete (Admin)",
        responses={
            **success_204(),
            **error_401("custom-attribute", is_detail=True),
            **error_403("custom-attribute", is_detail=True),
            **error_404("custom-attribute", is_detail=True),
            **error_500("custom-attribute", is_detail=True),
        },
    ),
)
class CustomAttributeViewSet(viewsets.ModelViewSet):
    """
    Custom attributes - company-specific.
    Admin can create/update/delete, others can only read.
    """

    serializer_class = CustomAttributeSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember, IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "data_type", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Filter by user's company"""
        return CustomAttribute.objects.filter(
            company=self.request.user.company, is_active=True
        )

    def destroy(self, request, *args, **kwargs):
        """Soft delete"""
        instance = self.get_object()

        # Check if attribute is used in any template
        if instance.template_attributes.filter(is_active=True).exists():
            raise ValidationError(
                {"error": "Cannot delete attribute that is used in templates"}
            )

        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
