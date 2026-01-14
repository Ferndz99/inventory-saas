# management/commands/populate_data.py
# Coloca este archivo en: myapp/management/commands/populate_data.py

from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
import random

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
from inventory.factories import (
    AccountFactory,
    CompanyFactory,
    CategoryFactory,
    GlobalAttributeFactory,
    CustomAttributeFactory,
    TemplateFactory,
    TemplateAttributeFactory,
    ProductFactory,
    WarehouseFactory,
    StockRecordFactory,
    StockMovementFactory,
)


class Command(BaseCommand):
    help = "Pobla la base de datos con datos de prueba realistas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users", type=int, default=5, help="Número de usuarios a crear"
        )
        parser.add_argument(
            "--companies", type=int, default=2, help="Número de empresas a crear"
        )
        parser.add_argument(
            "--products",
            type=int,
            default=50,
            help="Número de productos a crear por empresa",
        )
        parser.add_argument(
            "--movements",
            type=int,
            default=20,
            help="Número de movimientos de stock a crear por producto",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Limpia los datos existentes antes de poblar",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clean"]:
            self.stdout.write(self.style.WARNING("Limpiando datos existentes..."))
            self.clean_data()

        self.stdout.write(self.style.SUCCESS("Iniciando población de datos..."))

        # 1. Crear atributos globales primero (compartidos por todas las empresas)
        self.stdout.write("Creando atributos globales...")
        global_attrs = self.create_global_attributes()
        self.stdout.write(
            self.style.SUCCESS(f"✓ {len(global_attrs)} atributos globales creados")
        )

        # 2. Crear empresas con sus datos
        all_users = []
        for i in range(options["companies"]):
            self.stdout.write(
                f"\n--- Creando empresa {i + 1}/{options['companies']} ---"
            )
            company = CompanyFactory()
            self.stdout.write(f"Empresa: {company.name} ({company.rut})")

            # 3. Crear usuarios para esta empresa
            self.stdout.write(f"Creando usuarios para {company.name}...")
            users = self.create_users_for_company(company, options["users"])
            all_users.extend(users)
            self.stdout.write(self.style.SUCCESS(f"✓ {len(users)} usuarios creados"))

            # 4. Crear categorías para la empresa
            categories = self.create_categories(company)
            self.stdout.write(
                self.style.SUCCESS(f"✓ {len(categories)} categorías creadas")
            )

            # 5. Crear atributos personalizados para la empresa
            custom_attrs = self.create_custom_attributes(company)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {len(custom_attrs)} atributos personalizados creados"
                )
            )

            # 6. Crear plantillas con atributos asignados
            templates = self.create_templates_with_attributes(
                company, global_attrs, custom_attrs
            )
            self.stdout.write(
                self.style.SUCCESS(f"✓ {len(templates)} plantillas creadas")
            )

            # 7. Crear bodegas
            warehouses = self.create_warehouses(company)
            self.stdout.write(
                self.style.SUCCESS(f"✓ {len(warehouses)} bodegas creadas")
            )

            # 8. Crear productos con especificaciones
            products = self.create_products_with_specs(
                company, categories, templates, options["products"]
            )
            self.stdout.write(
                self.style.SUCCESS(f"✓ {len(products)} productos creados")
            )

            # 9. Crear registros de stock
            stock_records = self.create_stock_records(products, warehouses)
            self.stdout.write(
                self.style.SUCCESS(f"✓ {len(stock_records)} registros de stock creados")
            )

            # 10. Crear movimientos de inventario
            movements = self.create_stock_movements(
                stock_records,
                users,  # Usuarios de esta empresa
                options["movements"],
            )
            self.stdout.write(
                self.style.SUCCESS(f"✓ {movements} movimientos de inventario creados")
            )

        self.stdout.write(
            self.style.SUCCESS("\n✅ Población de datos completada exitosamente!")
        )
        self.print_summary()

    def clean_data(self):
        """Elimina todos los datos existentes"""
        StockMovement.objects.all().delete()
        StockRecord.objects.all().delete()
        Product.objects.all().delete()
        Warehouse.objects.all().delete()
        TemplateAttribute.objects.all().delete()
        Template.objects.all().delete()
        CustomAttribute.objects.all().delete()
        GlobalAttribute.objects.all().delete()
        Category.objects.all().delete()
        Company.objects.all().delete()
        from django.contrib.auth import get_user_model

        get_user_model().objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.SUCCESS("✓ Datos limpiados"))

    def create_users_for_company(self, company, count):
        """Crea usuarios asociados a una empresa específica"""
        from accounts.choices import RoleAccount

        users = []

        # Crear al menos un admin
        admin = AccountFactory(
            company=company,
            role=RoleAccount.ADMIN if hasattr(RoleAccount, "ADMIN") else "admin",
            onboarding_completed=True,
            is_staff=True,
        )
        users.append(admin)

        # Crear usuarios regulares
        for _ in range(count - 1):
            user = AccountFactory(
                company=company,
                role=RoleAccount.USER if hasattr(RoleAccount, "USER") else "user",
                onboarding_completed=True,
            )
            users.append(user)

        return users

    def create_global_attributes(self):
        """Crea atributos globales predefinidos"""
        attributes = [
            {
                "name": "Marca",
                "data_type": "text",
                "unit_of_measure": "",
                "description": "Marca del producto",
            },
            {
                "name": "Modelo",
                "data_type": "text",
                "unit_of_measure": "",
                "description": "Modelo del producto",
            },
            {
                "name": "Color",
                "data_type": "text",
                "unit_of_measure": "",
                "description": "Color principal",
            },
            {
                "name": "Peso",
                "data_type": "decimal",
                "unit_of_measure": "kg",
                "description": "Peso del producto",
            },
            {
                "name": "Dimensiones",
                "data_type": "text",
                "unit_of_measure": "cm",
                "description": "Dimensiones (largo x ancho x alto)",
            },
            {
                "name": "Material",
                "data_type": "text",
                "unit_of_measure": "",
                "description": "Material principal",
            },
            {
                "name": "Garantía",
                "data_type": "number",
                "unit_of_measure": "meses",
                "description": "Meses de garantía",
            },
            {
                "name": "País Origen",
                "data_type": "text",
                "unit_of_measure": "",
                "description": "País de origen",
            },
        ]

        created = []
        for attr in attributes:
            obj, _ = GlobalAttribute.objects.get_or_create(
                slug=attr["name"].lower().replace(" ", "-"), defaults=attr
            )
            created.append(obj)

        return created

    def create_categories(self, company):
        """Crea categorías predefinidas para una empresa"""
        category_names = [
            "Electrónica",
            "Ropa y Accesorios",
            "Hogar y Jardín",
            "Deportes",
            "Alimentos",
            "Ferretería",
            "Oficina",
        ]

        return [CategoryFactory(name=name, company=company) for name in category_names]

    def create_custom_attributes(self, company):
        """Crea atributos personalizados para una empresa"""
        attributes = [
            {"name": f"Código Interno {company.name[:10]}", "data_type": "text"},
            {"name": "Ubicación Bodega", "data_type": "text"},
            {"name": "Proveedor Preferido", "data_type": "text"},
            {"name": "Nivel de Rotación", "data_type": "text"},
        ]

        return [
            CustomAttributeFactory(
                name=attr["name"], data_type=attr["data_type"], company=company
            )
            for attr in attributes
        ]

    def create_templates_with_attributes(self, company, global_attrs, custom_attrs):
        """Crea plantillas y asigna atributos"""
        template_configs = [
            {
                "name": "Electrónica General",
                "global_attrs": ["Marca", "Modelo", "Color", "Peso", "Garantía"],
                "custom_attrs": 2,
            },
            {
                "name": "Ropa",
                "global_attrs": ["Marca", "Color", "Material"],
                "custom_attrs": 1,
            },
            {
                "name": "Herramientas",
                "global_attrs": ["Marca", "Modelo", "Peso", "Material", "Garantía"],
                "custom_attrs": 2,
            },
        ]

        templates = []
        for config in template_configs:
            template = TemplateFactory(name=config["name"], company=company)

            # Asignar atributos globales
            order = 0
            for attr_name in config["global_attrs"]:
                global_attr = next(
                    (a for a in global_attrs if a.name == attr_name), None
                )
                if global_attr:
                    TemplateAttributeFactory(
                        template=template,
                        global_attribute=global_attr,
                        custom_attribute=None,
                        is_required=random.choice([True, False]),
                        order=order,
                    )
                    order += 1

            # Asignar atributos personalizados
            for custom_attr in random.sample(
                custom_attrs, min(config["custom_attrs"], len(custom_attrs))
            ):
                TemplateAttributeFactory(
                    template=template,
                    global_attribute=None,
                    custom_attribute=custom_attr,
                    is_required=False,
                    order=order,
                )
                order += 1

            templates.append(template)

        return templates

    def create_warehouses(self, company):
        """Crea bodegas para una empresa"""
        warehouse_names = ["Bodega Principal", "Bodega Secundaria", "Bodega Norte"]

        warehouses = []
        for i, name in enumerate(warehouse_names):
            warehouse = WarehouseFactory(name=name, company=company, is_main=(i == 0))
            warehouses.append(warehouse)

        return warehouses

    def create_products_with_specs(self, company, categories, templates, count):
        """Crea productos con especificaciones basadas en plantillas"""
        products = []

        for _ in range(count):
            category = random.choice(categories)
            template = random.choice(templates)

            # Crear el producto
            product = ProductFactory(
                company=company, category=category, template=template
            )

            # Generar especificaciones basadas en la plantilla
            specs = {}
            for template_attr in template.template_attributes.all():
                attr = template_attr.custom_attribute or template_attr.global_attribute

                # Generar valor según el tipo de dato
                if attr.data_type == "text":
                    value = random.choice(
                        [
                            "Valor A",
                            "Valor B",
                            "Valor C",
                            f"Especial {random.randint(1, 100)}",
                        ]
                    )
                elif attr.data_type == "number":
                    value = str(random.randint(1, 100))
                elif attr.data_type == "decimal":
                    value = str(round(random.uniform(0.1, 50.0), 2))
                elif attr.data_type == "boolean":
                    value = str(random.choice([True, False]))
                else:
                    value = "N/A"

                specs[attr.slug] = value

            product.specifications = specs
            product.save()
            products.append(product)

        return products

    def create_stock_records(self, products, warehouses):
        """Crea registros de stock para productos en bodegas"""
        stock_records = []

        for product in products:
            # Crear stock en 1-2 bodegas aleatorias
            selected_warehouses = random.sample(
                warehouses, random.randint(1, min(2, len(warehouses)))
            )

            for warehouse in selected_warehouses:
                stock_record = StockRecordFactory(
                    product=product,
                    warehouse=warehouse,
                    current_quantity=0,  # Se actualizará con los movimientos
                )
                stock_records.append(stock_record)

        return stock_records

    def create_stock_movements(self, stock_records, users, movements_per_product):
        """Crea movimientos de inventario para los registros de stock"""
        total_movements = 0

        for stock_record in stock_records:
            # Siempre empezar con un movimiento de entrada
            user = random.choice(users)
            initial_quantity = random.uniform(50, 500)

            StockMovementFactory(
                stock_record=stock_record,
                movement_type="IN",
                quantity=initial_quantity,
                resulting_balance=initial_quantity,
                reason="purchase",
                account=user,
                unit_cost=stock_record.product.cost,
            )

            stock_record.current_quantity = initial_quantity
            stock_record.save()
            total_movements += 1

            # Crear movimientos adicionales aleatorios
            for _ in range(random.randint(1, movements_per_product)):
                movement_type = random.choice(["IN", "OUT"])
                quantity = random.uniform(
                    1,
                    stock_record.current_quantity * 0.3
                    if movement_type == "OUT"
                    else 100,
                )

                if movement_type == "OUT" and quantity > stock_record.current_quantity:
                    quantity = stock_record.current_quantity * 0.5

                if quantity > 0:
                    StockMovementFactory(
                        stock_record=stock_record,
                        movement_type=movement_type,
                        quantity=quantity,
                        account=random.choice(users),
                        reason="purchase" if movement_type == "IN" else "sale",
                        unit_cost=stock_record.product.cost
                        if movement_type == "IN"
                        else None,
                    )
                    total_movements += 1

        return total_movements

    def print_summary(self):
        """Imprime un resumen de los datos creados"""
        from django.contrib.auth import get_user_model

        Account = get_user_model()

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("RESUMEN DE DATOS CREADOS"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"Usuarios: {Account.objects.count()}")
        self.stdout.write(f"Empresas: {Company.objects.count()}")
        self.stdout.write(f"Categorías: {Category.objects.count()}")
        self.stdout.write(f"Atributos Globales: {GlobalAttribute.objects.count()}")
        self.stdout.write(
            f"Atributos Personalizados: {CustomAttribute.objects.count()}"
        )
        self.stdout.write(f"Plantillas: {Template.objects.count()}")
        self.stdout.write(
            f"Atributos de Plantilla: {TemplateAttribute.objects.count()}"
        )
        self.stdout.write(f"Productos: {Product.objects.count()}")
        self.stdout.write(f"Bodegas: {Warehouse.objects.count()}")
        self.stdout.write(f"Registros de Stock: {StockRecord.objects.count()}")
        self.stdout.write(f"Movimientos de Inventario: {StockMovement.objects.count()}")
        self.stdout.write("=" * 50 + "\n")

        # Mostrar credenciales de los usuarios admin
        self.stdout.write(self.style.WARNING("Credenciales de Administradores:"))
        from accounts.choices import RoleAccount

        admin_role = RoleAccount.ADMIN if hasattr(RoleAccount, "ADMIN") else "admin"
        admins = Account.objects.filter(role=admin_role)
        for admin in admins:
            self.stdout.write(
                f"  Email: {admin.email} | Password: password123 | Empresa: {admin.company.name if admin.company else 'N/A'}"
            )
        self.stdout.write("")
