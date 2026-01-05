from rest_framework import permissions


class IsCompanyMember(permissions.BasePermission):
    """
    Permission to check if user belongs to a company.
    All authenticated users with a company can access.
    """

    message = "You must belong to a company to access this resource."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "company")
            and request.user.company is not None
        )

    def has_object_permission(self, request, view, obj):
        """
        Verify object belongs to user's company.
        """
        # If object has a company attribute
        if hasattr(obj, "company"):
            return obj.company == request.user.company

        # If object has a product with company (like StockRecord)
        if hasattr(obj, "product") and hasattr(obj.product, "company"):
            return obj.product.company == request.user.company

        # If object has stock_record.product.company (like StockMovement)
        if hasattr(obj, "stock_record"):
            if hasattr(obj.stock_record, "product"):
                return obj.stock_record.product.company == request.user.company

        return False


class IsAdminUser(permissions.BasePermission):
    """
    Permission for admin users only.
    Checks if user has 'admin' role.
    """

    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "role")
            and request.user.role == "admin"
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission that allows:
    - Admins: full access (read + write)
    - Others: read-only access
    """

    def has_permission(self, request, view):
        # Allow read operations for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        # Write operations only for admins
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "role")
            and request.user.role == "admin"
        )

    def has_object_permission(self, request, view, obj):
        # Read operations for all
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write operations only for admins
        return (
            request.user
            and hasattr(request.user, "role")
            and request.user.role == "admin"
        )


class IsSameCompany(permissions.BasePermission):
    """
    Permission to verify that related objects belong to the same company.
    Useful for validating relationships between objects.
    """

    message = "All related objects must belong to the same company."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if not hasattr(request.user, "company"):
            return False

        user_company = request.user.company

        # Validate based on object type
        if hasattr(obj, "company"):
            return obj.company == user_company

        return False


class CanModifyStock(permissions.BasePermission):
    """
    Permission to modify stock.
    Both admins and sellers can modify stock.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "role")
            and request.user.role in ["admin", "seller"]
        )


class CanViewReports(permissions.BasePermission):
    """
    Permission to view reports.
    Only admins can view reports.
    """

    message = "Only administrators can view reports."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "role")
            and request.user.role == "admin"
        )
