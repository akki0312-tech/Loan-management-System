from django.urls import path
from .views import EMICalculationView

urlpatterns = [
    path('loans/emi-calculator/', EMICalculationView.as_view(), name='emi_calculator'),
]
