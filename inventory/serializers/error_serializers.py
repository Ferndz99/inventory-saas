from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):
    field = serializers.CharField(help_text="Nombre del campo que produjo el error")
    message = serializers.CharField(help_text="Mensaje de error correspondiente")

    class Meta:
        ref_name = "CatalogErrorDetails"


class AccountProblemDetailsSerializer(serializers.Serializer):
    type = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="URL con información del código de estado HTTP",
    )
    status = serializers.IntegerField(required=True, help_text="Código de estado HTTP")
    title = serializers.CharField(required=True, help_text="Título resumido del error")
    detail = serializers.CharField(
        required=True, help_text="Descripción detallada del error"
    )
    instance = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Ruta o endpoint donde ocurrió el error",
    )
    errors = ErrorDetailSerializer(  # type: ignore
        many=True, required=False, help_text="Lista de errores de validación por campo"
    )
