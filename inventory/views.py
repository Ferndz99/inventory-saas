from django.db.models import (
    Q,
    Sum,
    F,
    Count,
    Avg,
    Max,
    Min,
    ExpressionWrapper,
    DecimalField,
)
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError


from inventory.models import (
    Company,
    Category,
    GlobalAttribute,
    CustomAttribute,
    Template,
    TemplateAttribute,
    Product,
    Warehouse,
    StockRecord,
    StockMovement,
)
from inventory.serializers import (
    CompanySerializer,
    CategorySerializer,
    GlobalAttributeSerializer,
    CustomAttributeSerializer,
    TemplateSerializer,
    TemplateDetailSerializer,
    TemplateAttributeSerializer,
    TemplateAttributeCreateSerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    WarehouseSerializer,
    StockRecordSerializer,
    StockMovementSerializer,
    StockMovementCreateSerializer,
    StockAdjustmentSerializer,
)
from inventory.permissions import IsCompanyMember, IsAdminUser, IsAdminOrReadOnly
from inventory.filters import ProductFilter, StockMovementFilter


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def setup_company(request):
    """
    Create company and assign user as admin.
    Called after user registers and optionally pays.
    """
    user = request.user

    # Validar que el usuario no tenga empresa ya
    if user.has_company:
        return Response(
            {"error": "User already belongs to a company"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_name = request.data.get("company_name")
    company_rut = request.data.get("company_rut")

    if not company_name or not company_rut:
        return Response(
            {"error": "company_name and company_rut are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            # 1. Crear empresa
            company = Company.objects.create(name=company_name, rut=company_rut)

            # 2. Asignar usuario a empresa como admin
            user.company = company
            user.role = "admin"
            user.save()

            # 3. Crear bodega principal
            warehouse = Warehouse.objects.create(
                name="Bodega Principal", company=company, is_main=True
            )

            # 4. Crear categoría y plantilla por defecto (opcional)
            from inventory.models import Category, Template

            default_category = Category.objects.create(name="General", company=company)

            default_template = Template.objects.create(
                name="Plantilla Básica",
                description="Plantilla inicial para productos",
                company=company,
            )

            return Response(
                {
                    "company": {
                        "id": company.id,
                        "name": company.name,
                        "rut": company.rut,
                    },
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "company": company.id,
                        "role": user.role,
                    },
                    "warehouse": {"id": warehouse.id, "name": warehouse.name},
                    "defaults": {
                        "category": default_category.id,
                        "template": default_template.id,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def onboarding_progress(request):
    """
    Get onboarding progress for current user's company.
    """
    user = request.user

    if not user.has_company:
        return Response(
            {
                "completed": 0,
                "has_company": False,
                "message": "Please complete company setup first",
            }
        )

    company = user.company

    # Calcular progreso
    steps = {
        "has_categories": company.categories.filter(is_active=True).exists(),
        "has_templates": company.templates.filter(is_active=True).exists(),
        "has_products": company.products.filter(is_active=True).exists(),
        "has_stock": company.products.filter(
            stock_records__current_quantity__gt=0
        ).exists(),
        "has_team": company.accounts.filter(is_active=True).count() > 1,
    }

    completed_steps = sum(steps.values())
    total_steps = len(steps)
    progress = (completed_steps / total_steps) * 100

    return Response(
        {
            "completed": progress,
            "has_company": True,
            "company_id": company.id,
            "steps": {
                "create_category": steps["has_categories"],
                "create_template": steps["has_templates"],
                "create_product": steps["has_products"],
                "add_stock": steps["has_stock"],
                "invite_team": steps["has_team"],
            },
            "onboarding_completed": user.onboarding_completed,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_onboarding(request):
    """Mark onboarding as completed for user."""
    user = request.user

    if not user.has_company:
        return Response(
            {"error": "Cannot complete onboarding without a company"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.onboarding_completed = True
    user.save()

    return Response(
        {"message": "Onboarding completed successfully", "onboarding_completed": True}
    )


# ============================================================
# COMPANY
# ============================================================


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


# ============================================================
# CATEGORIES
# ============================================================


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


# ============================================================
# ATTRIBUTES
# ============================================================


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


# ============================================================
# TEMPLATES
# ============================================================


class TemplateViewSet(viewsets.ModelViewSet):
    """
    Product templates with dynamic attributes.
    Admin can create/update/delete, others can only read.
    """

    permission_classes = [IsAuthenticated, IsCompanyMember, IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TemplateDetailSerializer
        return TemplateSerializer

    def get_queryset(self):
        """Filter by user's company"""
        return Template.objects.filter(
            company=self.request.user.company, is_active=True
        ).prefetch_related(
            "template_attributes__custom_attribute",
            "template_attributes__global_attribute",
        )

    @action(detail=True, methods=["get"])
    def structure(self, request, pk=None):
        """
        Get template structure for dynamic forms.
        Returns attribute definitions in order.
        """
        template = self.get_object()
        return Response(
            {
                "template_id": template.id,
                "template_name": template.name,
                "description": template.description,
                "attributes": template.get_attribute_structure(),
            }
        )

    @action(
        detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsAdminUser]
    )
    def add_attribute(self, request, pk=None):
        """Add an attribute to this template"""
        template = self.get_object()

        serializer = TemplateAttributeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate attribute belongs to same company
        custom_attr = serializer.validated_data.get("custom_attribute")
        if custom_attr and custom_attr.company != template.company:
            return Response(
                {"error": "Custom attribute must belong to the same company"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template_attr = TemplateAttribute.objects.create(
            template=template, **serializer.validated_data
        )

        return Response(
            TemplateAttributeSerializer(template_attr).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def remove_attribute(self, request, pk=None):
        """Remove an attribute from this template"""
        template = self.get_object()
        attribute_id = request.data.get("attribute_id")

        if not attribute_id:
            return Response(
                {"error": "attribute_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template_attr = template.template_attributes.get(id=attribute_id)
            template_attr.is_active = False
            template_attr.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TemplateAttribute.DoesNotExist:
            return Response(
                {"error": "Attribute not found in this template"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def reorder_attributes(self, request, pk=None):
        """
        Reorder template attributes.
        Expects: {"attributes": [{"id": 1, "order": 0}, {"id": 2, "order": 1}]}
        """
        template = self.get_object()
        attributes_data = request.data.get("attributes", [])

        if not attributes_data:
            return Response(
                {"error": "attributes list is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for attr_data in attributes_data:
                attr_id = attr_data.get("id")
                order = attr_data.get("order")

                if attr_id is None or order is None:
                    continue

                try:
                    template_attr = template.template_attributes.get(id=attr_id)
                    template_attr.order = order
                    template_attr.save()
                except TemplateAttribute.DoesNotExist:
                    pass

        return Response({"message": "Attributes reordered successfully"})

    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Get all products using this template"""
        template = self.get_object()
        products = template.products.filter(is_active=True)

        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Soft delete"""
        instance = self.get_object()

        # Check if template has active products
        if instance.products.filter(is_active=True).exists():
            return Response(
                {"error": "Cannot delete template with active products"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# PRODUCTS
# ============================================================


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


# ============================================================
# WAREHOUSES
# ============================================================


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


# ============================================================
# STOCK RECORDS
# ============================================================


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


# ============================================================
# STOCK MOVEMENTS
# ============================================================


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


# ============================================================
# REPORTS
# ============================================================


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

        categories = (
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
