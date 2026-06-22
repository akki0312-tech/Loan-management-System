from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, null=True, blank=True)
    last_name = models.CharField(max_length=30, null=True, blank=True)
    phone_number = models.CharField(max_length=10, unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    # Aadhar: stored encrypted; hash used for uniqueness checks
    aadhar_number = models.TextField(null=True, blank=True)          # encrypted ciphertext
    aadhar_hash   = models.CharField(max_length=64, unique=True, null=True, blank=True)  # HMAC-SHA256
    # PAN: same pattern
    pan_number    = models.TextField(null=True, blank=True)           # encrypted ciphertext
    pan_hash      = models.CharField(max_length=64, unique=True, null=True, blank=True)  # HMAC-SHA256
    role = models.CharField(max_length=15, choices=[('SUPER_ADMIN', 'Super Admin'),('ADMIN', 'Admin'),('MANAGER', 'Manager'),('LOAN_OFFICER', 'Loan_officer'), ('BORROWER', 'Borrower')], default='BORROWER')
    manager = models.ForeignKey(
    'self',                          # 'self' means it points to the same table (CustomUser)
    on_delete=models.SET_NULL,       # if manager is deleted, don't delete the employee, just set this to NULL
    null=True,                       # not everyone has a manager (e.g. Admin, Borrower)
    blank=True,                      # optional in forms/API
    related_name='subordinates',     # manager.subordinates.all() gives you all their team members
    limit_choices_to={'role__in': ['ADMIN', 'MANAGER']}  # only Admins or Managers can be set as manager
)

    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.username
    
class BorrowerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='borrower_profile')
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    employment_type = models.CharField(max_length=20, choices=[('SALARIED', 'Salaried'), ('SELF_EMPLOYED', 'Self-Employed'),('BUSINESS', 'Business')], null=True, blank=True)
    employer_name = models.CharField(max_length=100, null=True, blank=True)
    credit_score = models.IntegerField(null=True, blank=True,validators=[MinValueValidator(300), MaxValueValidator(900)])
    monthly_expenses = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_kyc_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Borrower Profile"
    
class CreditScoreHistory(models.Model):
    borrower_profile = models.ForeignKey(BorrowerProfile, on_delete=models.CASCADE, related_name='credit_score_history')
    score = models.IntegerField(validators=[MinValueValidator(300), MaxValueValidator(900)])
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_credit_scores')
    remarks = models.TextField()

    def __str__(self):
        return f"Credit Score {self.score} for {self.borrower_profile.user.username} recorded at {self.recorded_at}"

