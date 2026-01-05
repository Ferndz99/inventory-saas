import django_filters
from django.db import models
from django.db.models import Q, Sum

from .models import Product, StockMovement, StockRecord


class ProductFilter(django_filters.FilterSet):
    """
    Advanced filtering for products.
    Supports filtering by category, template, price range, stock level, etc.
    """

    # Text search
    search = django_filters.CharFilter(method="search_filter", label="Search")

    # Category and template
    category = django_filters.NumberFilter(field_name="category__id")
    category_name = django_filters.CharFilter(
        field_name="category__name", lookup_expr="icontains"
    )
    template = django_filters.NumberFilter(field_name="template__id")
    template_name = django_filters.CharFilter(
        field_name="template__name", lookup_expr="icontains"
    )

    # Price filters
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    cost_min = django_filters.NumberFilter(field_name="cost", lookup_expr="gte")
    cost_max = django_filters.NumberFilter(field_name="cost", lookup_expr="lte")

    # Stock filters
    has_stock = django_filters.BooleanFilter(method="filter_has_stock")
    below_minimum = django_filters.BooleanFilter(method="filter_below_minimum")
    warehouse = django_filters.NumberFilter(method="filter_by_warehouse")

    # Other filters
    price_includes_tax = django_filters.BooleanFilter()
    unit_of_measure = django_filters.CharFilter(lookup_expr="iexact")

    # Date filters
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Product
        fields = [
            "category",
            "template",
            "price_includes_tax",
            "unit_of_measure",
            "is_active",
        ]

    def search_filter(self, queryset, name, value):
        """
        Search across multiple fields.
        """
        return queryset.filter(
            Q(name__icontains=value)
            | Q(sku__icontains=value)
            | Q(barcode__icontains=value)
        )

    def filter_has_stock(self, queryset, name, value):
        """
        Filter products with/without stock.
        """
        queryset = queryset.annotate(total_stock=Sum("stock_records__current_quantity"))

        if value:
            return queryset.filter(total_stock__gt=0)
        else:
            return queryset.filter(Q(total_stock=0) | Q(total_stock__isnull=True))

    def filter_below_minimum(self, queryset, name, value):
        """
        Filter products below minimum stock.
        """
        queryset = queryset.annotate(total_stock=Sum("stock_records__current_quantity"))

        if value:
            return queryset.filter(total_stock__lt=models.F("minimum_stock"))
        else:
            return queryset.filter(total_stock__gte=models.F("minimum_stock"))

    def filter_by_warehouse(self, queryset, name, value):
        """
        Filter products available in a specific warehouse.
        """
        return queryset.filter(
            stock_records__warehouse__id=value, stock_records__current_quantity__gt=0
        ).distinct()


class StockMovementFilter(django_filters.FilterSet):
    """
    Advanced filtering for stock movements.
    Supports filtering by type, reason, date range, warehouse, product, etc.
    """

    # Movement type and reason
    movement_type = django_filters.ChoiceFilter(
        choices=StockMovement.MOVEMENT_TYPE_CHOICES
    )
    reason = django_filters.ChoiceFilter(choices=StockMovement.REASON_CHOICES)

    # Product filters
    product = django_filters.NumberFilter(field_name="stock_record__product__id")
    product_name = django_filters.CharFilter(
        field_name="stock_record__product__name", lookup_expr="icontains"
    )
    product_sku = django_filters.CharFilter(
        field_name="stock_record__product__sku", lookup_expr="icontains"
    )
    category = django_filters.NumberFilter(
        field_name="stock_record__product__category__id"
    )

    # Warehouse filters
    warehouse = django_filters.NumberFilter(field_name="stock_record__warehouse__id")
    warehouse_name = django_filters.CharFilter(
        field_name="stock_record__warehouse__name", lookup_expr="icontains"
    )
    from_warehouse = django_filters.NumberFilter(field_name="from_warehouse__id")
    to_warehouse = django_filters.NumberFilter(field_name="to_warehouse__id")

    # User filter
    user = django_filters.NumberFilter(field_name="account__id")
    user_email = django_filters.CharFilter(
        field_name="account__email", lookup_expr="icontains"
    )

    # Quantity filters
    quantity_min = django_filters.NumberFilter(field_name="quantity", lookup_expr="gte")
    quantity_max = django_filters.NumberFilter(field_name="quantity", lookup_expr="lte")

    # Date filters
    date_from = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    date_to = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    date = django_filters.DateFilter(field_name="created_at__date")

    # Reference document
    reference_document = django_filters.CharFilter(lookup_expr="icontains")

    # Search
    search = django_filters.CharFilter(method="search_filter", label="Search")

    class Meta:
        model = StockMovement
        fields = ["movement_type", "reason", "reference_document"]

    def search_filter(self, queryset, name, value):
        """
        Search across multiple fields.
        """
        return queryset.filter(
            Q(stock_record__product__name__icontains=value)
            | Q(stock_record__product__sku__icontains=value)
            | Q(reference_document__icontains=value)
            | Q(notes__icontains=value)
        )


class StockRecordFilter(django_filters.FilterSet):
    """
    Filtering for stock records.
    """

    # Product filters
    product = django_filters.NumberFilter(field_name="product__id")
    product_name = django_filters.CharFilter(
        field_name="product__name", lookup_expr="icontains"
    )
    product_sku = django_filters.CharFilter(
        field_name="product__sku", lookup_expr="icontains"
    )
    category = django_filters.NumberFilter(field_name="product__category__id")

    # Warehouse filters
    warehouse = django_filters.NumberFilter(field_name="warehouse__id")
    warehouse_name = django_filters.CharFilter(
        field_name="warehouse__name", lookup_expr="icontains"
    )

    # Quantity filters
    quantity_min = django_filters.NumberFilter(
        field_name="current_quantity", lookup_expr="gte"
    )
    quantity_max = django_filters.NumberFilter(
        field_name="current_quantity", lookup_expr="lte"
    )
    has_stock = django_filters.BooleanFilter(method="filter_has_stock")
    below_minimum = django_filters.BooleanFilter(method="filter_below_minimum")

    # Search
    search = django_filters.CharFilter(method="search_filter", label="Search")

    class Meta:
        model = StockRecord
        fields = ["is_active"]

    def search_filter(self, queryset, name, value):
        """
        Search across product and warehouse.
        """
        return queryset.filter(
            Q(product__name__icontains=value)
            | Q(product__sku__icontains=value)
            | Q(warehouse__name__icontains=value)
        )

    def filter_has_stock(self, queryset, name, value):
        """
        Filter records with/without stock.
        """
        if value:
            return queryset.filter(current_quantity__gt=0)
        else:
            return queryset.filter(current_quantity=0)

    def filter_below_minimum(self, queryset, name, value):
        """
        Filter records below minimum stock.
        """
        from django.db.models import F

        if value:
            return queryset.filter(current_quantity__lt=F("product__minimum_stock"))
        else:
            return queryset.filter(current_quantity__gte=F("product__minimum_stock"))
