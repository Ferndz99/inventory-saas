from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.utils.encoding import force_str

from rest_framework import status

from drf_spectacular.utils import OpenApiResponse, OpenApiExample

from inventory.serializers import AccountProblemDetailsSerializer

import logging

logger = logging.getLogger("app")


def get_doc_url(
    basename: str,
    action_name: str | None = None,
    is_detail: bool = False,
    search_field: str = "pk",
) -> str:
    """
    basename: El 'basename' definido en el router (ej: 'report', 'globalattribute')
    action_name: Nombre de la función @action o acciones estándar (list, retrieve, etc.)
    is_detail: Si la URL requiere un ID
    """

    standard_actions = {
        "list": "list",
        "create": "list",
        "retrieve": "detail",
        "update": "detail",
        "partial_update": "detail",
        "destroy": "detail",
    }

    # 2. Determinar el sufijo real
    if action_name in standard_actions:
        suffix = standard_actions[action_name]
    elif action_name:
        suffix = action_name.replace("_", "-")
    else:
        suffix = "detail" if is_detail else "list"

    url_name = f"{basename}-{suffix}"

    actual_is_detail = is_detail or suffix == "detail"
    kwargs = {search_field: "id"} if actual_is_detail else None

    try:
        return reverse_lazy(url_name, kwargs=kwargs)
    except Exception:
        path = f"/api/v1/{basename}/"
        if actual_is_detail:
            path += "id/"
        return path


def error_401(basename: str, action: str | None = None, is_detail: bool = False):
    instance_path = get_doc_url(basename, action, is_detail)
    return {
        status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
            description="Authentication credentials were not provided or are invalid.",
            response=AccountProblemDetailsSerializer,
            examples=[
                OpenApiExample(
                    "Missing Authorization header",
                    value={
                        "type": "https://httpstatuses.com/401",
                        "status": 401,
                        "title": "Unauthorized",
                        "instance": instance_path,
                        "detail": "Authentication credentials were not provided.",
                    },
                )
            ],
        )
    }


def error_403(basename: str, action: str | None = None, is_detail: bool = False):
    instance_path = get_doc_url(basename, action, is_detail)
    return {
        status.HTTP_403_FORBIDDEN: OpenApiResponse(
            description="Forbidden - Insufficient permissions",
            response=AccountProblemDetailsSerializer,
            examples=[
                OpenApiExample(
                    "Forbidden",
                    value={
                        "type": "https://httpstatuses.com/403",
                        "status": 403,
                        "title": "Forbidden",
                        "instance": instance_path,
                        "detail": "You do not have permission to perform this action.",
                    },
                )
            ],
        )
    }


def error_404(basename: str, action: str | None = None, is_detail: bool = False):
    instance_path = get_doc_url(basename, action, is_detail)
    return {
        status.HTTP_404_NOT_FOUND: OpenApiResponse(
            description="Resource not found",
            response=AccountProblemDetailsSerializer,
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "type": "https://httpstatuses.com/404",
                        "status": 404,
                        "title": "Not Found",
                        "instance": instance_path,
                        "detail": "The requested resource was not found.",
                    },
                )
            ],
        )
    }


def error_400(basename: str, action: str | None = None, is_detail: bool = False):
    instance_path = get_doc_url(basename, action, is_detail)
    return {
        status.HTTP_400_BAD_REQUEST: OpenApiResponse(
            description="Bad Request - Invalid data provided",
            response=AccountProblemDetailsSerializer,
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "type": "https://httpstatuses.com/400",
                        "status": 400,
                        "title": "Bad Request",
                        "instance": instance_path,
                        "detail": "Invalid data provided.",
                        "errors": [
                            {
                                "field": "field",
                                "message": "This field is required.",
                            },
                        ],
                    },
                )
            ],
        )
    }


def error_500(basename: str, action: str | None = None, is_detail: bool = False):
    instance_path = get_doc_url(basename, action, is_detail)
    return {
        status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
            description="Internal Server Error",
            response=AccountProblemDetailsSerializer,
            examples=[
                OpenApiExample(
                    "Internal Server Error",
                    value={
                        "type": "https://httpstatuses.com/500",
                        "status": 500,
                        "title": "Internal Server Error",
                        "instance": instance_path,
                        "detail": "An unexpected error occurred. Please try again later.",
                    },
                )
            ],
        )
    }


def success_200(serializer_class, description: str | None = None, many=False):
    if description is None:
        description = (
            "Listing obtained successfully" if many else "Successful operation"
        )

    response_schema = serializer_class(many=True) if many else serializer_class

    return {
        status.HTTP_200_OK: OpenApiResponse(
            description=description, response=response_schema
        )
    }


def success_201(serializer_class, description="Resource created successfully"):
    return {
        status.HTTP_201_CREATED: OpenApiResponse(
            description=description, response=serializer_class
        )
    }


def success_204(description="Resource successfully removed"):
    return {status.HTTP_204_NO_CONTENT: OpenApiResponse(description=description)}
