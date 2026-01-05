from django.urls import path, include
from rest_framework.routers import DefaultRouter

from inventory.views import (
    CompanyViewSet,
    CategoryViewSet,
    GlobalAttributeViewSet,
    CustomAttributeViewSet,
    TemplateViewSet,
    ProductViewSet,
    WarehouseViewSet,
    StockRecordViewSet,
    StockMovementViewSet,
    ReportViewSet,
    complete_onboarding,
    onboarding_progress,
    setup_company,
)


# Create router and register viewsets
router = DefaultRouter()

router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(
    r"global-attributes", GlobalAttributeViewSet, basename="global-attribute"
)
router.register(
    r"custom-attributes", CustomAttributeViewSet, basename="custom-attribute"
)
router.register(r"templates", TemplateViewSet, basename="template")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"stock-records", StockRecordViewSet, basename="stock-record")
router.register(r"stock-movements", StockMovementViewSet, basename="stock-movement")
router.register(r"reports", ReportViewSet, basename="report")


# URL patterns
urlpatterns = [
    path("onboarding/setup-company/", setup_company, name="setup-company"),
    path("onboarding/progress/", onboarding_progress, name="onboarding-progress"),
    path("onboarding/complete/", complete_onboarding, name="complete-onboarding"),
    path("", include(router.urls)),
]


"""
API Endpoints Documentation:

COMPANIES
---------
GET    /api/companies/                    - List companies (user's company only)
GET    /api/companies/{id}/               - Retrieve company details
GET    /api/companies/stats/              - Get company statistics

CATEGORIES
----------
GET    /api/categories/                   - List categories
POST   /api/categories/                   - Create category (admin only)
GET    /api/categories/{id}/              - Retrieve category
PUT    /api/categories/{id}/              - Update category (admin only)
DELETE /api/categories/{id}/              - Soft delete category (admin only)
GET    /api/categories/{id}/products/     - List products in category

GLOBAL ATTRIBUTES
-----------------
GET    /api/global-attributes/            - List global attributes
GET    /api/global-attributes/{id}/       - Retrieve global attribute

CUSTOM ATTRIBUTES
-----------------
GET    /api/custom-attributes/            - List custom attributes
POST   /api/custom-attributes/            - Create custom attribute (admin only)
GET    /api/custom-attributes/{id}/       - Retrieve custom attribute
PUT    /api/custom-attributes/{id}/       - Update custom attribute (admin only)
DELETE /api/custom-attributes/{id}/       - Soft delete custom attribute (admin only)

TEMPLATES
---------
GET    /api/templates/                    - List templates
POST   /api/templates/                    - Create template (admin only)
GET    /api/templates/{id}/               - Retrieve template with attributes
PUT    /api/templates/{id}/               - Update template (admin only)
DELETE /api/templates/{id}/               - Soft delete template (admin only)
GET    /api/templates/{id}/structure/     - Get template structure for forms
POST   /api/templates/{id}/add_attribute/ - Add attribute to template (admin only)
DELETE /api/templates/{id}/remove_attribute/ - Remove attribute from template (admin only)
PATCH  /api/templates/{id}/reorder_attributes/ - Reorder template attributes (admin only)
GET    /api/templates/{id}/products/      - List products using this template

PRODUCTS
--------
GET    /api/products/                     - List products
POST   /api/products/                     - Create product (admin only)
GET    /api/products/{id}/                - Retrieve product details
PUT    /api/products/{id}/                - Update product (admin only)
DELETE /api/products/{id}/                - Soft delete product (admin only)
POST   /api/products/validate_specifications/ - Validate specifications without creating
GET    /api/products/low_stock/           - List products with low stock
GET    /api/products/out_of_stock/        - List products out of stock
GET    /api/products/{id}/stock_details/  - Get detailed stock info for product
GET    /api/products/{id}/movement_history/ - Get movement history for product
POST   /api/products/bulk_create/         - Bulk create products (admin only)
GET    /api/products/export/              - Export products to JSON

Filters for products:
- search: Search in name, SKU, barcode
- category: Filter by category ID
- category_name: Filter by category name (partial match)
- template: Filter by template ID
- template_name: Filter by template name (partial match)
- price_min, price_max: Filter by price range
- cost_min, cost_max: Filter by cost range
- has_stock: Filter products with/without stock (true/false)
- below_minimum: Filter products below minimum stock (true/false)
- warehouse: Filter products in specific warehouse
- price_includes_tax: Filter by tax inclusion (true/false)
- unit_of_measure: Filter by unit (exact match)
- created_after, created_before: Filter by creation date

WAREHOUSES
----------
GET    /api/warehouses/                   - List warehouses
POST   /api/warehouses/                   - Create warehouse (admin only)
GET    /api/warehouses/{id}/              - Retrieve warehouse
PUT    /api/warehouses/{id}/              - Update warehouse (admin only)
DELETE /api/warehouses/{id}/              - Soft delete warehouse (admin only)
GET    /api/warehouses/{id}/inventory/    - Get complete inventory for warehouse
GET    /api/warehouses/{id}/stats/        - Get warehouse statistics
GET    /api/warehouses/{id}/movements/    - Get recent movements for warehouse

STOCK RECORDS
-------------
GET    /api/stock-records/                - List stock records
GET    /api/stock-records/{id}/           - Retrieve stock record
POST   /api/stock-records/{id}/reconcile/ - Reconcile stock record (admin only)

Filters for stock records:
- product: Filter by product ID
- product_name: Filter by product name (partial match)
- product_sku: Filter by product SKU (partial match)
- category: Filter by category ID
- warehouse: Filter by warehouse ID
- warehouse_name: Filter by warehouse name (partial match)
- quantity_min, quantity_max: Filter by quantity range
- has_stock: Filter records with/without stock (true/false)
- below_minimum: Filter records below minimum stock (true/false)
- search: Search across product and warehouse

STOCK MOVEMENTS
---------------
GET    /api/stock-movements/              - List stock movements
POST   /api/stock-movements/              - Create stock movement
GET    /api/stock-movements/{id}/         - Retrieve stock movement
POST   /api/stock-movements/adjustment/   - Create stock adjustment
GET    /api/stock-movements/summary/      - Get movement summary for date range
GET    /api/stock-movements/recent/       - Get recent movements (last 24h)

Filters for stock movements:
- movement_type: Filter by type (IN, OUT, TRANSFER)
- reason: Filter by reason (sale, purchase, loss, return, adjustment, transfer)
- product: Filter by product ID
- product_name: Filter by product name (partial match)
- product_sku: Filter by product SKU (partial match)
- category: Filter by category ID
- warehouse: Filter by warehouse ID
- warehouse_name: Filter by warehouse name (partial match)
- from_warehouse, to_warehouse: Filter transfers by warehouses
- user: Filter by user ID
- user_email: Filter by user email (partial match)
- quantity_min, quantity_max: Filter by quantity range
- date_from, date_to: Filter by date range
- date: Filter by specific date
- reference_document: Filter by reference document (partial match)
- search: Search across product, SKU, reference, notes

REPORTS
-------
GET    /api/reports/inventory_valuation/  - Get current inventory valuation by warehouse
GET    /api/reports/stock_alerts/         - Get all stock alerts (low stock, out of stock)
GET    /api/reports/movement_report/      - Get movement report for date range
GET    /api/reports/category_analysis/    - Get analysis by category
GET    /api/reports/top_products/         - Get top products by metric

Query params for reports:
- date_from, date_to: Date range for reports
- metric: Metric for top products (stock_value, stock_quantity, price)
- limit: Number of results for top products (default: 10)

COMMON QUERY PARAMETERS
-----------------------
- page: Page number for pagination
- page_size: Number of items per page
- search: Global search across relevant fields
- ordering: Order by field (prefix with - for descending)
  Examples: ordering=name, ordering=-created_at
"""
