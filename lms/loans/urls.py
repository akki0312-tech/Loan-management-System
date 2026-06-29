from django.urls import path
from loans.views import (
    EMICalculationView,
    LoanTypeListCreateView,
    LoanTypeDetailView,
    LoanListCreateView,
    LoanDetailView,
    EMIScheduleListView,
    PaymentCreateView,
    PaymentListView,
    PublicMarketDataView
)

urlpatterns = [
    # Public EMI calculator
    path('loans/emi-calculator/', EMICalculationView.as_view(), name='emi_calculator'),

    # Loan Types (admin creates/edits, borrowers read)
    path('loans/types/', LoanTypeListCreateView.as_view(), name='loan_type_list'),
    path('loans/types/<int:pk>/', LoanTypeDetailView.as_view(), name='loan_type_detail'),

    # Loans (borrowers apply/view, admins approve/disburse)
    path('loans/', LoanListCreateView.as_view(), name='loan_list_create'),
    path('loans/<int:pk>/', LoanDetailView.as_view(), name='loan_detail'),

    # EMI Schedule (read-only, nested under a loan)
    path('loans/<int:loan_pk>/emi-schedule/', EMIScheduleListView.as_view(), name='emi_schedule'),

    # Payments
    path('loans/payments/', PaymentCreateView.as_view(), name='payment_create'),
    path('loans/payments/history/', PaymentListView.as_view(), name='payment_list'),
    path('loans/market-data/', PublicMarketDataView.as_view(), name='market_data'),
]
