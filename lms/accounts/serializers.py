from rest_framework import serializers
from .models import BorrowerProfile, CustomUser, CreditScoreHistory
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from datetime import date
from .encryption import encrypt, make_hash, mask_aadhar, mask_pan

class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    # Raw input fields — validated, then encrypted before saving
    aadhar_number = serializers.CharField(write_only=True)
    pan_number    = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'confirm_password',
                  'first_name', 'last_name', 'phone_number',
                  'date_of_birth', 'aadhar_number', 'pan_number']
        extra_kwargs = {
            'password': {'write_only': True},
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
    
    def validate_aadhar_number(self, value):
        if not value.isdigit() or len(value) != 12:
            raise serializers.ValidationError("Aadhar number must be exactly 12 digits.")
        # Uniqueness check via hash (not ciphertext)
        h = make_hash(value)
        if CustomUser.objects.filter(aadhar_hash=h).exists():
            raise serializers.ValidationError("This Aadhar number is already registered.")
        return value

    def validate_pan_number(self, value):
        import re
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', value.upper()):
            raise serializers.ValidationError("PAN must be in format: ABCDE1234F")
        value = value.upper()
        # Uniqueness check via hash
        h = make_hash(value)
        if CustomUser.objects.filter(pan_hash=h).exists():
            raise serializers.ValidationError("This PAN number is already registered.")
        return value
    
    def validate_date_of_birth(self,value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError("You must be at least 18 years old to register.")
        return value
#Once all validation checks pass, calling .save() on a serializer will trigger this create() method to actually insert a new record into your database.
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        validated_data['role'] = 'BORROWER'

        # Encrypt + hash Aadhar
        raw_aadhar = validated_data.pop('aadhar_number')
        validated_data['aadhar_number'] = encrypt(raw_aadhar)
        validated_data['aadhar_hash']   = make_hash(raw_aadhar)

        # Encrypt + hash PAN
        raw_pan = validated_data.pop('pan_number')
        validated_data['pan_number'] = encrypt(raw_pan)
        validated_data['pan_hash']   = make_hash(raw_pan)

        return CustomUser.objects.create_user(**validated_data)

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
    # Return masked values in the response — never raw encrypted blobs or plain text
    aadhar_display = serializers.SerializerMethodField()
    pan_display    = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'phone_number', 'date_of_birth',
                  'aadhar_display', 'pan_display',
                  'profile_picture', 'role', 'borrower_profile']
        read_only_fields = ['role', 'profile_picture']

    def get_aadhar_display(self, obj):
        if not obj.aadhar_number:
            return None
        from .encryption import decrypt
        try:
            return mask_aadhar(decrypt(obj.aadhar_number))
        except Exception:
            return 'XXXX-XXXX-XXXX'

    def get_pan_display(self, obj):
        if not obj.pan_number:
            return None
        from .encryption import decrypt
        try:
            return mask_pan(decrypt(obj.pan_number))
        except Exception:
            return 'XXXXXXXXXX'
    
    
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


class ProfilePictureSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['profile_picture']

    def validate_profile_picture(self, image):
        from PIL import Image

        # 1. Only allow JPEG and PNG
        img = Image.open(image)
        if img.format not in ['JPEG', 'PNG']:
            raise serializers.ValidationError("Only JPEG and PNG images are allowed.")

        # 2. Reject files larger than 5 MB before processing
        if image.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image size must not exceed 5 MB.")

        # 3. Resize to max 500x500 using Pillow (preserves aspect ratio)
        max_size = (500, 500)
        img.thumbnail(max_size, Image.LANCZOS)

        # 4. Save the resized image back into the InMemoryUploadedFile
        import io
        from django.core.files.uploadedfile import InMemoryUploadedFile
        output = io.BytesIO()
        img_format = img.format or 'JPEG'
        img.save(output, format=img_format)
        output.seek(0)

        return InMemoryUploadedFile(
            output,
            'ImageField',
            image.name,
            image.content_type,
            output.getbuffer().nbytes,
            None
        )
