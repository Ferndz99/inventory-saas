from django.db import transaction

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from inventory.models import Company, Warehouse


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
