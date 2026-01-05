from django.db import transaction

from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.core.exceptions import ValidationError

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiExample

from inventory.models import Company, Warehouse
from inventory.utils import error_400, error_401, error_500


@extend_schema(
    tags=["Onboarding"],
    summary="Configuración inicial de empresa (Onboarding)",
    description=(
        "Crea una nueva empresa, asigna al usuario autenticado como administrador y "
        "genera automáticamente los recursos base: una bodega principal, una categoría 'General' "
        "y una plantilla de atributos básica."
    ),
    request=inline_serializer(
        name="SetupCompanyRequest",
        fields={
            "company_name": serializers.CharField(help_text="Nombre legal o comercial"),
            "company_rut": serializers.CharField(
                help_text="Identificador tributario único (RUT/NIT/DNI)"
            ),
        },
    ),
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="SetupCompanyResponse",
            fields={
                "company": inline_serializer(
                    name="SetupCompanyData",
                    fields={
                        "id": serializers.UUIDField(),
                        "name": serializers.CharField(),
                        "rut": serializers.CharField(),
                    },
                ),
                "user": inline_serializer(
                    name="SetupUserData",
                    fields={
                        "id": serializers.UUIDField(),
                        "email": serializers.EmailField(),
                        "company": serializers.UUIDField(),
                        "role": serializers.CharField(),
                    },
                ),
                "warehouse": inline_serializer(
                    name="SetupWarehouseData",
                    fields={
                        "id": serializers.UUIDField(),
                        "name": serializers.CharField(),
                    },
                ),
                "defaults": inline_serializer(
                    name="SetupDefaultsData",
                    fields={
                        "category": serializers.UUIDField(),
                        "template": serializers.UUIDField(),
                    },
                ),
            },
        ),
        status.HTTP_400_BAD_REQUEST: inline_serializer(
            name="SetupError400",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.DictField(
                    child=serializers.ListField(child=serializers.CharField())
                ),
                "instance": serializers.CharField(),
            },
        ),
        status.HTTP_403_FORBIDDEN: inline_serializer(
            name="SetupError403",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.CharField(),
                "instance": serializers.CharField(),
            },
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: inline_serializer(
            name="SetupError500",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.CharField(),
                "instance": serializers.CharField(),
            },
        ),
    },
    examples=[
        OpenApiExample(
            "Error de Validación (RUT Duplicado)",
            status_codes=["400"],
            value={
                "type": "/errors/validation-error",
                "title": "Validation Error",
                "status": 400,
                "detail": {
                    "company_rut": ["Ya existe una empresa registrada con este RUT."]
                },
                "instance": "/api/v1/setup-company/",
            },
        ),
        OpenApiExample(
            "Error de Permiso (Empresa ya vinculada)",
            status_codes=["403"],
            value={
                "type": "/errors/forbidden",
                "title": "Forbidden",
                "status": 403,
                "detail": "El usuario ya está vinculado a una empresa.",
                "instance": "/api/v1/setup-company/",
            },
        ),
    ],
)
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
        # return Response(
        #     {"error": "company_name and company_rut are required"},
        #     status=status.HTTP_400_BAD_REQUEST,
        # )
        raise ValidationError(
            {
                "company_name": "Este campo es requerido",
                "company_rut": "Este campo es requerido",
            }
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


@extend_schema(
    tags=["Onboarding"],
    summary="Progreso del Onboarding",
    description=(
        "Calcula el porcentaje de completitud de la configuración inicial de la empresa. "
        "Verifica hitos clave como creación de productos, carga de stock inicial e invitación de equipo."
    ),
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="OnboardingProgressResponse",
            fields={
                "completed": serializers.FloatField(
                    help_text="Porcentaje de progreso (0-100)"
                ),
                "has_company": serializers.BooleanField(),
                "company_id": serializers.UUIDField(allow_null=True),
                "steps": inline_serializer(
                    name="OnboardingSteps",
                    fields={
                        "create_category": serializers.BooleanField(),
                        "create_template": serializers.BooleanField(),
                        "create_product": serializers.BooleanField(),
                        "add_stock": serializers.BooleanField(),
                        "invite_team": serializers.BooleanField(),
                    },
                ),
                "onboarding_completed": serializers.BooleanField(
                    help_text="Flag de perfil de usuario"
                ),
            },
        ),
        status.HTTP_401_UNAUTHORIZED: inline_serializer(
            name="OnboardingError401",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.CharField(),
                "instance": serializers.CharField(),
            },
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: inline_serializer(
            name="OnboardingError500",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.CharField(),
                "instance": serializers.CharField(),
            },
        ),
    },
    examples=[
        OpenApiExample(
            "Progreso Parcial",
            status_codes=["200"],
            value={
                "completed": 40.0,
                "has_company": True,
                "company_id": "550e8400-e29b-41d4-a716-446655440000",
                "steps": {
                    "create_category": True,
                    "create_template": True,
                    "create_product": False,
                    "add_stock": False,
                    "invite_team": False,
                },
                "onboarding_completed": False,
            },
        ),
        OpenApiExample(
            "Usuario sin Empresa",
            status_codes=["200"],
            value={
                "completed": 0,
                "has_company": False,
                "message": "Please complete company setup first",
            },
            description="Si el usuario no tiene empresa, el progreso es cero pero la respuesta es 200 OK.",
        ),
        OpenApiExample(
            "Error de Autenticación",
            status_codes=["401"],
            value={
                "type": "/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Las credenciales de autenticación no se proveyeron.",
                "instance": "/api/v1/onboarding-progress/",
            },
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def onboarding_progress(request):
    """
    Get onboarding progress for current user's company.
    """
    user = request.user

    if not user.has_company:
        return ValidationError(
            {
                "error": "Please complete company setup first",
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


@extend_schema(
    tags=["Onboarding"],
    summary="Finalizar Onboarding",
    description=(
        "Marca permanentemente el perfil del usuario como 'onboarding completado'. "
        "Este cambio suele utilizarse para ocultar guías de bienvenida o barras de progreso en la interfaz."
    ),
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="CompleteOnboardingSuccess",
            fields={
                "message": serializers.CharField(),
                "onboarding_completed": serializers.BooleanField(),
            },
        ),
        status.HTTP_400_BAD_REQUEST: inline_serializer(
            name="CompleteOnboardingError400",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.DictField(),
                "instance": serializers.CharField(),
            },
        ),
        status.HTTP_401_UNAUTHORIZED: inline_serializer(
            name="CompleteOnboardingError401",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.CharField(),
                "instance": serializers.CharField(),
            },
        ),
    },
    examples=[
        OpenApiExample(
            "Éxito",
            status_codes=["200"],
            value={
                "message": "Onboarding completed successfully",
                "onboarding_completed": True,
            },
        ),
        OpenApiExample(
            "Error: Sin Empresa",
            status_codes=["400"],
            value={
                "type": "/errors/validation-error",
                "title": "Validation Error",
                "status": 400,
                "detail": {"error": "Cannot complete onboarding without a company"},
                "instance": "/api/v1/complete-onboarding/",
            },
            description="Ocurre cuando el usuario intenta finalizar el proceso sin haber creado o unido a una empresa.",
        ),
    ],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_onboarding(request):
    """Mark onboarding as completed for user."""
    user = request.user

    if not user.has_company:
        return ValidationError(
            {"error": "Cannot complete onboarding without a company"}
        )

    user.onboarding_completed = True
    user.save()

    return Response(
        {"message": "Onboarding completed successfully", "onboarding_completed": True}
    )
