from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import (
    RegisterView,
    LoginView,
    MyProfileView,
    BorrowerProfileView,
    kycView,
    CreditScoreUpdateView,
    ProfilePictureView,
    RoleAssignmentView,
)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MyProfileView.as_view(), name='my_profile'),
    path('auth/borrower-profile/', BorrowerProfileView.as_view(), name='borrower_profile'),
    path('admin/verify-kyc/<int:pk>/', kycView.as_view(), name='verify_kyc'),
    path('admin/update-credit-score/', CreditScoreUpdateView.as_view(), name='update_credit_score'),
    path('auth/profile-picture/', ProfilePictureView.as_view(), name='profile_picture'),
    path('auth/users/<int:pk>/assign-role/', RoleAssignmentView.as_view(), name='assign_role'),
]
