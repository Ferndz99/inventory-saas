from django.urls import path, include

from rest_framework.routers import DefaultRouter

from accounts.views import (
    CustomAccountViewSet,
    AccountLoginAPIView,
    TokenRefreshView,
    AccountLogoutView,
)


router = DefaultRouter()
router.register(r"accounts", CustomAccountViewSet, basename="account")

urlpatterns = [
    path("auth/login/", AccountLoginAPIView.as_view(), name="account-login"),
    path("auth/logout/", AccountLogoutView.as_view(), name="account-logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("", include(router.urls)),
]
