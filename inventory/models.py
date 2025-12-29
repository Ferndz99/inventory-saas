from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator


Account = get_user_model()


class Company(models.Model):
    """Empresa - Company model"""

    name = models.CharField(max_length=255)
    rut = models.CharField(max_length=20, unique=True)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


class Category(models.Model):
    """Product category"""

    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="categories"
    )

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ["name", "company"]

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

    def __str__(self):
        return self.name


class CustomAttribute(models.Model):
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
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="custom_attributes"
    )

    class Meta:
        unique_together = ["slug", "company"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Template(models.Model):
    """Product template defining structure"""

    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="templates"
    )

    class Meta:
        unique_together = ["name", "company"]

    def __str__(self):
        return self.name


class TemplateAttribute(models.Model):
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

    class Meta:
        ordering = ["order"]
        unique_together = ["template", "custom_attribute", "global_attribute"]

    def __str__(self):
        return f"{self.template.name} - {self.custom_attribute.name} - {self.global_attribute.name}"


class Product(models.Model):
    """Product model with dynamic specifications"""

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=0, validators=[MinValueValidator(Decimal("0"))]
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    template = models.ForeignKey(
        Template, on_delete=models.PROTECT, related_name="products"
    )
    specifications = models.JSONField(
        default=dict, blank=True, help_text="Dynamic product attributes"
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="products"
    )

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Warehouse(models.Model):
    """Warehouse or storage location"""

    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    is_main = models.BooleanField(default=False, help_text="Main warehouse")
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="warehouses"
    )

    class Meta:
        unique_together = ["name", "company"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class StockRecord(models.Model):
    """Current stock level for a product in a warehouse"""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_records"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stock_records"
    )
    current_quantity = models.FloatField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        unique_together = ["product", "warehouse"]

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.current_quantity}"


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
    ]

    stock_record = models.ForeignKey(
        StockRecord, on_delete=models.CASCADE, related_name="movements"
    )
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.FloatField()
    resulting_balance = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="stock_movements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.movement_type} - {self.quantity} ({self.created_at})"
