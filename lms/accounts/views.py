from rest_framework import generics
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils import timezone
from rest_framework.response import Response
from accounts.models import BorrowerProfile, CustomUser, CreditScoreHistory
from accounts.serializers import (
    BorrowerProfileSerializer, CreditScoreHistorySerializer,RoleAssignmentSerializer,
    RegisterSerializer, LoginWithOTPSerializer, VerifyOTPSerializer,
    UserSerializer, AdminKYCSerializer, ProfilePictureSerializer,
)
from accounts.permissions import HasRole, InGroup, IsBorrower, IsKYCVerified
from django.db.models import Q


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.role == 'ADMIN' or request.user.is_superuser)

# --- Custom Token View ---
class RegisterView(generics.CreateAPIView): #what is generics.CreateAPIView? It is a built-in view provided by Django REST Framework that handles the creation of new model instances. It provides a default implementation for handling POST requests to create new objects in the database.
    queryset = CustomUser.objects.all() #what is queryset? A queryset is a collection of database queries that can be filtered, ordered, and manipulated to retrieve specific data from the database. In this case, it retrieves all instances of the CustomUser model.
    serializer_class = RegisterSerializer #what is serializer_class? It specifies which serializer should be used to validate and serialize the incoming data for this view. In this case, it uses the RegisterSerializer to handle user registration.
    
    permission_classes = [AllowAny] #why is permission_classes empty? Because we want to allow anyone to register, so we don't require any authentication or permissions for this view.

class LoginView(generics.GenericAPIView):
    serializer_class = LoginWithOTPSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)

class VerifyOTPView(generics.GenericAPIView):
    serializer_class = VerifyOTPSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)

class MyProfileView(generics.RetrieveUpdateAPIView):
    #what is generics.RetrieveUpdateAPIView? It is a built-in view provided by Django REST Framework that handles retrieving and updating a single model instance. It provides a default implementation for handling GET and PUT requests to retrieve and update an object from the database.
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated] #why is permission_classes set to IsAuthenticated? Because we want to ensure that only authenticated users can access their profile information. This view requires the user to be logged in and have a valid token to retrieve their profile data.

    def get_object(self):
        return self.request.user
    
class BorrowerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = BorrowerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, created = BorrowerProfile.objects.get_or_create(user=self.request.user)
        return profile
    
# When a new user registers, they don't have a BorrowerProfile record in the database yet. If we just call self.request.user.borrower_profile, Django will throw a RelatedObjectDoesNotExist error because the profile record doesn't exist.
# We can solve this elegantly inside get_object() by using Django's get_or_create method. This method checks if a profile exists; if it does, it returns it, and if it doesn't, it creates a blank one for that user first.

class kycView(generics.UpdateAPIView):
    serializer_class = AdminKYCSerializer
    permission_classes = [HasRole('SUPER_ADMIN', 'ADMIN', 'MANAGER', 'LOAN_OFFICER')]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role in ['SUPER_ADMIN', 'ADMIN']:
            return BorrowerProfile.objects.all()
        elif user.role == 'MANAGER':
            # Manager sees profiles of borrowers assigned directly to them OR assigned to officers who report to them
            return BorrowerProfile.objects.filter(Q(user__manager=user) | Q(user__manager__manager=user))
        elif user.role == 'LOAN_OFFICER':
            # Loan officer sees profiles of borrowers assigned to them
            return BorrowerProfile.objects.filter(user__manager=user)
        return BorrowerProfile.objects.none()
    
class CreditScoreUpdateView(generics.CreateAPIView):
    queryset = CreditScoreHistory.objects.all()
    serializer_class = CreditScoreHistorySerializer
    permission_classes = [HasRole('SUPER_ADMIN', 'ADMIN', 'MANAGER', 'LOAN_OFFICER')]


class ProfilePictureView(generics.UpdateAPIView):
    # PATCH /api/auth/profile-picture/ — upload or replace profile picture.
    serializer_class = ProfilePictureSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    http_method_names = ['patch']  # PUT not allowed — only partial update makes sense here

    def get_object(self):
        return self.request.user

class IsAdminManagerOrSuperAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        # Allow Super Admin, Admin, and Manager
        return request.user.role in ['SUPER_ADMIN', 'ADMIN', 'MANAGER'] or request.user.is_superuser

class RoleAssignmentView(generics.UpdateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = RoleAssignmentSerializer
    permission_classes = [IsAdminManagerOrSuperAdmin]  # Updated here
    http_method_names = ['patch']





    
    