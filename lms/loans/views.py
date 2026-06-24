from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q


from loans.models import LoanType, Loan, EMISchedule, Payment
from loans.serializers import (
    EMICalculationSerializer,
    LoanTypeSerializer,
    LoanSerializer,
    EMIScheduleSerializer,
    PaymentSerializer,
)
# Reuse IsAdminUser from accounts — DRY, no duplication
from accounts.views import IsAdminUser

def generate_emi_schedule(loan):
    principal = loan.amount_requested   
    annual_rate = loan.interest_rate
    tenure = loan.tenure_months
    interest_type = loan.interest_type
    start_date = loan.disbursed_at.date() if loan.disbursed_at else timezone.now().date()

    EMISchedule.objects.filter(loan=loan).delete()  # clean slate if regenerated

    if interest_type == 'FLAT':
        total_interest = principal * (annual_rate / Decimal('100')) * (Decimal(tenure) / Decimal('12'))
        monthly_emi = ((principal + total_interest) / tenure).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        monthly_principal = (principal / tenure).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        monthly_interest = (total_interest / tenure).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        outstanding = principal

        for i in range(1, tenure + 1):
            outstanding = (outstanding - monthly_principal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if i == tenure:
                outstanding = Decimal('0.00')
            EMISchedule.objects.create(
                loan=loan,
                emi_number=i,
                due_date=start_date + relativedelta(months=i),
                emi_amount=monthly_emi,
                principal_component=monthly_principal,
                interest_component=monthly_interest,
                outstanding_balance=max(outstanding, Decimal('0.00')),
            )

    elif interest_type == 'REDUCING_BALANCE':
        monthly_rate = annual_rate / Decimal('100') / Decimal('12')
        factor = (1 + monthly_rate) ** tenure
        monthly_emi = (principal * monthly_rate * factor / (factor - 1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        outstanding = principal

        for i in range(1, tenure + 1):
            interest_component = (outstanding * monthly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            principal_component = (monthly_emi - interest_component).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            outstanding = (outstanding - principal_component).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if i == tenure:
                outstanding = Decimal('0.00')
            EMISchedule.objects.create(
                loan=loan,
                emi_number=i,
                due_date=start_date + relativedelta(months=i),
                emi_amount=monthly_emi,
                principal_component=principal_component,
                interest_component=interest_component,
                outstanding_balance=max(outstanding, Decimal('0.00')),
            )


class EMICalculationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EMICalculationSerializer(data=request.data)
        if serializer.is_valid():
            loan_amount = float(serializer.validated_data['loan_amount'])
            annual_rate = float(serializer.validated_data['interest_rate'])
            tenure_months = int(serializer.validated_data['tenure_months'])
            interest_type = serializer.validated_data['interest_type']

            if interest_type == 'FLAT':
                monthly_emi = (loan_amount + (loan_amount * (annual_rate / 100) * (tenure_months / 12))) / tenure_months
            else:
                monthly_rate = (annual_rate / 100) / 12
                monthly_emi = loan_amount * monthly_rate * ((1 + monthly_rate) ** tenure_months) / (((1 + monthly_rate) ** tenure_months) - 1)

            return Response({'monthly_emi': round(monthly_emi, 2)}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# LOAN TYPE: Admin CRUD, Borrowers read-only


class LoanTypeListCreateView(generics.ListCreateAPIView):

    # GET  — anyone authenticated can list loan types.
    # POST — admin only, to create a new loan type.

    queryset = LoanType.objects.all()
    serializer_class = LoanTypeSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticated()]


class LoanTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    
    # GET    — any authenticated user.
    # PUT/PATCH/DELETE — admin only.
    
    queryset = LoanType.objects.all()
    serializer_class = LoanTypeSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminUser()]
        return [IsAuthenticated()]


class LoanListCreateView(generics.ListCreateAPIView):
    
    # POST — borrower applies for a loan.
    # GET  — borrowers see only their own loans; admins see all.
    
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role in ['SUPER_ADMIN', 'ADMIN']:
            return Loan.objects.all()
        elif user.role == 'MANAGER':
            # Manager sees loans of borrowers assigned directly to them OR assigned to officers who report to them
            return Loan.objects.filter(Q(borrower__manager=user) | Q(borrower__manager__manager=user))
        elif user.role == 'LOAN_OFFICER':
            # Loan officer sees loans of borrowers assigned to them
            return Loan.objects.filter(borrower__manager=user)
        elif user.role == 'BORROWER':
            return Loan.objects.filter(borrower=user)
        return Loan.objects.none()

    def get_serializer_context(self):
        # Pass request into serializer so validate() can access request.user
        return {'request': self.request}


class LoanDetailView(generics.RetrieveUpdateAPIView):
    # GET        — borrower can view their own loan; staff/admin can view assigned.
    # PATCH/PUT  — staff/admin only (to update status through the state machine).
    serializer_class = LoanSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            # Require staff or admin to update loan status
            return [HasRole('SUPER_ADMIN', 'ADMIN', 'MANAGER', 'LOAN_OFFICER')()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role in ['SUPER_ADMIN', 'ADMIN']:
            return Loan.objects.all()
        elif user.role == 'MANAGER':
            return Loan.objects.filter(Q(borrower__manager=user) | Q(borrower__manager__manager=user))
        elif user.role == 'LOAN_OFFICER':
            return Loan.objects.filter(borrower__manager=user)
        elif user.role == 'BORROWER':
            return Loan.objects.filter(borrower=user)
        return Loan.objects.none()

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_update(self, serializer):
        loan = serializer.save()
        if loan.status == 'APPROVED' and not loan.approved_at:
            loan.approved_by = self.request.user
            loan.approved_at = timezone.now()
            loan.save(update_fields=['approved_by', 'approved_at'])
        if loan.status == 'DISBURSED' and not loan.disbursed_at:
            loan.disbursed_at = timezone.now()
            loan.save(update_fields=['disbursed_at'])
            generate_emi_schedule(loan)


# EMI SCHEDULE: Read-only for borrower


class EMIScheduleListView(generics.ListAPIView):
    """
    GET — borrower can only see EMIs for their own loans.
    Staff can see EMIs for assigned loans.
    URL: /api/loans/<loan_pk>/emi-schedule/
    """
    serializer_class = EMIScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        loan_pk = self.kwargs['loan_pk']
        
        # Verify the user has access to the loan first
        if user.is_superuser or user.role in ['SUPER_ADMIN', 'ADMIN']:
            return EMISchedule.objects.filter(loan_id=loan_pk)
        elif user.role == 'MANAGER':
            return EMISchedule.objects.filter(
                Q(loan__borrower__manager=user) | Q(loan__borrower__manager__manager=user),
                loan_id=loan_pk
            )
        elif user.role == 'LOAN_OFFICER':
            return EMISchedule.objects.filter(loan__borrower__manager=user, loan_id=loan_pk)
        elif user.role == 'BORROWER':
            return EMISchedule.objects.filter(loan__borrower=user, loan_id=loan_pk)
        return EMISchedule.objects.none()



# PAYMENTS: Borrower pays an EMI


class PaymentCreateView(generics.CreateAPIView):
 
    # POST — borrower submits a payment for a specific EMI.
    # All validation (amount match, no skipping, loan active) is in the serializer.
   
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        return {'request': self.request}


class PaymentListView(generics.ListAPIView):
    # GET — borrowers see only their own payment history; staff/admins see assigned.
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role in ['SUPER_ADMIN', 'ADMIN']:
            return Payment.objects.all()
        elif user.role == 'MANAGER':
            return Payment.objects.filter(Q(loan__borrower__manager=user) | Q(loan__borrower__manager__manager=user))
        elif user.role == 'LOAN_OFFICER':
            return Payment.objects.filter(loan__borrower__manager=user)
        elif user.role == 'BORROWER':
            return Payment.objects.filter(loan__borrower=user)
        return Payment.objects.none()


