from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from .models import User, StudentProfile, OwnerProfile, OTPVerification, AuditLog
import pyotp
import random
import re


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['student', 'owner'], write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'phone_number', 'password', 'password_confirm', 'role']
    
    def validate_phone_number(self, value):
        """Validate Kenyan phone number format"""
        # Remove any spaces or dashes
        phone = re.sub(r'[\s\-]', '', value)
        
        # Convert 07xx to +2547xx
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif phone.startswith('7'):
            phone = '+254' + phone
        elif not phone.startswith('+254'):
            raise serializers.ValidationError("Phone number must start with +254 or 0")
        
        # Check length
        if len(phone) != 13:  # +254XXXXXXXXX is 13 characters
            raise serializers.ValidationError("Phone number must be 9 digits after +254")
        
        return phone
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        role = validated_data.pop('role')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            phone_number=validated_data['phone_number']
        )
        user.is_active = False  # Require OTP verification
        
        # Generate OTP
        otp_code = str(random.randint(100000, 999999))
        OTPVerification.objects.create(
            user=user,
            otp_type='phone',
            code=otp_code,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
            ip_address=self.context.get('request').META.get('REMOTE_ADDR') if self.context.get('request') else None,
            user_agent=self.context.get('request').META.get('HTTP_USER_AGENT', '') if self.context.get('request') else ''
        )
        
        # Create appropriate profile
        if role == 'student':
            StudentProfile.objects.create(user=user)
        else:
            OwnerProfile.objects.create(user=user)
        
        user.save()
        
        # Send OTP (handled by view)
        return user


class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, data):
        try:
            # Format phone number
            phone = data['phone_number']
            if phone.startswith('0'):
                phone = '+254' + phone[1:]
            elif not phone.startswith('+254'):
                phone = '+254' + phone
            
            user = User.objects.get(phone_number=phone)
            otp = OTPVerification.objects.filter(
                user=user,
                otp_type='phone',
                code=data['otp_code'],
                is_used=False,
                expires_at__gt=timezone.now()
            ).latest('created_at')
            
            if not otp:
                raise serializers.ValidationError("Invalid or expired OTP")
            
            data['user'] = user
            data['otp'] = otp
            return data
            
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        except OTPVerification.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired OTP")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        
        if user.is_blocked:
            if user.blocked_until and user.blocked_until > timezone.now():
                raise serializers.ValidationError(
                    f"Account blocked until {user.blocked_until.strftime('%Y-%m-%d %H:%M')}. Reason: {user.blocked_reason}"
                )
            elif user.blocked_until and user.blocked_until <= timezone.now():
                user.is_blocked = False
                user.failed_login_attempts = 0
                user.blocked_reason = ''
                user.save()
        
        data['user'] = user
        return data


class TwoFactorSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    token = serializers.CharField(max_length=6)
    
    def validate(self, data):
        try:
            user = User.objects.get(id=data['user_id'])
            
            if not user.two_factor_enabled:
                raise serializers.ValidationError("2FA not enabled for this user")
            
            totp = pyotp.TOTP(user.otp_secret)
            if not totp.verify(data['token']):
                raise serializers.ValidationError("Invalid 2FA token")
            
            data['user'] = user
            return data
            
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")


class StudentProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = '__all__'
        read_only_fields = ['id', 'user', 'is_verified', 'total_bookings', 'total_spent', 
                           'average_rating_given', 'created_at', 'updated_at']


class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ['course', 'year_of_study', 'alternative_phone', 'preferred_budget_min',
                 'preferred_budget_max', 'preferred_distance_km', 'looking_for_roommate', 'roommate_bio']


class OwnerProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = OwnerProfile
        fields = '__all__'
        read_only_fields = ['id', 'user', 'is_approved', 'fraud_score', 'total_hostels', 
                           'total_bookings', 'total_revenue', 'total_commission_owed', 
                           'total_commission_paid', 'created_at', 'updated_at']


class OwnerProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnerProfile
        fields = ['business_phone', 'business_email', 'business_address']


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords do not match"})
        return data


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords do not match"})
        return data


class NotificationPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['notification_preferences']


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'