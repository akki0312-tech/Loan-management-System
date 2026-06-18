from rest_framework import serializers
from django.contrib.auth.models import User
from .models import BorrowerProfile, CustomUser, CreditScoreHistory
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from datetime import date

class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True) #why is this not on model?Because its just a check to confirm password and we don't want to store it in database

    class Meta: #what is a meta class? Meta class is a way to specify additional information about the serializer, such as which model it is based on and which fields to include or exclude.
        model = CustomUser
        fields = ['username', 'email', 'password', 'confirm_password',
                  'first_name', 'last_name', 'phone_number',
                  'date_of_birth', 'aadhar_number']
        extra_kwargs = {
            'password': {'write_only': True},  # never return password in response
        }
#Object level validation: validate() method is called after field level validation and can be used to validate multiple fields together. In this case, we are checking if password and confirm_password match.
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data
#Field level validations : format is very important 
    def validate_phone_number(self,value):
        if not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError("Phone number must be 10 digits.")
        return value
    
    def validate_aadhar_number(self,value):
        if not value.isdigit() or len(value) != 12:
            raise serializers.ValidationError("Aadhar number must be 12 digits.")
        return value
    
    def validate_date_of_birth(self,value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError("You must be at least 18 years old to register.")
        return value
#Once all validation checks pass, calling .save() on a serializer will trigger this create() method to actually insert a new record into your database.
    def create(self, validated_data): #validated_data is a dictionary of the validated data that was passed to the serializer. It contains all the fields that were defined in the serializer's Meta class, as well as any additional fields that were added during validation.
        validated_data.pop('confirm_password') #remove confirm_password from validated_data before creating user because it is not a field in the CustomUser model
        validated_data['role'] = 'BORROWER' #You should never allow a user to register themselves as an Admin via a public registration endpoint
        user = CustomUser.objects.create_user(**validated_data) #CustomUser.objects.create_user(...) (and objects.create(...)) does both in one step: it instantiates the object, hashes the password safely, and saves it directly to the database.
        return user

#So when the user logs in, they send their username and password.
#parent class validates if this particular username+password exists in db, 
# if fails then error otherwise it calls to get_token(user) to obtain the randomly generated access token for that particular user, 
# we also embed username, email and role in this case.

#Why do we embed username, email and role in the token?
# Because when the user makes subsequent requests to protected endpoints, we can decode the token to quickly access these details without having to query the database again. 
# This allows us to implement role-based access control and personalize responses based on the user's information.


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['role'] = user.role
        return token

class BorrowerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BorrowerProfile
        fields = ['salary', 'monthly_expenses', 'credit_score', 'employment_type','is_kyc_verified']   
        extra_kwargs = {
            'is_kyc_verified': {'read_only': True}, #only admin can update this field, borrower cannot update this field, but they can read it in response
        }

    def validate(self, data):
    # Get values from input, or fallback to None if they aren't provided in the request
        salary = data.get('salary')
        expenses = data.get('monthly_expenses')
    
    # Only validate if both values are present in the request
        if salary is not None and expenses is not None:
            if expenses > salary:
                raise serializers.ValidationError("Monthly expenses cannot be greater than salary.")
            
        return data

    def validate_salary(self, value):
        if not value > 0:
            raise serializers.ValidationError("Salary must be a positive number.")
        return value

    def validate_monthly_expenses(self, value):
        if not value > 0:
            raise serializers.ValidationError("Monthly expenses must be a positive number.")
        return value  
    
class UserSerializer(serializers.ModelSerializer):
    borrower_profile = BorrowerProfileSerializer(read_only=True)
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number', 'date_of_birth', 'aadhar_number', 'role', 'borrower_profile']
        read_only_fields = ['role']
    
    
class CreditScoreHistorySerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True)
    class Meta:
        model = CreditScoreHistory
        fields = ['id', 'borrower_profile', 'score', 'remarks', 'recorded_at', 'updated_by', 'updated_by_username']
        read_only_fields = ['recorded_at', 'updated_by'] #recorded_at and updated_by are read-only because they are automatically set by the system when a new credit score history record is created or updated.
    def create(self, validated_data):
        # Retrieve the logged-in admin user from the request context
        request = self.context.get('request')
        if request and request.user:
            validated_data['updated_by'] = request.user
            
        return super().create(validated_data)
    
#Views in Django REST Framework pass the HTTP request object into the serializer's context. 
# Inside the serializer, we can access the logged-in user using self.context['request'].user. 
# This ensures updated_by is always set to the correct logged-in admin who is performing the update

    
class AdminKYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = BorrowerProfile
        fields = ['is_kyc_verified']

    
class CreditScoreHistorySerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = CreditScoreHistory
        fields = ['id', 'borrower_profile', 'score', 'remarks', 'recorded_at', 'updated_by', 'updated_by_username']
        read_only_fields = ['recorded_at', 'updated_by']

    def create(self, validated_data):
        # 1. Get the admin making the request
        request = self.context.get('request')
        if request and request.user:
            validated_data['updated_by'] = request.user
            
        # 2. Create the history record
        history = super().create(validated_data)
        
        # 3. Update the borrower's main profile score
        profile = history.borrower_profile
        profile.credit_score = history.score
        profile.save()
        
        return history
        
    
        

    


           
    

    
