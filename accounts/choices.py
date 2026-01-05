from django.db import models


class RoleAccount(models.TextChoices):
    ADMIN = "admin"
    MANAGER = "manager"
    SELLER = "seller"
    VIEWER = "viewer"
