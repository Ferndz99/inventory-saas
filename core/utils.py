import re
from django.db.models.deletion import ProtectedError


def build_rfc9457_error(status_code, title, instance, detail=None, errors=None):
    response = {
        "type": f"https://httpstatuses.com/{status_code}",
        "status": status_code,
        "title": title,
        "instance": instance,
    }

    if detail is not None:
        response["detail"] = detail

    if errors is not None:
        response["errors"] = errors

    return response


def flatten_errors(data, parent=""):
    """
    Aplana errores anidados de DRF: dict, list, string.
    """
    flat = []

    if isinstance(data, dict):
        for field, value in data.items():
            full = f"{parent}.{field}" if parent else field
            flat.extend(flatten_errors(value, full))

    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                flat.extend(flatten_errors(item, parent))
            else:
                flat.append(
                    {
                        "field": parent or "non_field_errors",
                        "message": str(item),
                    }
                )

    else:
        flat.append(
            {
                "field": parent or "non_field_errors",
                "message": str(data),
            }
        )

    return flat


def parse_integrity_error(exc):
    msg = str(exc)

    if isinstance(exc, ProtectedError):
        protected_objects = list(exc.protected_objects)

        # Construye errores detallados si quieres
        errors = []

        for obj in protected_objects:
            errors.append(
                {
                    "field": "non_field_errors",
                    "message": f"This object is referenced by {obj._meta.model_name} '{obj}'.",
                }
            )

        # Respuesta estandarizada
        return (
            "Cannot delete object because other resources depend on it.",
            errors if errors else [{"field": "non_field_errors", "message": msg}],
        )

    # UNIQUE constraint
    unique = re.search(r"UNIQUE constraint failed: (\w+)\.(\w+)", msg)
    if unique:
        table, field = unique.groups()
        return (
            "Unique constraint violation.",
            [
                {
                    "field": field,
                    "message": f"A record with this {field} already exists.",
                }
            ],
        )

    # FOREIGN KEY constraint
    if "FOREIGN KEY constraint failed" in msg:
        return (
            "Foreign key constraint violation.",
            [
                {
                    "field": "non_field_errors",
                    "message": "Referenced object does not exist.",
                }
            ],
        )

    # NOT NULL constraint
    not_null = re.search(r"NOT NULL constraint failed: (\w+)\.(\w+)", msg)
    if not_null:
        table, field = not_null.groups()
        return (
            "Required field missing.",
            [{"field": field, "message": "This field is required."}],
        )

    # fallback
    return "Database integrity error.", [{"field": "non_field_errors", "message": msg}]
