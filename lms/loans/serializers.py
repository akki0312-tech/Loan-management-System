from rest_framework import serializers
from django.contrib.auth.models import User
from .models import LoanType,Loan,EMISchedule,Payment
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from datetime import date

