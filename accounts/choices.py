from django.db import models


class RoleAccount(models.TextChoices):
    ADMIN = "Admin"
    MANAGER = "Manager"
    SELLER = "Seller"
    VIEWER = "Viewer"
