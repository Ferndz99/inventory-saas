from django.conf import settings

from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.decorators import (
    api_view,
    permission_classes,
)

from djoser.views import UserViewSet
from djoser.serializers import UserSerializer

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
    inline_serializer
)

from accounts.constants import DocTags
from accounts.serializers import (
    AccountLoginSerializer,
    CustomTokenObtainPairSerializer,
    ProblemDetailsSerializer,
    AccountLoginResponseSerializer,
    DetailResponseSerializer,
)


@extend_schema_view(
    create=extend_schema(
        tags=[DocTags.TAG_ACCOUNT],
        summary="Create a new account",
        description="Endpoint to create a new account.",
        responses={
            status.HTTP_201_CREATED: OpenApiResponse(
                description="Account created successfully",
                response=UserSerializer,
                examples=[
                    OpenApiExample(
                        name="AccountCreated",
                        summary="Successful account creation",
                        value={"id": 1, "email": "new_user@email.com"},
                    )
                ],
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="ValidationErrorMissingFields",
                        summary="Example of missing required fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {
                                    "field": "email",
                                    "message": "This field is required.",
                                },
                                {
                                    "field": "password",
                                    "message": "This field is required.",
                                },
                                {
                                    "field": "re_password",
                                    "message": "This field is required.",
                                },
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    list=extend_schema(
        tags=[DocTags.TAG_ADMIN_ACCOUNT],
        summary="List accounts",
        description="Retrieve a paginated list of all accounts.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="List of accounts retrieved successfully.",
                response=UserSerializer(many=True),
                examples=[
                    OpenApiExample(
                        name="AccountList",
                        summary="Paginated list of accounts",
                        value={
                            "count": 2,
                            "next": None,
                            "previous": None,
                            "results": [
                                {"id": 2, "email": "user2@email.com"},
                                {"id": 1, "email": "user1@email.com"},
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    retrieve=extend_schema(
        tags=[DocTags.TAG_ADMIN_ACCOUNT],
        summary="Retrieve account details",
        description="Fetch a specific account by ID.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Account details",
                response=UserSerializer,
                examples=[
                    OpenApiExample(
                        name="AccountDetail",
                        summary="Details for a single account",
                        value={"id": 1, "email": "user1@email.com"},
                    )
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Account not found",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Account not found",
                        value={
                            "type": "https://httpstatuses.com/404",
                            "status": 404,
                            "title": "Not Found",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "The requested resource was not found.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/some_id",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    update=extend_schema(
        tags=[DocTags.TAG_ADMIN_ACCOUNT],
        summary="Update an account",
        description="Update email or profile fields for a specific user.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Account updated successfully",
                response=UserSerializer,
                examples=[
                    OpenApiExample(
                        "Account updated",
                        value={"id": 5, "email": "updated_email@example.com"},
                    )
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Account not found",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Account not found",
                        value={
                            "type": "https://httpstatuses.com/404",
                            "status": 404,
                            "title": "Not Found",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "The requested resource was not found.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/some_id",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    partial_update=extend_schema(
        tags=[DocTags.TAG_ADMIN_ACCOUNT],
        summary="Partially update an account",
        description="Partially update email or profile fields for a user.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Account updated successfully",
                response=UserSerializer,
                examples=[
                    OpenApiExample(
                        "Account updated",
                        value={"id": 5, "email": "updated_email@example.com"},
                    )
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Account not found",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Account not found",
                        value={
                            "type": "https://httpstatuses.com/404",
                            "status": 404,
                            "title": "Not Found",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "The requested resource was not found.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/some_id",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    destroy=extend_schema(
        tags=[DocTags.TAG_ADMIN_ACCOUNT],
        summary="Delete an account",
        description="Delete a specific account by ID.",
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Account deleted successfully"
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation Error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/1/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {
                                    "field": "current_password",
                                    "message": "This field is required.",
                                }
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Account not found",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Account not found",
                        value={
                            "type": "https://httpstatuses.com/404",
                            "status": 404,
                            "title": "Not Found",
                            "instance": "/api/v1/accounts/some_id/",
                            "detail": "The requested resource was not found.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/some_id",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    activation=extend_schema(
        tags=[DocTags.TAG_ACCOUNT_ACTIVATION],
        summary="Activate account",
        description=(
            "Activate an account using the unique UID and token sent via email. "
        ),
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Account successfully activated. No content returned."
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation Error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/activation/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {"field": "uid", "message": "This field is required."},
                                {
                                    "field": "token",
                                    "message": "This field is required.",
                                },
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/activation/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    resend_activation=extend_schema(
        tags=[DocTags.TAG_ACCOUNT_ACTIVATION],
        summary="Resend activation email",
        description=(
            "Resend the activation email if the account has not been activated yet."
        ),
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Activation email resent successfully."
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation Error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/resend_activation/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {"field": "email", "message": "This field is required."}
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/resend_activation/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    reset_password=extend_schema(
        tags=[DocTags.TAG_PASSWORD_RESET],
        summary="Request password reset",
        description=(
            "Send a password reset email containing a unique token to the user's email address."
        ),
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Password reset email sent successfully."
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation Error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/reset_password/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {"field": "email", "message": "This field is required."}
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/resend_activation/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    reset_password_confirm=extend_schema(
        tags=[DocTags.TAG_PASSWORD_RESET],
        summary="Confirm password reset",
        description=(
            "Confirm password reset by providing the UID, token, and new password values."
        ),
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Password reset successfully completed."
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation Error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/reset_password_confirm/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {"field": "uid", "message": "This field is required."},
                                {
                                    "field": "token",
                                    "message": "This field is required.",
                                },
                                {
                                    "field": "new_password",
                                    "message": "This field is required.",
                                },
                                {
                                    "field": "re_new_password",
                                    "message": "This field is required.",
                                },
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/resend_activation/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
    set_password=extend_schema(
        tags=[DocTags.TAG_PASSWORD_RESET],
        summary="Set a new password",
        description=(
            "Allow authenticated users to change their password by providing the current password, "
            "and the new password (with confirmation)."
        ),
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Password successfully updated."
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation Error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/set_password/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {
                                    "field": "new_password",
                                    "message": "This field is required.",
                                },
                                {
                                    "field": "re_new_password",
                                    "message": "This field is required.",
                                },
                                {
                                    "field": "current_password",
                                    "message": "This field is required.",
                                },
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/set_password/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/set_password/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    ),
)
class CustomAccountViewSet(UserViewSet):
    """UserViewSet with extended documentation for OpenAPI/Swagger."""

    def set_username(self, request, *args, **kwargs):
        raise NotImplementedError("This endpoint is disabled.")

    def reset_username(self, request, *args, **kwargs):
        raise NotImplementedError("This endpoint is disabled.")

    def reset_username_confirm(self, request, *args, **kwargs):
        raise NotImplementedError("This endpoint is disabled.")

    @extend_schema(
        tags=[DocTags.TAG_ACCOUNT],
        methods=["GET"],
        summary="Retrieve current account",
        description=("Retrieve the information of the currently authenticated user"),
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Current account data retrieved successfully",
                response=UserSerializer,
                examples=[
                    OpenApiExample("ok", value={"id": 2, "email": "admin@email.com"})
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/me/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/me/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    )
    @extend_schema(
        tags=[DocTags.TAG_ACCOUNT],
        methods=["PUT", "PATCH"],
        summary="Update current account",
        description="Update account data.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Account data",
                response=UserSerializer,
                examples=[
                    OpenApiExample("ds", value={"id": 2, "email": "admin@email.com"})
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/me/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/me/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    )
    @extend_schema(
        tags=[DocTags.TAG_ACCOUNT],
        summary="Delete current account",
        description="Delete the current authenticated account. No request body required.",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: OpenApiResponse(
                description="Account deleted succesfully"
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Validation Error",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing fields",
                        value={
                            "type": "https://httpstatuses.com/400",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "/api/v1/accounts/me/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {
                                    "field": "current_password",
                                    "message": "This field is required.",
                                }
                            ],
                        },
                    )
                ],
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Authentication credentials were not provided or are invalid.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        name="Missing Authorization header",
                        value={
                            "type": "https://httpstatuses.com/401",
                            "status": 401,
                            "title": "Unauthorized",
                            "instance": "/api/v1/accounts/me/",
                            "detail": "Authentication credentials were not provided.",
                        },
                    )
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "/api/v1/accounts/me/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    )
    @action(["get", "put", "patch", "delete"], detail=False)
    def me(self, request, *args, **kwargs):
        self.get_object = self.get_instance  # type: ignore

        if request.method == "GET":
            return self.retrieve(request, *args, **kwargs)
        elif request.method == "PUT":
            return self.update(request, *args, **kwargs)
        elif request.method == "PATCH":
            return self.partial_update(request, *args, **kwargs)
        elif request.method == "DELETE":
            return self.destroy(request, *args, **kwargs)


class AccountLoginAPIView(APIView):
    """
    API endpoint for user login.
    Validates credentials and returns a JWT access token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=[DocTags.TAG_AUTHENTICATION],
        summary="User login",
        description="Validates credentials and returns a JWT access token. Sets refresh token in a secure cookie.",
        request=AccountLoginSerializer,
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Successful login, returns access token.",
                response=AccountLoginResponseSerializer,
                examples=[
                    OpenApiExample(
                        "Successful Login",
                        summary="Successful Login Example",
                        description="Example response for a successful login.",
                        value={"access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
                        status_codes=["200"],
                    )
                ],
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid credentials or validation error.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Invalid Credentials",
                        summary="Invalid Credentials Example",
                        description="Example response for invalid login credentials.",
                        value={
                            "type": "https://example.com/probs/authentication",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "api/v1/auth/login/",
                            "detail": "Account not found with the given credentials.",
                        },
                        status_codes=["400"],
                    ),
                    OpenApiExample(
                        "Validation Error",
                        summary="Validation Error Example",
                        description="Example response for validation errors.",
                        value={
                            "type": "https://example.com/probs/validation",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "api/v1/auth/login/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {"field": "email", "message": "Email is required."},
                                {
                                    "field": "password",
                                    "message": "Password is required.",
                                },
                            ],
                        },
                        status_codes=["400"],
                    ),
                    OpenApiExample(
                        "Invalid Email Format",
                        summary="Invalid Email Format Example",
                        description="Example response for invalid email format.",
                        value={
                            "type": "https://example.com/probs/validation",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "api/v1/auth/login/",
                            "detail": "The submitted data failed validation.",
                            "errors": [
                                {
                                    "field": "email",
                                    "message": "Please enter a valid email address.",
                                }
                            ],
                        },
                    ),
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during login.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during login.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "api/v1/auth/login/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    )
    def post(self, request):
        login_serializer = AccountLoginSerializer(
            data=request.data, context={"request": request}
        )

        login_serializer.is_valid(raise_exception=True)
        user = login_serializer.validated_data["user"]  # type: ignore

        refresh = CustomTokenObtainPairSerializer.get_token(user)

        response = Response(
            {"access": str(refresh.access_token)},  # type: ignore
            status=status.HTTP_200_OK,  # type: ignore
        )

        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=7 * 24 * 60 * 60,  # 7 días
            path="/",
        )

        return response


class TokenRefreshView(APIView):
    """
    View to refresh the access token using the refresh token from the cookie.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=[DocTags.TAG_AUTHENTICATION],
        summary="Refresh access token",
        request=None,
        description="Obtains a new access token using the refresh token stored in an HTTP-only cookie.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="New access token obtained successfully.",
                response=AccountLoginResponseSerializer,
                examples=[
                    OpenApiExample(
                        "Successful Token Refresh",
                        summary="Successful Token Refresh Example",
                        description="Example response for a successful token refresh.",
                        value={"access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
                        status_codes=["200"],
                    )
                ],
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid or missing refresh token.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing Refresh Token",
                        summary="Missing Refresh Token Example",
                        description="Example response when refresh token is missing.",
                        value={
                            "type": "https://example.com/probs/authentication",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "api/v1/auth/refresh/",
                            "detail": "Refresh token not found in cookies.",
                        },
                        status_codes=["400"],
                    ),
                    OpenApiExample(
                        "Invalid Refresh Token",
                        summary="Invalid Refresh Token Example",
                        description="Example response for invalid refresh token.",
                        value={
                            "type": "https://example.com/probs/authentication",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "api/v1/auth/refresh/",
                            "detail": "Invalid or expired refresh token.",
                        },
                        status_codes=["400"],
                    ),
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during logout.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during logout.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "api/v1/auth/refresh/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    )
    def post(self, request):
        """
        Obtain a new access token using the cookie's refresh token.
        """

        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            raise ValidationError({"error": ["Refresh token not found in cookies."]})

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            return Response({"access": access_token}, status=status.HTTP_200_OK)

        except TokenError:
            raise ValidationError({"error": ["Invalid or expired refresh token."]})
        except Exception as exc:
            raise ValidationError({"error": [f"Unexpected refresh error: {str(exc)}"]})


class AccountLogoutView(APIView):
    """
    View to logout by removing the refresh token cookie.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=[DocTags.TAG_AUTHENTICATION],
        summary="User logout",
        request=None,
        description="Logs out the user by blacklisting the refresh token and deleting the cookie.",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                description="Successful logout.",
                response=DetailResponseSerializer,
                examples=[
                    OpenApiExample(
                        "Successful Logout",
                        summary="Successful Logout Example",
                        description="Example response for a successful logout.",
                        value={"detail": "Logged out successfully."},
                        status_codes=["200"],
                    )
                ],
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="Invalid or missing refresh token.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Missing Refresh Token",
                        summary="Missing Refresh Token Example",
                        description="Example response when refresh token is missing.",
                        value={
                            "type": "https://example.com/probs/authentication",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "api/v1/auth/logout/",
                            "detail": "Refresh token not found in cookies.",
                        },
                        status_codes=["400"],
                    ),
                    OpenApiExample(
                        "Invalid Refresh Token",
                        summary="Invalid Refresh Token Example",
                        description="Example response for invalid refresh token.",
                        value={
                            "type": "https://example.com/probs/authentication",
                            "status": 400,
                            "title": "Validation Error",
                            "instance": "api/v1/auth/logout/",
                            "detail": "Invalid or expired refresh token.",
                        },
                        status_codes=["400"],
                    ),
                ],
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                description="Server error during logout.",
                response=ProblemDetailsSerializer,
                examples=[
                    OpenApiExample(
                        "Server Error",
                        summary="Server Error Example",
                        description="Example response for server errors during logout.",
                        value={
                            "type": "https://example.com/probs/server-error",
                            "status": 500,
                            "title": "Internal Server Error",
                            "instance": "api/v1/auth/logout/",
                            "detail": "An unexpected error occurred. Please try again later.",
                        },
                        status_codes=["500"],
                    )
                ],
            ),
        },
    )
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            raise ValidationError({"error": ["Refresh token not found in cookies."]})

        try:
            refresh = RefreshToken(refresh_token)

            refresh.blacklist()

            response = Response(
                {"detail": "Logged out successfully."},
                status=status.HTTP_200_OK,
            )

            response.delete_cookie(
                key="refresh_token",
                samesite="Lax",
                path="/",  # type: ignore
            )

            return response

        except TokenError:
            raise ValidationError({"error": ["Invalid or expired refresh token."]})

        except Exception as exc:
            raise ValidationError({"error": [f"Unexpected logout error: {str(exc)}"]})


@extend_schema(
    tags=[DocTags.TAG_AUTHENTICATION],
    summary="Verificar validez del token",
    description=(
        "Valida si el token de acceso JWT enviado en el encabezado Authorization "
        "es válido y no ha expirado. "
        "Este endpoint es utilizado por el frontend para proteger rutas privadas "
        "como el dashboard y confirmar una sesión activa."
    ),
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="VerifyTokenResponse",
            fields={
                "valid": serializers.BooleanField(
                    help_text="Indica si el token es válido"
                ),
                "user_id": serializers.IntegerField(
                    help_text="ID del usuario autenticado"
                ),
                "email": serializers.EmailField(
                    help_text="Email del usuario autenticado"
                ),
            },
        ),
        status.HTTP_401_UNAUTHORIZED: inline_serializer(
            name="VerifyTokenError401",
            fields={
                "type": serializers.CharField(),
                "title": serializers.CharField(),
                "status": serializers.IntegerField(),
                "detail": serializers.CharField(),
                "instance": serializers.CharField(),
            },
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: inline_serializer(
            name="VerifyTokenError500",
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
            "Token válido",
            status_codes=["200"],
            value={
                "valid": True,
                "user_id": 12,
                "email": "usuario@inventorycl.com",
            },
        ),
        OpenApiExample(
            "Token expirado o inválido",
            status_codes=["401"],
            value={
                "type": "/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "El token es inválido o ha expirado.",
                "instance": "/api/v1/auth/verify-token/",
            },
            description="Se retorna cuando el token JWT no es válido o ha expirado.",
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verify_token(request):
    return Response(
        {
            "valid": True,
            "user_id": request.user.id,
            "email": request.user.email,
        },
        status=status.HTTP_200_OK,
    )
