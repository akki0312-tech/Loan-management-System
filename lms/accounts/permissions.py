from rest_framework.permissions import BasePermission


def HasRole(*roles):
    # Dynamically generates a permission class that checks 
    # if a user belongs to one of the specified roles.
    # Usage: permission_classes = [HasRole('ADMIN', 'MANAGER')]
    class RolePermission(BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Super Admin (superuser flag or role) always has access
            if request.user.is_superuser or request.user.role == 'SUPER_ADMIN':
                return True
                
            return request.user.role in roles
            
    return RolePermission

def InGroup(*group_names):
    # Dynamically generates a permission class that checks if a user
    # belongs to one of the specified Django permission groups.
    # Usage: permission_classes = [InGroup('Admins', 'Managers')]
    class GroupPermission(BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Super Admin always bypasses group checks
            if request.user.is_superuser or request.user.role == 'SUPER_ADMIN':
                return True
                
            return request.user.groups.filter(name__in=group_names).exists()
            
    return GroupPermission

class IsBorrower(BasePermission):
    # Checks if the user has the Borrower role.
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'BORROWER'
        )
class IsKYCVerified(BasePermission):
    # Checks if the user is a borrower and has completed KYC verification.
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # If user is admin/manager/loan officer, they bypass borrower KYC checks
        if request.user.is_superuser or request.user.role in ['SUPER_ADMIN', 'ADMIN', 'MANAGER', 'LOAN_OFFICER']:
            return True
            
        # For borrowers, check if their profile is KYC verified
        borrower_profile = getattr(request.user, 'borrower_profile', None)
        return borrower_profile is not None and borrower_profile.is_kyc_verified