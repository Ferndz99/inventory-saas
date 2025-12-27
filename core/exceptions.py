"""
Custom exception handler con formato RFC 9457.
Ubicación sugerida: core/exceptions.py
"""

import logging

from django.db import IntegrityError
from django.http import Http404
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
    ObjectDoesNotExist,
)

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnList
from rest_framework.exceptions import (
    ValidationError,
    AuthenticationFailed,
    PermissionDenied,
    NotFound,
    MethodNotAllowed,
    NotAuthenticated,
    Throttled,
    ParseError,
)


from core.utils import build_rfc9457_error, flatten_errors, parse_integrity_error

logger = logging.getLogger("app")


def RFC9457_exception_handler(exc, context):
    logger.debug(exc)

    request = context.get("request")
    instance = request.path if request else "unknown"

    response = exception_handler(exc, context)
    # ================================================================
    # CASO A: Excepciones que DRF NO maneja (response es None)
    # ================================================================
    if response is None:
        # Django ValidationError ─ (models/forms)
        if isinstance(exc, DjangoValidationError):
            errors = []

            if hasattr(exc, "message_dict"):
                for field, msgs in exc.message_dict.items():
                    for msg in msgs:
                        errors.append({"field": field, "message": msg})
            else:
                for msg in exc.messages:
                    errors.append({"field": "non_field_errors", "message": msg})

            data = build_rfc9457_error(
                status_code=400,
                title="Validation Error",
                instance=instance,
                detail="The submitted data failed validation.",
                errors=errors,
            )

            return Response(data, status=400, content_type="application/problem+json")

        # IntegrityError ─ SQL
        if isinstance(exc, IntegrityError):
            detail, errors = parse_integrity_error(exc)

            data = build_rfc9457_error(
                status_code=400,
                title="Bad Request",
                instance=instance,
                detail=detail,
                errors=errors,
            )

            return Response(data, status=400, content_type="application/problem+json")

        # ObjectDoesNotExist
        if isinstance(exc, ObjectDoesNotExist):
            data = build_rfc9457_error(
                status_code=404,
                title="Not Found",
                instance=instance,
                detail="The requested resource does not exist.",
            )
            return Response(data, status=404, content_type="application/problem+json")

        # ParseError (json inválido)
        if isinstance(exc, ParseError):
            data = build_rfc9457_error(
                status_code=400,
                title="Malformed Request",
                instance=instance,
                detail="Malformed JSON.",
            )
            return Response(data, status=400, content_type="application/problem+json")

        # ERROR 500 fallback
        data = build_rfc9457_error(
            status_code=500,
            title="Internal Server Error",
            instance=instance,
            detail="An unexpected error occurred. Please try again later.",
        )
        return Response(data, status=500, content_type="application/problem+json")

    # ================================================================
    # CASO B: Excepciones manejadas por DRF (response existe)
    # ================================================================

    status_code = response.status_code
    status_text = response.status_text
    data_original = response.data

    if isinstance(data_original, (list, ReturnList)):
        data = build_rfc9457_error(
            status_code=400,
            title="Validation Error",
            instance=instance,
            detail="One or more items failed validation.",
            errors=data_original,
        )
        return Response(
            data,
            status=400,
            content_type="application/problem+json",
        )

    # ================================================================
    # 🔹 CASO NORMAL (dict)
    # ================================================================
    data_original = data_original or {}

    # Unificar extracción de detail
    detail = data_original.get("detail", None)
    if isinstance(detail, list):
        detail = detail[0] if detail else None

    # Http404 / NotFound
    if isinstance(exc, (Http404, NotFound)):
        data = build_rfc9457_error(
            status_code=404,
            title="Not Found",
            instance=instance,
            detail="The requested resource was not found.",
        )
        return Response(data, status=404, content_type="application/problem+json")

    # AuthenticationFailed / NotAuthenticated
    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        data = build_rfc9457_error(
            status_code=status_code,
            title=status_text,
            instance=instance,
            detail=detail
            or "Authentication credentials were not provided or are invalid.",
        )
        return Response(
            data, status=status_code, content_type="application/problem+json"
        )

    # PermissionDenied
    if isinstance(exc, PermissionDenied):
        data = build_rfc9457_error(
            status_code=403,
            title="Forbidden",
            instance=instance,
            detail=detail or "You do not have permission to perform this action.",
        )
        return Response(data, status=403, content_type="application/problem+json")

    # MethodNotAllowed
    if isinstance(exc, MethodNotAllowed):
        data = build_rfc9457_error(
            status_code=405,
            title="Method Not Allowed",
            instance=instance,
            detail=f"Method '{request.method}' not allowed.",
        )
        return Response(data, status=405, content_type="application/problem+json")

    # Throttled
    if isinstance(exc, Throttled):
        wait = exc.wait
        detail = (
            f"Request was throttled. Expected available in {wait} seconds."
            if wait
            else "Too many requests."
        )
        data = build_rfc9457_error(
            status_code=429,
            title="Too Many Requests",
            instance=instance,
            detail=detail,
        )
        return Response(data, status=429, content_type="application/problem+json")

    # ValidationError (DRF)
    if isinstance(exc, ValidationError):
        errors = flatten_errors(data_original)

        if len(errors) == 1 and errors[0]["field"] in ("error", "non_field_errors"):
            detail_message = errors[0]["message"]

            data = build_rfc9457_error(
                status_code=400,
                title="Validation Error",
                instance=instance,
                detail=detail_message,
            )

            return Response(
                data,
                status=400,
                content_type="application/problem+json",
            )

        data = build_rfc9457_error(
            status_code=400,
            title="Validation Error",
            instance=instance,
            detail="The submitted data failed validation.",
            errors=errors,
        )
        return Response(data, status=400, content_type="application/problem+json")

    # Errores genéricos basados en data (sin tipo específico)
    errors = flatten_errors(data_original) if isinstance(data_original, dict) else None

    data = build_rfc9457_error(
        status_code=status_code,
        title=status_text,
        instance=instance,
        detail=detail,
        errors=errors,
    )

    return Response(data, status=status_code, content_type="application/problem+json")
