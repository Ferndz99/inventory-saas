# factories.py
# Coloca este archivo en: myapp/factories.py


from factory.django import DjangoModelFactory
from factory import fuzzy
from decimal import Decimal
from django.contrib.auth import get_user_model
from faker import Faker
from factory.declarations import Sequence, LazyAttribute, SubFactory, SelfAttribute
from factory.faker import Faker as FactoryFaker
from factory.helpers import post_generation


from .models import (
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

fake = Faker("es_CL")  # Faker en español chileno
Account = get_user_model()


class AccountFactory(DjangoModelFactory):
    class Meta:
        model = Account
        django_get_or_create = ("email",)

    email = Sequence(lambda n: f"user{n}@example.com")
    is_staff = False
    is_active = True
    role = "admin"  # Asume que RoleAccount.ADMIN = 'admin'
    company = None  # Se puede asignar después o con SubFactory si es necesario
    onboarding_completed = False

    @post_generation
    def password(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password("password123")


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company
        django_get_or_create = ("rut",)

    name = FactoryFaker("company", locale="es_CL")
    rut = Sequence(lambda n: f"{76000000 + n}-K")
    is_active = True


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = FactoryFaker("word")
    company = SubFactory(CompanyFactory)
    is_active = True


class GlobalAttributeFactory(DjangoModelFactory):
    class Meta:
        model = GlobalAttribute
        django_get_or_create = ("slug",)

    name = Sequence(lambda n: f"Global Attr {n}")
    slug = LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))
    data_type = fuzzy.FuzzyChoice(["text", "number", "boolean", "date", "decimal"])
    unit_of_measure = FactoryFaker("word")
    description = FactoryFaker("sentence", locale="es_CL")
    is_active = True


class CustomAttributeFactory(DjangoModelFactory):
    class Meta:
        model = CustomAttribute

    name = Sequence(lambda n: f"Custom Attr {n}")
    slug = LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))
    data_type = fuzzy.FuzzyChoice(["text", "number", "boolean", "date", "decimal"])
    unit_of_measure = FactoryFaker("word")
    description = FactoryFaker("sentence", locale="es_CL")
    company = SubFactory(CompanyFactory)
    is_active = True


class TemplateFactory(DjangoModelFactory):
    class Meta:
        model = Template

    name = Sequence(lambda n: f"Template {n}")
    description = FactoryFaker("text", max_nb_chars=200, locale="es_CL")
    company = SubFactory(CompanyFactory)
    is_active = True


class TemplateAttributeFactory(DjangoModelFactory):
    class Meta:
        model = TemplateAttribute

    template = SubFactory(TemplateFactory)
    global_attribute = SubFactory(GlobalAttributeFactory)
    custom_attribute = None  # Solo uno debe estar definido
    is_required = FactoryFaker("boolean", chance_of_getting_true=30)
    order = Sequence(lambda n: n)
    default_value = FactoryFaker("word")
    is_active = True


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = FactoryFaker("catch_phrase", locale="es_CL")
    sku = Sequence(lambda n: f"SKU-{n:06d}")
    barcode = Sequence(lambda n: f"{7800000000000 + n}")
    price = fuzzy.FuzzyDecimal(1000, 100000, precision=0)
    cost = LazyAttribute(lambda obj: obj.price * Decimal("0.6"))
    price_includes_tax = True
    category = SubFactory(CategoryFactory)
    template = SubFactory(TemplateFactory)
    company = SelfAttribute("category.company")
    minimum_stock = fuzzy.FuzzyFloat(10, 50)
    unit_of_measure = fuzzy.FuzzyChoice(["unit", "kg", "liter", "meter", "box"])
    specifications = LazyAttribute(lambda obj: {})
    is_active = True

    @post_generation
    def sync_company(obj, create, extracted, **kwargs):
        """Asegura que template y category pertenezcan a la misma empresa"""
        if not create:
            return

        # Actualizar template para que pertenezca a la misma empresa
        if obj.template.company != obj.company:
            obj.template.company = obj.company
            obj.template.save()


class WarehouseFactory(DjangoModelFactory):
    class Meta:
        model = Warehouse

    name = Sequence(lambda n: f"Bodega {n}")
    address = FactoryFaker("address", locale="es_CL")
    is_main = False
    company = SubFactory(CompanyFactory)
    is_active = True


class StockRecordFactory(DjangoModelFactory):
    class Meta:
        model = StockRecord

    product = SubFactory(ProductFactory)
    warehouse = SubFactory(WarehouseFactory)
    current_quantity = fuzzy.FuzzyFloat(0, 1000)
    is_active = True

    @post_generation
    def sync_company(obj, create, extracted, **kwargs):
        """Asegura que warehouse pertenezca a la misma empresa del producto"""
        if not create:
            return

        if obj.warehouse.company != obj.product.company:
            obj.warehouse.company = obj.product.company
            obj.warehouse.save()


class StockMovementFactory(DjangoModelFactory):
    class Meta:
        model = StockMovement

    stock_record = SubFactory(StockRecordFactory)
    movement_type = fuzzy.FuzzyChoice(["IN", "OUT"])
    quantity = fuzzy.FuzzyFloat(1, 100)
    resulting_balance = LazyAttribute(
        lambda obj: obj.stock_record.current_quantity
        + (obj.quantity if obj.movement_type == "IN" else -obj.quantity)
    )
    reason = LazyAttribute(
        lambda obj: "purchase" if obj.movement_type == "IN" else "sale"
    )
    account = SubFactory(AccountFactory)
    notes = FactoryFaker("sentence", locale="es_CL")
    reference_document = Sequence(lambda n: f"DOC-{n:06d}")
    unit_cost = LazyAttribute(
        lambda obj: obj.stock_record.product.cost if obj.movement_type == "IN" else None
    )
