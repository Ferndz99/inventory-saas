from decimal import Decimal

from django.db import models
from django.db.models import QuerySet
from django.db.models import Q, Sum, F, Case, When
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify


Account = get_user_model()


class BaseModel(models.Model):
    """Abstract base model with common fields for soft-delete and audit"""

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(BaseModel):
    """Empresa - Company model"""

    name = models.CharField(max_length=255)
    rut = models.CharField(max_length=20, unique=True, db_index=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = "Companies"
        indexes = [
            models.Index(fields=["rut"]),
        ]

    def __str__(self):
        return self.name


class Category(BaseModel):
    """Product category"""

    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="categories"
    )

    class Meta(BaseModel.Meta):
        verbose_name_plural = "Categories"
        unique_together = ["name", "company"]
        indexes = [
            models.Index(fields=["company", "name"]),
        ]

    def __str__(self):
        return self.name


class GlobalAttribute(models.Model):
    """Global attributes available for all companies"""

    DATA_TYPE_CHOICES = [
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("date", "Date"),
        ("decimal", "Decimal"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    unit_of_measure = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True, help_text="Description for users")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.data_type})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class CustomAttribute(BaseModel):
    """Company-specific custom attributes"""

    DATA_TYPE_CHOICES = [
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("date", "Date"),
        ("decimal", "Decimal"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField()
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    unit_of_measure = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True, help_text="Description for users")
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="custom_attributes"
    )

    class Meta(BaseModel.Meta):
        unique_together = ["slug", "company"]
        ordering = ["name"]
        indexes = [
            models.Index(fields=["company", "slug"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Template(BaseModel):
    """Product template defining structure"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="templates"
    )

    template_attributes: QuerySet["TemplateAttribute"]

    class Meta(BaseModel.Meta):
        unique_together = ["name", "company"]
        indexes = [
            models.Index(fields=["company", "name"]),
        ]

    def __str__(self):
        return self.name

    def get_attribute_structure(self):
        """
        Returns the complete attribute structure for this template.
        Useful for frontend forms and validation.
        """
        attrs = self.template_attributes.select_related(
            "custom_attribute", "global_attribute"
        ).filter(is_active=True)

        return [
            {
                "slug": (ta.custom_attribute or ta.global_attribute).slug,
                "name": (ta.custom_attribute or ta.global_attribute).name,
                "data_type": (ta.custom_attribute or ta.global_attribute).data_type,
                "unit_of_measure": (
                    ta.custom_attribute or ta.global_attribute
                ).unit_of_measure,
                "description": (ta.custom_attribute or ta.global_attribute).description,
                "is_required": ta.is_required,
                "order": ta.order,
                "default_value": ta.default_value
            }
            for ta in attrs
        ]


class TemplateAttribute(BaseModel):
    """Attributes assigned to a template"""

    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="template_attributes"
    )
    custom_attribute = models.ForeignKey(
        CustomAttribute,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="template_attributes",
    )
    global_attribute = models.ForeignKey(
        GlobalAttribute,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="template_attributes",
    )
    is_required = models.BooleanField(default=False)
    order = models.IntegerField(default=0, help_text="Display order in UI")
    default_value = models.CharField(
        max_length=255, blank=True, help_text="Default value for this attribute"
    )

    class Meta(BaseModel.Meta):
        ordering = ["order"]
        indexes = [
            models.Index(fields=["template", "order"]),
        ]

    def __str__(self):
        attr = self.custom_attribute or self.global_attribute
        return f"{self.template.name} - {attr.name if attr else 'N/A'}"

    def clean(self):
        """Validate that either custom_attribute or global_attribute is set, but not both"""
        if not self.custom_attribute and not self.global_attribute:
            raise ValidationError(
                "Either custom_attribute or global_attribute must be set"
            )
        if self.custom_attribute and self.global_attribute:
            raise ValidationError(
                "Only one of custom_attribute or global_attribute can be set"
            )

        # Validate that custom_attribute belongs to the same company as template
        if (
            self.custom_attribute
            and self.custom_attribute.company != self.template.company
        ):
            raise ValidationError(
                "Custom attribute must belong to the same company as the template"
            )


class Product(BaseModel):
    """Product model with dynamic specifications"""

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    barcode = models.CharField(
        max_length=50, blank=True, db_index=True, help_text="Barcode for scanning"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Sales price",
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(Decimal("0"))],
        default=Decimal("0"),
        help_text="Cost price",
    )
    price_includes_tax = models.BooleanField(
        default=True, help_text="Price includes IVA (19%)"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    template = models.ForeignKey(
        Template, on_delete=models.PROTECT, related_name="products"
    )
    specifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dynamic product attributes based on template",
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="products"
    )
    minimum_stock = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minimum stock level for alerts",
    )
    unit_of_measure = models.CharField(
        max_length=20,
        default="unit",
        help_text="Unit of measure (unit, kg, liter, etc.)",
    )
    stock_records: QuerySet["StockRecord"]

    class Meta(BaseModel.Meta):
        indexes = [
            models.Index(fields=["company", "sku"]),
            models.Index(fields=["company", "category"]),
            models.Index(fields=["barcode"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_specification(self, slug, default=None):
        """Get a specification value safely"""
        return self.specifications.get(slug, default)

    def set_specification(self, slug, value):
        """
        Set a specification value with validation against template.
        Returns True if successful, raises ValidationError otherwise.
        """
        # Check if attribute exists in template
        attribute_exists = self.template.template_attributes.filter(
            Q(custom_attribute__slug=slug) | Q(global_attribute__slug=slug)
        ).exists()

        if not attribute_exists:
            raise ValidationError(
                f"Attribute '{slug}' is not defined in template '{self.template.name}'"
            )

        self.specifications[slug] = value
        return True

    def get_total_stock(self):
        """Get total stock across all warehouses"""
        return self.stock_records.aggregate(total=Sum("current_quantity"))["total"] or 0

    def is_below_minimum(self):
        """Check if total stock is below minimum threshold"""
        return self.get_total_stock() < self.minimum_stock

    def clean(self):
        """Validate that template and category belong to the same company"""
        if self.template.company != self.company:
            raise ValidationError("Template must belong to the same company")
        if self.category.company != self.company:
            raise ValidationError("Category must belong to the same company")


class Warehouse(BaseModel):
    """Warehouse or storage location"""

    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    is_main = models.BooleanField(default=False, help_text="Main warehouse")
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="warehouses"
    )

    class Meta(BaseModel.Meta):
        unique_together = ["name", "company"]
        indexes = [
            models.Index(fields=["company", "is_main"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    def save(self, *args, **kwargs):
        """Ensure only one main warehouse per company"""
        if self.is_main:
            # Set all other warehouses as non-main for this company
            Warehouse.objects.filter(company=self.company, is_main=True).exclude(
                pk=self.pk
            ).update(is_main=False)
        super().save(*args, **kwargs)


class StockRecord(BaseModel):
    """Current stock level for a product in a warehouse"""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_records"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stock_records"
    )
    current_quantity = models.FloatField(default=0, validators=[MinValueValidator(0)])

    movements: QuerySet["StockMovement"]

    class Meta(BaseModel.Meta):
        unique_together = ["product", "warehouse"]
        indexes = [
            models.Index(fields=["product", "warehouse"]),
            models.Index(fields=["warehouse", "current_quantity"]),
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.current_quantity}"

    def calculate_quantity_from_movements(self):
        """
        Calculate current quantity from movement history.
        Useful for verification and reconciliation.
        """
        movements = self.movements.aggregate(
            total=Sum(
                Case(
                    When(movement_type="IN", then=F("quantity")),
                    When(movement_type="OUT", then=-F("quantity")),
                    default=0,
                    output_field=models.FloatField(),
                )
            )
        )
        return movements["total"] or 0

    def reconcile(self):
        """
        Reconcile current_quantity with movement history.
        Updates current_quantity to match calculated value.
        """
        calculated = self.calculate_quantity_from_movements()
        if self.current_quantity != calculated:
            self.current_quantity = calculated
            self.save()
            return True
        return False


class StockMovement(models.Model):
    """Record of stock movements (in/out/transfer)"""

    MOVEMENT_TYPE_CHOICES = [
        ("IN", "Stock In"),
        ("OUT", "Stock Out"),
        ("TRANSFER", "Transfer"),
    ]

    REASON_CHOICES = [
        ("sale", "Sale"),
        ("purchase", "Purchase"),
        ("loss", "Loss/Waste"),
        ("return", "Return"),
        ("adjustment", "Adjustment"),
        ("transfer", "Transfer"),
    ]

    stock_record = models.ForeignKey(
        StockRecord, on_delete=models.CASCADE, related_name="movements"
    )
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.FloatField(validators=[MinValueValidator(0.01)])
    resulting_balance = models.FloatField(help_text="Balance after this movement")
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="stock_movements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    # Additional fields for better traceability
    reference_document = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference number (invoice, purchase order, etc.)",
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
        help_text="Unit cost at the time of movement (for IN movements)",
    )

    # For transfers
    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_out",
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_in",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stock_record", "-created_at"]),
            models.Index(fields=["account", "-created_at"]),
            models.Index(fields=["movement_type", "-created_at"]),
            models.Index(fields=["reference_document"]),
        ]

    def __str__(self):
        return f"{self.movement_type} - {self.quantity} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    def clean(self):
        """Validate movement based on type"""
        # Validate OUT movements don't exceed available stock
        if self.movement_type == "OUT":
            available = self.stock_record.current_quantity
            if self.quantity > available:
                raise ValidationError(
                    f"Insufficient stock. Available: {available}, Requested: {self.quantity}"
                )

        # Validate TRANSFER movements have both warehouses set
        if self.movement_type == "TRANSFER":
            if not self.from_warehouse or not self.to_warehouse:
                raise ValidationError(
                    "Transfer movements must have both from_warehouse and to_warehouse set"
                )
            if self.from_warehouse == self.to_warehouse:
                raise ValidationError(
                    "Transfer movements must have different from_warehouse and to_warehouse"
                )

    def save(self, *args, **kwargs):
        """Update stock record balance after saving movement"""
        is_new = self.pk is None

        if is_new:
            # Calculate resulting balance for new movements
            current = self.stock_record.current_quantity
            if self.movement_type == "IN":
                self.resulting_balance = current + self.quantity
            elif self.movement_type == "OUT":
                self.resulting_balance = current - self.quantity
            else:  # TRANSFER
                self.resulting_balance = current

        super().save(*args, **kwargs)

        # Update stock record
        if is_new:
            self.stock_record.current_quantity = self.resulting_balance
            self.stock_record.save()
