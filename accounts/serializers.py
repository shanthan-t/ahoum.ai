from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import UserProfile


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    role = serializers.ChoiceField(choices=UserProfile.Role.choices)

    def validate(self, attrs):
        if "username" in self.initial_data:
            raise serializers.ValidationError(
                {"username": "Username is not accepted."}
            )
        return attrs


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
