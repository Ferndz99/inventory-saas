"""
Pytest tests for Inventory System
Run with: pytest inventory/tests/
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from django.urls import reverse


# Use pytest-django fixtures
pytestmark = pytest.mark.django_db


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def api_client():
    """API client for making requests"""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def company():
    """Create a test company"""
    from inventory.models import Company

    return Company.objects.create(name="Test Company", rut="76.123.456-7")


@pytest.fixture
def admin_user(company):
    """Create an admin user"""
    from django.contrib.auth import get_user_model

    Account = get_user_model()
    return Account.objects.create_user(
        email="admin@test.com", password="testpass123", company=company, role="admin"
    )


@pytest.fixture
def seller_user(company):
    """Create a seller user"""
    from django.contrib.auth import get_user_model

    Account = get_user_model()
    return Account.objects.create_user(
        email="seller@test.com",
        password="testpass123",
        company=company,
        role="seller",
    )


@pytest.fixture
def authenticated_client(api_client, admin_user):
    """API client authenticated as admin"""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def seller_client(api_client, seller_user):
    """API client authenticated as seller"""
    api_client.force_authenticate(user=seller_user)
    return api_client


@pytest.fixture
def category(company):
    """Create a test category"""
    from inventory.models import Category

    return Category.objects.create(name="Electronics", company=company)


@pytest.fixture
def global_attribute():
    """Create a global attribute"""
    from inventory.models import GlobalAttribute

    return GlobalAttribute.objects.create(
        name="Brand", slug="brand", data_type="text", description="Product brand"
    )


@pytest.fixture
def custom_attribute(company):
    """Create a custom attribute"""
    from inventory.models import CustomAttribute

    return CustomAttribute.objects.create(
        name="RAM",
        slug="ram",
        data_type="number",
        unit_of_measure="GB",
        company=company,
    )


@pytest.fixture
def template(company):
    """Create a test template"""
    from inventory.models import Template

    return Template.objects.create(
        name="Computers", description="Template for computers", company=company
    )


@pytest.fixture
def template_with_attributes(template, global_attribute, custom_attribute):
    """Template with attributes attached"""
    from inventory.models import TemplateAttribute

    TemplateAttribute.objects.create(
        template=template, global_attribute=global_attribute, is_required=True, order=1
    )

    TemplateAttribute.objects.create(
        template=template, custom_attribute=custom_attribute, is_required=True, order=2
    )

    return template


@pytest.fixture
def product(company, category, template_with_attributes):
    """Create a test product"""
    from inventory.models import Product

    return Product.objects.create(
        name="Laptop HP",
        sku="LAP-HP-001",
        barcode="1234567890",
        price=Decimal("650000"),
        cost=Decimal("520000"),
        minimum_stock=5,
        category=category,
        template=template_with_attributes,
        company=company,
        specifications={"brand": "HP", "ram": 8},
    )


@pytest.fixture
def warehouse(company):
    """Create a test warehouse"""
    from inventory.models import Warehouse

    return Warehouse.objects.create(
        name="Main Warehouse", address="Test Address 123", is_main=True, company=company
    )


@pytest.fixture
def stock_record(product, warehouse):
    """Create a stock record"""
    from inventory.models import StockRecord

    return StockRecord.objects.create(
        product=product, warehouse=warehouse, current_quantity=50
    )


# ============================================================
# ONBOARDING TESTS
# ============================================================


class TestOnboarding:
    """Tests for onboarding endpoints"""

    def test_setup_company_success(self, api_client):
        """Test successful company setup"""
        from django.contrib.auth import get_user_model

        Account = get_user_model()

        # Create user without company
        user = Account.objects.create_user(
            email="newuser@test.com", password="testpass123", role="admin"
        )

        api_client.force_authenticate(user=user)

        url = reverse("setup-company")
        data = {"company_name": "New Company", "company_rut": "76.111.222-3"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["company"]["name"] == "New Company"
        assert response.data["user"]["role"] == "admin"

        # Verify user was updated
        user.refresh_from_db()
        assert user.company is not None
        assert user.role == "admin"

    def test_setup_company_already_has_company(self, authenticated_client):
        """Test setup fails if user already has company"""
        url = reverse("setup-company")
        response = authenticated_client.post(
            url,
            {"company_name": "Another Company", "company_rut": "76.333.444-5"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already belongs" in response.data["error"]

    def test_onboarding_progress(self, authenticated_client, company):
        """Test onboarding progress calculation"""

        url = reverse("onboarding-progress")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["has_company"] is True
        assert "completed" in response.data
        assert "steps" in response.data


# ============================================================
# COMPANY TESTS
# ============================================================


class TestCompanyViewSet:
    """Tests for Company endpoints"""

    def test_list_company(self, authenticated_client, company):
        """Test listing companies (only user's company)"""

        url = reverse("company-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["name"] == company.name

    def test_company_stats(self, authenticated_client, product, stock_record):
        """Test company statistics"""
        url = reverse("company-stats")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_products"] == 1
        assert response.data["total_categories"] == 1
        assert response.data["total_warehouses"] == 1


# ============================================================
# CATEGORY TESTS
# ============================================================


class TestCategoryViewSet:
    """Tests for Category endpoints"""

    def test_list_categories(self, authenticated_client, category):
        """Test listing categories"""
        url = reverse("category-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == category.name

    def test_create_category_as_admin(self, authenticated_client):
        """Test creating category as admin"""
        url = reverse("category-list")
        response = authenticated_client.post(url, {"name": "New Category"})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Category"

    def test_create_category_as_seller(self, seller_client):
        """Test seller cannot create category"""
        url = reverse("category-list")
        response = seller_client.post(url, {"name": "New Category"})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_category_with_products(
        self, authenticated_client, category, product
    ):
        """Test cannot delete category with products"""
        url = reverse("category-detail", kwargs={"pk": category.id})

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "active products" in response.data["error"]

    def test_get_category_products(self, authenticated_client, category, product):
        """Test getting products in category"""
        url = reverse("category-products", kwargs={"pk": category.id})

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1


# ============================================================
# ATTRIBUTE TESTS
# ============================================================


class TestAttributeViewSets:
    """Tests for Global and Custom Attributes"""

    def test_list_global_attributes(self, authenticated_client, global_attribute):
        """Test listing global attributes"""
        url = reverse("global-attribute-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_create_custom_attribute(self, authenticated_client):
        """Test creating custom attribute"""
        url = reverse("global-attribute-list")

        response = authenticated_client.post(
            url,
            {"name": "Storage", "data_type": "number", "unit_of_measure": "GB"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "storage"

    def test_delete_attribute_in_use(
        self, authenticated_client, custom_attribute, template_with_attributes
    ):
        """Test cannot delete attribute in use"""
        url = reverse("global-attribute-detail", kwargs={"pk": custom_attribute.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================
# TEMPLATE TESTS
# ============================================================


class TestTemplateViewSet:
    """Tests for Template endpoints"""

    def test_list_templates(self, authenticated_client, template):
        """Test listing templates"""
        url = reverse("template-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_get_template_structure(
        self, authenticated_client, template_with_attributes
    ):
        """Test getting template structure"""
        url = reverse("template-structure", kwargs={"pk": template_with_attributes.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "attributes" in response.data
        assert len(response.data["attributes"]) == 2

    def test_add_attribute_to_template(
        self, authenticated_client, template, custom_attribute
    ):
        """Test adding attribute to template"""
        url = reverse("template-add-attribute", kwargs={"pk": template.id})
        response = authenticated_client.post(
            url,
            {"custom_attribute": custom_attribute.id, "is_required": True, "order": 1},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_reorder_attributes(self, authenticated_client, template_with_attributes):
        """Test reordering template attributes"""
        attrs = template_with_attributes.template_attributes.all()

        url = reverse(
            "template-reorder-attributes", kwargs={"pk": template_with_attributes.id}
        )

        response = authenticated_client.patch(
            url,
            {
                "attributes": [
                    {"id": attrs[0].id, "order": 2},
                    {"id": attrs[1].id, "order": 1},
                ]
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK


# ============================================================
# PRODUCT TESTS
# ============================================================


class TestProductViewSet:
    """Tests for Product endpoints"""

    def test_list_products(self, authenticated_client, product):
        """Test listing products"""

        url = reverse("product-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_create_product(
        self, authenticated_client, category, template_with_attributes
    ):
        """Test creating product"""

        url = reverse("product-list")

        response = authenticated_client.post(
            url,
            {
                "name": "New Laptop",
                "sku": "LAP-NEW-001",
                "price": 500000,
                "cost": 400000,
                "minimum_stock": 5,
                "category": category.id,
                "template": template_with_attributes.id,
                "specifications": {"brand": "Dell", "ram": 16},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Laptop"

    def test_create_product_invalid_specifications(
        self, authenticated_client, category, template_with_attributes
    ):
        """Test creating product with invalid specifications"""

        url = reverse("product-list")

        response = authenticated_client.post(
            url,
            {
                "name": "New Laptop",
                "sku": "LAP-NEW-002",
                "price": 500000,
                "cost": 400000,
                "category": category.id,
                "template": template_with_attributes.id,
                "specifications": {
                    "brand": "Dell"
                    # Missing required 'ram'
                },
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_validate_specifications(
        self, authenticated_client, category, template_with_attributes
    ):
        """Test specification validation endpoint"""

        url = reverse("product-validate-specifications")

        response = authenticated_client.post(
            url,
            {
                "name": "Test",
                "sku": "TEST-001",
                "price": 100000,
                "category": category.id,
                "template": template_with_attributes.id,
                "specifications": {"brand": "HP", "ram": 8},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is True

    def test_search_products(self, authenticated_client, product):
        """Test searching products"""

        url = reverse("product-list")

        response = authenticated_client.get(url, {"search": "HP"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_get_product_stock_details(
        self, authenticated_client, product, stock_record
    ):
        """Test getting product stock details"""

        url = reverse("product-stock-details", kwargs={"pk": product.id})

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_stock"] == 50
        assert len(response.data["stock_by_warehouse"]) == 1

    def test_low_stock_products(self, authenticated_client, product, stock_record):
        """Test getting low stock products"""
        # Set stock below minimum
        stock_record.current_quantity = 3
        stock_record.save()

        url = reverse("product-low-stock")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_delete_product_with_stock(
        self, authenticated_client, product, stock_record
    ):
        """Test cannot delete product with stock"""

        url = reverse("product-detail", kwargs={"pk": product.id})

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================
# WAREHOUSE TESTS
# ============================================================


class TestWarehouseViewSet:
    """Tests for Warehouse endpoints"""

    def test_list_warehouses(self, authenticated_client, warehouse):
        """Test listing warehouses"""

        url = reverse("warehouse-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_create_warehouse(self, authenticated_client):
        """Test creating warehouse"""
        url = reverse("warehouse-list")
        response = authenticated_client.post(
            url,
            {"name": "Secondary Warehouse", "address": "Address 456", "is_main": False},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_warehouse_stats(self, authenticated_client, warehouse, stock_record):
        """Test warehouse statistics"""
        url = reverse("warehouse-stats", kwargs={"pk": warehouse.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_products"] == 1
        assert response.data["total_items"] == 50

    def test_warehouse_inventory(self, authenticated_client, warehouse, stock_record):
        """Test getting warehouse inventory"""
        url = reverse("warehouse-inventory", kwargs={"pk": warehouse.id})

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1


# ============================================================
# STOCK MOVEMENT TESTS
# ============================================================


class TestStockMovementViewSet:
    """Tests for Stock Movement endpoints"""

    def test_create_stock_in(
        self, authenticated_client, product, warehouse, admin_user
    ):
        """Test creating stock IN movement"""
        url = reverse("stock-movement-list")
        response = authenticated_client.post(
            url,
            {
                "product": product.id,
                "warehouse": warehouse.id,
                "movement_type": "IN",
                "quantity": 20,
                "reason": "purchase",
                "reference_document": "INV-001",
                "unit_cost": 520000,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["resulting_balance"] == 20.0

        # Verify stock was updated
        from inventory.models import StockRecord

        stock_record = StockRecord.objects.get(product=product, warehouse=warehouse)
        assert stock_record.current_quantity == 20

    def test_create_stock_out(
        self, authenticated_client, product, warehouse, stock_record
    ):
        """Test creating stock OUT movement"""
        url = reverse("stock-movement-list")
        response = authenticated_client.post(
            url,
            {
                "product": product.id,
                "warehouse": warehouse.id,
                "movement_type": "OUT",
                "quantity": 10,
                "reason": "sale",
                "reference_document": "SALE-001",
                "unit_cost": 520000,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["resulting_balance"] == 40.0

    def test_stock_out_insufficient(
        self, authenticated_client, product, warehouse, stock_record
    ):
        """Test stock OUT with insufficient quantity fails"""
        url = reverse("stock-movement-list")

        response = authenticated_client.post(
            url,
            {
                "product": product.id,
                "warehouse": warehouse.id,
                "movement_type": "OUT",
                "quantity": 100,  # More than available
                "reason": "sale",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_transfer(
        self, authenticated_client, product, warehouse, company, stock_record
    ):
        """Test creating transfer between warehouses"""
        from inventory.models import Warehouse

        # Create second warehouse
        warehouse2 = Warehouse.objects.create(name="Warehouse 2", company=company)

        url = reverse("stock-movement-list")

        response = authenticated_client.post(
            url,
            {
                "product": product.id,
                "warehouse": warehouse.id,
                "to_warehouse": warehouse2.id,
                "movement_type": "TRANSFER",
                "quantity": 15,
                "reason": "transfer",
                "unit_cost": 520000,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify stock in both warehouses
        from inventory.models import StockRecord

        origin = StockRecord.objects.get(product=product, warehouse=warehouse)
        destination = StockRecord.objects.get(product=product, warehouse=warehouse2)

        assert origin.current_quantity == 35
        assert destination.current_quantity == 15

    def test_stock_adjustment(
        self, authenticated_client, product, warehouse, stock_record
    ):
        """Test stock adjustment"""

        url = reverse("stock-movement-adjustment")

        response = authenticated_client.post(
            url,
            {
                "product": product.id,
                "warehouse": warehouse.id,
                "new_quantity": 45,
                "notes": "Physical count adjustment",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify stock was adjusted
        stock_record.refresh_from_db()
        assert stock_record.current_quantity == 45

    def test_movement_summary(
        self, authenticated_client, product, warehouse, admin_user
    ):
        """Test movement summary"""
        from inventory.models import StockRecord, StockMovement

        # Create stock record
        sr = StockRecord.objects.create(
            product=product, warehouse=warehouse, current_quantity=0
        )

        # Create some movements
        StockMovement.objects.create(
            stock_record=sr,
            movement_type="IN",
            quantity=50,
            resulting_balance=50,
            reason="purchase",
            account=admin_user,
        )

        url = reverse("stock-movement-summary")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_movements"] >= 1

    def test_recent_movements(self, authenticated_client):
        """Test getting recent movements"""

        url = reverse("stock-movement-recent")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK


# ============================================================
# REPORT TESTS
# ============================================================


class TestReportViewSet:
    """Tests for Report endpoints"""

    def test_inventory_valuation(self, authenticated_client, product, stock_record):
        """Test inventory valuation report"""
        url = reverse("report-inventory-valuation")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "total_value" in response.data
        assert "by_warehouse" in response.data

    def test_stock_alerts(self, authenticated_client, product, stock_record):
        """Test stock alerts report"""
        # Set stock below minimum
        stock_record.current_quantity = 3
        stock_record.save()

        url = reverse("report-stock-alerts")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "low_stock" in response.data
        assert "out_of_stock" in response.data
        assert response.data["low_stock"]["count"] == 1

    def test_movement_report(self, authenticated_client):
        """Test movement report"""

        url = reverse("report-movement-report")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "by_type" in response.data
        assert "by_reason" in response.data

    def test_category_analysis(
        self, authenticated_client, category, product, stock_record
    ):
        """Test category analysis report"""

        url = reverse("report-category-analysis")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["categories"]) >= 1

    def test_top_products(self, authenticated_client, product, stock_record):
        """Test top products report"""

        url = reverse("report-top-products")

        response = authenticated_client.get(url, {"metric": "stock_value", "limit": 5})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["metric"] == "stock_value"
        assert response.data["limit"] == 5


# ============================================================
# PERMISSION TESTS
# ============================================================


class TestPermissions:
    """Tests for permission system"""

    def test_unauthenticated_access(self, api_client):
        """Test unauthenticated users cannot access endpoints"""

        url = reverse("product-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_seller_cannot_create_product(self, seller_client, category, template):
        """Test seller cannot create products"""

        url = reverse("product-list")

        response = seller_client.post(
            url,
            {
                "name": "Test",
                "sku": "TEST-001",
                "price": 100000,
                "category": category.id,
                "template": template.id,
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_seller_can_create_movement(
        self, seller_client, product, warehouse, stock_record
    ):
        """Test seller can create stock movements"""

        url = reverse("stock-movement-list")

        response = seller_client.post(
            url,
            {
                "product": product.id,
                "warehouse": warehouse.id,
                "movement_type": "OUT",
                "quantity": 1,
                "reason": "sale",
                "unit_cost": 520000,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED


# ============================================================
# INTEGRATION TESTS
# ============================================================


class TestIntegrationScenarios:
    """End-to-end integration tests"""

    def test_complete_product_lifecycle(
        self, authenticated_client, company, category, template_with_attributes
    ):
        """Test complete product lifecycle from creation to sale"""

        url_product = reverse("product-list")

        # 1. Create product
        product_response = authenticated_client.post(
            url_product,
            {
                "name": "Integration Test Laptop",
                "sku": "INT-TEST-001",
                "barcode": "9999999999",
                "price": 600000,
                "cost": 480000,
                "minimum_stock": 5,
                "category": category.id,
                "template": template_with_attributes.id,
                "specifications": {"brand": "Test Brand", "ram": 16},
            },
            format="json",
        )
        assert product_response.status_code == status.HTTP_201_CREATED
        product_id = product_response.data["id"]

        url_warehouse = reverse("warehouse-list")

        # 2. Create warehouse
        warehouse_response = authenticated_client.post(
            url_warehouse, {"name": "Test Warehouse", "is_main": True}
        )
        assert warehouse_response.status_code == status.HTTP_201_CREATED
        warehouse_id = warehouse_response.data["id"]

        url_stock_movement = reverse("stock-movement-list")

        # 3. Add stock (purchase)
        purchase_response = authenticated_client.post(
            url_stock_movement,
            {
                "product": product_id,
                "warehouse": warehouse_id,
                "movement_type": "IN",
                "quantity": 30,
                "reason": "purchase",
                "unit_cost": 480000,
            },
        )
        assert purchase_response.status_code == status.HTTP_201_CREATED
        assert purchase_response.data["resulting_balance"] == 30.0

        # 4. Make a sale
        sale_response = authenticated_client.post(
            url_stock_movement,
            {
                "product": product_id,
                "warehouse": warehouse_id,
                "movement_type": "OUT",
                "quantity": 5,
                "reason": "sale",
                "reference_document": "SALE-TEST-001",
                "unit_cost": 480000
            },
        )
        assert sale_response.status_code == status.HTTP_201_CREATED
        assert sale_response.data["resulting_balance"] == 25.0

        url_product_stock = reverse("product-stock-details", kwargs={"pk": product_id})

        # 5. Check stock details
        stock_response = authenticated_client.get(url_product_stock)
        assert stock_response.status_code == status.HTTP_200_OK
        assert stock_response.data["total_stock"] == 25.0

        url_product_movement = reverse(
            "product-movement-history", kwargs={"pk": product_id}
        )

        # 6. Verify movement history
        history_response = authenticated_client.get(url_product_movement)
        assert history_response.status_code == status.HTTP_200_OK
        assert len(history_response.data["results"]) == 2  # Purchase + Sale

    def test_multi_warehouse_transfer_workflow(
        self, authenticated_client, company, product, admin_user
    ):
        """Test transferring products between multiple warehouses"""
        from inventory.models import Warehouse, StockRecord

        # Create warehouses
        wh1 = Warehouse.objects.create(name="WH1", company=company, is_main=True)
        wh2 = Warehouse.objects.create(name="WH2", company=company)
        wh3 = Warehouse.objects.create(name="WH3", company=company)

        # Initial stock in WH1
        StockRecord.objects.create(product=product, warehouse=wh1, current_quantity=100)

        url_stock_movement = reverse("stock-movement-list")

        # Transfer WH1 -> WH2
        response1 = authenticated_client.post(
            url_stock_movement,
            {
                "product": product.id,
                "warehouse": wh1.id,
                "to_warehouse": wh2.id,
                "movement_type": "TRANSFER",
                "quantity": 30,
                "reason": "transfer",
                "unit_cost": 480000
            },
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Transfer WH2 -> WH3
        response2 = authenticated_client.post(
            url_stock_movement,
            {
                "product": product.id,
                "warehouse": wh2.id,
                "to_warehouse": wh3.id,
                "movement_type": "TRANSFER",
                "quantity": 10,
                "reason": "transfer",
                "unit_cost": 480000
            },
        )
        assert response2.status_code == status.HTTP_201_CREATED

        url_product_stock = reverse("product-stock-details", kwargs={"pk": product.id})

        # Verify final distribution
        stock_response = authenticated_client.get(
            url_product_stock
        )
        assert stock_response.data["total_stock"] == 100  # Total unchanged

