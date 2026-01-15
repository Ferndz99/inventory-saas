from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

from accounts.choices import RoleAccount
from accounts.managers import AccountManager


class Account(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=10, choices=RoleAccount, null=True)

    # TODO: Relacionar con el modelo Empresa/Company una vez creada la app de negocio.
    # El campo debería definirse como:
    company = models.ForeignKey(
        "inventory.Company",
        on_delete=models.CASCADE,
        related_name="accounts",
        null=True,
    )
    onboarding_completed = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = AccountManager()

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def has_company(self):
        """Check if user has been assigned to a company"""
        return self.company is not None

    @property
    def is_admin(self):
        """Check if user is admin of their company"""
        return self.role == RoleAccount.ADMIN
