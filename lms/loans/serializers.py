from rest_framework import serializers
from loans.models import LoanType, Loan, EMISchedule, Payment
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import BorrowerProfile

class EMICalculationSerializer(serializers.Serializer):
    loan_amount = serializers.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(1000.00)])
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0.01)])
    tenure_months = serializers.IntegerField(min_value=3) 
    interest_type = serializers.ChoiceField(choices=[('FLAT', 'Flat'), ('REDUCING_BALANCE', 'Reducing Balance')])

class LoanTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanType
        fields = '__all__'

    def validate(self, data):
        # Get values from input, or fallback to the existing object's values if updating
        min_tenure = data.get('min_tenure_months')
        max_tenure = data.get('max_tenure_months')
    
        if self.instance:
            if min_tenure is None:
                min_tenure = self.instance.min_tenure_months
            if max_tenure is None:
                max_tenure = self.instance.max_tenure_months

        # Perform the check only if both values are available
        if min_tenure is not None and max_tenure is not None:
            if min_tenure >= max_tenure:
                raise serializers.ValidationError("Minimum tenure must be less than maximum tenure.")
                
        return data

class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = [
            'id', 'borrower', 'loan_type', 'amount_requested', 
            'interest_rate', 'interest_type', 'tenure_months', 
            'status', 'approved_by', 'approved_at', 'disbursed_at', 
            'created_at', 'updated_at'
        ]
        # These fields are protected and set by the system or admin, not by the borrower
        read_only_fields = [
            'id', 'borrower', 'interest_rate', 'interest_type', 
            'approved_by', 'approved_at', 'disbursed_at', 
            'created_at', 'updated_at'
        ]

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication credentials were not provided.")
        
        user = request.user

        if not self.instance:
            # 1. Check if Borrower Profile exists and is KYC verified
            try:
                profile = user.borrower_profile
                if not profile.is_kyc_verified:
                    raise serializers.ValidationError("Your KYC must be verified to apply for a loan.")
            except BorrowerProfile.DoesNotExist:
                raise serializers.ValidationError("You must create your borrower profile before applying for a loan.")

            # 2. Check if user already has an active loan (unclosed)
            active_loans = Loan.objects.filter(
                borrower=user, 
                status__in=['APPROVED', 'DISBURSED', 'ACTIVE', 'OVERDUE']
            )
            if active_loans.exists():
                raise serializers.ValidationError("You already have an active/disbursed loan. You cannot apply for a new one.")

            # Get inputs
            loan_type = data.get('loan_type')
            amount_requested = data.get('amount_requested')
            tenure_months = data.get('tenure_months')

            if amount_requested is None or loan_type is None or tenure_months is None:
                raise serializers.ValidationError("Missing required loan application fields.")

            # 3. Check requested amount against loan type minimum
            if amount_requested < loan_type.min_amount:
                raise serializers.ValidationError(
                    f"Requested amount ({amount_requested}) cannot be less than the minimum allowed ({loan_type.min_amount}) for this loan type."
                )

            # 4. Check requested tenure against loan type limits
            if tenure_months < loan_type.min_tenure_months or tenure_months > loan_type.max_tenure_months:
                raise serializers.ValidationError(
                    f"Tenure months ({tenure_months}) must be between {loan_type.min_tenure_months} and {loan_type.max_tenure_months} months for this loan type."
                )

        else:
            new_status = data.get('status')
            if new_status and new_status != self.instance.status:
                # 1. Check if the user is staff or admin
                is_staff = user.role in ['SUPER_ADMIN', 'ADMIN', 'MANAGER', 'LOAN_OFFICER'] or user.is_superuser
                if not is_staff:
                    raise serializers.ValidationError("Only authorized staff or admins can change the status of a loan.")

                # 2. Enforce the state machine transitions
                current_status = self.instance.status
                valid_transitions = {
                    'PENDING': ['UNDER_REVIEW', 'APPROVED', 'REJECTED', 'CANCELLED'],
                    'UNDER_REVIEW': ['APPROVED', 'REJECTED', 'CANCELLED'],
                    'APPROVED': ['DISBURSED', 'CANCELLED'],
                    'REJECTED': [],
                    'DISBURSED': ['ACTIVE'],
                    'ACTIVE': ['CLOSED', 'OVERDUE'],
                    'OVERDUE': ['DEFAULTED', 'CLOSED'],
                    'DEFAULTED': [],
                    'CLOSED': [],
                    'CANCELLED': []
                }
                
                allowed = valid_transitions.get(current_status, [])
                if new_status not in allowed:
                    raise serializers.ValidationError(
                        f"Invalid status transition from {current_status} to {new_status}."
                    )

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        loan_type = validated_data['loan_type']

        # Auto-populate and snapshot fields
        validated_data['borrower'] = request.user
        validated_data['interest_rate'] = loan_type.interest_rate
        validated_data['interest_type'] = loan_type.interest_type
        validated_data['status'] = 'PENDING'

        return super().create(validated_data)
    

class EMIScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EMISchedule
        fields = [
            'id', 
            'loan', 
            'emi_number', 
            'due_date', 
            'emi_amount', 
            'principal_component', 
            'interest_component', 
            'outstanding_balance', 
            'status'
        ]
        # Everything is read-only because EMI schedules are generated
        # automatically when a loan is disbursed, and updated when payments are made.
        read_only_fields = [
            'id', 'loan', 'emi_number', 'due_date', 'emi_amount',
            'principal_component', 'interest_component', 'outstanding_balance', 'status'
        ]

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'loan', 'emi_schedule', 'amount_paid', 'paid_at']
        read_only_fields = ['id', 'paid_at']

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication credentials were not provided.")
        
        user = request.user
        emi_schedule = data.get('emi_schedule')
        loan = data.get('loan')
        amount_paid = data.get('amount_paid')

        # 1. Verify relationships
        if emi_schedule.loan != loan:
            raise serializers.ValidationError("The selected EMI schedule does not belong to this loan.")

        if loan.borrower != user:
            raise serializers.ValidationError("You can only make payments for your own loans.")

        # 2. Check loan status (Allow payments for ACTIVE and OVERDUE loans)
        if loan.status not in ['ACTIVE', 'OVERDUE']:
            raise serializers.ValidationError(
                f"Payments can only be made for ACTIVE or OVERDUE loans. This loan is currently {loan.status}."
            )

        # 3. Check if EMI is already paid
        if emi_schedule.status == 'PAID':
            raise serializers.ValidationError("This EMI has already been paid.")

        # 4. Check payment amount matches EMI amount exactly
        if amount_paid != emi_schedule.emi_amount:
            raise serializers.ValidationError(
                f"The payment amount must be exactly {emi_schedule.emi_amount} for this EMI."
            )

        # 5. Enforce sequential payment (No skipping EMIs)
        previous_unpaid_emis = EMISchedule.objects.filter(
            loan=loan,
            emi_number__lt=emi_schedule.emi_number,
            status__in=['PENDING', 'OVERDUE']
        )
        if previous_unpaid_emis.exists():
            raise serializers.ValidationError("All previous EMIs must be paid before paying this EMI.")

        return data

    def create(self, validated_data):
        emi_schedule = validated_data['emi_schedule']
        loan = validated_data['loan']

        # 1. Create the payment record
        payment = super().create(validated_data)

        # 2. Update the EMI schedule status to PAID
        emi_schedule.status = 'PAID'
        emi_schedule.save()

        # 3. If all EMIs (PENDING or OVERDUE) are paid, mark the loan as CLOSED
        unpaid_emis_exist = EMISchedule.objects.filter(
            loan=loan,
            status__in=['PENDING', 'OVERDUE']
        ).exists()
        
        if not unpaid_emis_exist:
            loan.status = 'CLOSED'
            loan.save()

        return payment