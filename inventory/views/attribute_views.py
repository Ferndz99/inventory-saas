from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from inventory.models import CustomAttribute, GlobalAttribute
from inventory.permissions import IsCompanyMember, IsAdminUser, IsAdminOrReadOnly
from inventory.serializers import GlobalAttributeSerializer, CustomAttributeSerializer


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
        return GlobalAttribute.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update"]:
            return [IsAdminUser()]
        return super().get_permissions()


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
            return Response(
                {"error": "Cannot delete attribute that is used in templates"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
