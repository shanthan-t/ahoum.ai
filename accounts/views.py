from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .exceptions import EmailNotVerifiedException, InvalidCredentialsException
from .serializers import (
    LoginSerializer,
    ResendOTPSerializer,
    SignupSerializer,
    VerifyEmailSerializer,
)
from .services import (
    normalize_email,
    process_resend_otp,
    process_signup,
    process_verify_email,
    send_otp_email,
)

User = get_user_model()


class SignupView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, otp_code = process_signup(
            serializer.validated_data["email"],
            serializer.validated_data["password"],
            serializer.validated_data["role"],
        )

        send_otp_email(user.email, otp_code)

        return Response(
            {
                "detail": "Verification email sent.",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        process_verify_email(
            serializer.validated_data["email"],
            serializer.validated_data["otp"],
        )

        return Response(
            {"detail": "Email verified successfully."},
            status=status.HTTP_200_OK,
        )


class ResendOTPView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp_code = process_resend_otp(email)

        if otp_code:
            send_otp_email(email, otp_code)

        return Response(
            {
                "detail": "If the account exists and requires verification, a new verification email has been sent."
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = normalize_email(serializer.validated_data["email"])
        password = serializer.validated_data["password"]

        user = User.objects.filter(email=email).first()

        # Check existence, password, and active status
        if not user or not user.check_password(password) or not user.is_active:
            raise InvalidCredentialsException(
                detail="Invalid credentials.", code="invalid_credentials"
            )

        # Check verified status
        if not hasattr(user, "profile") or not user.profile.email_verified:
            raise EmailNotVerifiedException(
                detail="Email not verified.", code="email_not_verified"
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "email": user.email,
                    "role": user.profile.role,
                },
            },
            status=status.HTTP_200_OK,
        )
