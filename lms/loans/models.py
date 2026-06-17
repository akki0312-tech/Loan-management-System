from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class LoanType(models.Model):
    name = models.CharField(max_length=100, choices=[('PERSONAL_LOAN', 'Personal Loan'), ('HOME_LOAN', 'Home Loan'), ('CAR_LOAN', 'Car Loan'), ('EDUCATION_LOAN', 'Education Loan')],unique=True)
    interest_type = models.CharField(max_length=20, choices=[('FLAT', 'Flat'), ('REDUCING_BALANCE', 'Reducing Balance')])
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    min_amount = models.DecimalField(max_digits=15, decimal_places=2)
    min_tenure_months = models.IntegerField()
    max_tenure_months = models.IntegerField()

    def __str__(self):
        return self.name
    
class Loan(models.Model):
    borrower = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='loans') #does this mean borrowers can have multiple loans? yes, a borrower can have multiple loans
    loan_type = models.ForeignKey(LoanType, on_delete=models.PROTECT, related_name='loans')
    amount_requested = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    interest_type = models.CharField(max_length=20, choices=[('FLAT', 'Flat'), ('REDUCING_BALANCE', 'Reducing Balance')])
    tenure_months = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'),('UNDER_REVIEW', 'Under Review'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'),('DISBURSED', 'Disbursed'),('ACTIVE', 'Active'),('CLOSED', 'Closed'),('OVERDUE', 'Overdue'),('DEFAULTED', 'Defaulted'),('CANCELLED', 'Cancelled')], default='PENDING')
    approved_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan {self.id} for {self.borrower.username} - {self.status}" #what does self.id mean? self.id is the unique identifier for each Loan instance in the database

class EMISchedule(models.Model):
    loan = models.ForeignKey(Loan,on_delete=models.CASCADE, related_name='emi_schedule')
    emi_number = models.IntegerField()
    due_date = models.DateField()
    emi_amount = models.DecimalField(max_digits=15, decimal_places=2)
    principal_component = models.DecimalField(max_digits=15, decimal_places=2)
    interest_component = models.DecimalField(max_digits=15, decimal_places=2)
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('PAID', 'Paid'), ('OVERDUE', 'Overdue')], default='PENDING')

    def __str__(self):
        return f"EMI {self.emi_number} for Loan {self.loan.id} - {self.status}"

class Payment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    emi_schedule = models.OneToOneField(EMISchedule, on_delete=models.CASCADE, related_name='payment')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment of {self.amount_paid} for EMI {self.emi_schedule.emi_number} on Loan {self.loan.id}"
    




