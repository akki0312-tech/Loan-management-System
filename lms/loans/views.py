from django.shortcuts import render
from rest_framework import generics
from rest_framework.views import APIView
from .serializers import EMICalculationSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission, SAFE_METHODS
from .models import LoanType, Loan, EMISchedule, Payment


class EMICalculationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EMICalculationSerializer(data=request.data)
        if serializer.is_valid():
            # Convert to float to avoid TypeError when mixing with integers/floats
            loan_amount = float(serializer.validated_data['loan_amount'])
            annual_rate = float(serializer.validated_data['interest_rate'])
            tenure_months = int(serializer.validated_data['tenure_months'])
            interest_type = serializer.validated_data['interest_type']

            schedule = []
            total_interest = 0.0

            if interest_type == 'FLAT':
                # Total interest for the entire loan
                total_interest = loan_amount * (annual_rate / 100) * (tenure_months / 12)
                monthly_emi = (loan_amount + total_interest) / tenure_months
                monthly_principal = loan_amount / tenure_months
                monthly_interest = total_interest / tenure_months
                outstanding = loan_amount

                for month in range(1, tenure_months + 1):
                    outstanding = round(outstanding - monthly_principal, 2)
                    schedule.append({
                        'month': month,
                        'emi_amount': round(monthly_emi, 2),
                        'principal_component': round(monthly_principal, 2),
                        'interest_component': round(monthly_interest, 2),
                        'outstanding_balance': max(outstanding, 0.0)
                    })

            elif interest_type == 'REDUCING_BALANCE':
                monthly_rate = (annual_rate / 100) / 12
                # Standard reducing balance EMI formula
                monthly_emi = loan_amount * monthly_rate * ((1 + monthly_rate) ** tenure_months) / (((1 + monthly_rate) ** tenure_months) - 1)
                outstanding = loan_amount

                for month in range(1, tenure_months + 1):
                    interest_component = outstanding * monthly_rate
                    principal_component = monthly_emi - interest_component
                    outstanding = outstanding - principal_component
                    total_interest += interest_component

                    # Correct floating-point dust on final month
                    if month == tenure_months:
                        outstanding = 0.0

                    schedule.append({
                        'month': month,
                        'emi_amount': round(monthly_emi, 2),
                        'principal_component': round(principal_component, 2),
                        'interest_component': round(interest_component, 2),
                        'outstanding_balance': max(round(outstanding, 2), 0.0)
                    })

            total_payable = loan_amount + total_interest

            return Response({
                'monthly_emi': round(monthly_emi, 2),
                'total_principal': round(loan_amount, 2),
                'total_interest': round(total_interest, 2),
                'total_payable': round(total_payable, 2),
                'schedule': schedule
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
