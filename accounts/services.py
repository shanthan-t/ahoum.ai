import hashlib
import secrets
import struct
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import connection, transaction
from django.utils import timezone

from .exceptions import (
    AlreadyVerifiedException,
    CooldownActiveException,
    EmailAlreadyRegisteredException,
    InvalidOTPException,
    OTPExpiredException,
    OTPMaxAttemptsException,
)
from .models import EmailOTP, UserProfile

User = get_user_model()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_email_lock_id(email: str) -> int:
    """Generate a 64-bit signed integer for PostgreSQL advisory locks."""
    h = hashlib.sha256(email.encode("utf-8")).digest()
    return struct.unpack("q", h[:8])[0]


def _generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return "".join(secrets.choice("0123456789") for _ in range(6))


@transaction.atomic
def process_signup(email: str, password: str, role: str) -> tuple[User, str]:
    """
    Handles user signup atomically.
    Returns (user, plaintext_otp).
    """
    email = normalize_email(email)
    
    # Acquire transaction-level advisory lock to prevent concurrent signups
    # for the exact same email from creating duplicate accounts.
    lock_id = get_email_lock_id(email)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])

    user = User.objects.filter(email=email).first()

    if user:
        # Check if already verified
        if hasattr(user, "profile") and user.profile.email_verified:
            raise EmailAlreadyRegisteredException(
                detail="A verified account with this email already exists.",
                code="email_already_registered",
            )
        
        # Unverified re-registration path
        user.set_password(password)
        user.save(update_fields=["password"])

        profile = user.profile
        profile.role = role
        profile.save(update_fields=["role", "updated_at"])

        # Deactivate existing active OTPs
        EmailOTP.objects.filter(user=user, is_active=True).update(is_active=False)
    else:
        # Fresh registration
        import uuid
        user = User.objects.create_user(
            username=uuid.uuid4().hex,
            email=email,
            password=password,
        )
        UserProfile.objects.create(user=user, role=role, email_verified=False)

    otp_code = _generate_otp_code()
    EmailOTP.objects.create(
        user=user,
        otp_hash=make_password(otp_code),
        is_active=True,
    )

    return user, otp_code


def process_verify_email(email: str, otp_code: str) -> None:
    """
    Verifies the OTP for a given email atomically.
    """
    email = normalize_email(email)
    user = User.objects.filter(email=email).first()

    if not user:
        raise InvalidOTPException(
            detail="Invalid email or OTP.", code="invalid_otp"
        )

    profile = user.profile
    if profile.email_verified:
        raise AlreadyVerifiedException(
            detail="Account is already verified.", code="already_verified"
        )

    error_to_raise = None

    with transaction.atomic():
        # Lock the active OTP row for this user to prevent concurrent double-use
        otp = EmailOTP.objects.select_for_update().filter(
            user=user, is_active=True, is_used=False
        ).first()

        if not otp:
            error_to_raise = InvalidOTPException(
                detail="Invalid email or OTP.", code="invalid_otp"
            )
        else:
            ttl = timedelta(minutes=getattr(settings, "OTP_TTL_MINUTES", 5))
            max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)

            if timezone.now() > otp.created_at + ttl:
                otp.is_active = False
                otp.save(update_fields=["is_active"])
                error_to_raise = OTPExpiredException(
                    detail="OTP has expired. Please request a new one.",
                    code="otp_expired"
                )
            elif otp.attempts >= max_attempts:
                otp.is_active = False
                otp.save(update_fields=["is_active"])
                error_to_raise = OTPMaxAttemptsException(
                    detail="Maximum verification attempts exceeded. Please request a new OTP.",
                    code="otp_max_attempts"
                )
            elif not check_password(otp_code, otp.otp_hash):
                otp.attempts += 1
                otp.save(update_fields=["attempts"])
                if otp.attempts >= max_attempts:
                    otp.is_active = False
                    otp.save(update_fields=["is_active"])
                error_to_raise = InvalidOTPException(
                    detail="Invalid email or OTP.", code="invalid_otp"
                )
            else:
                # Success
                otp.is_used = True
                otp.is_active = False
                otp.save(update_fields=["is_used", "is_active"])

                profile.email_verified = True
                profile.save(update_fields=["email_verified", "updated_at"])

    if error_to_raise:
        raise error_to_raise


@transaction.atomic
def process_resend_otp(email: str) -> str | None:
    """
    Generates a new OTP for the user, invalidating old ones.
    Returns the plaintext OTP if successful, or None if the user doesn't exist.
    """
    email = normalize_email(email)
    user = User.objects.filter(email=email).first()

    if not user:
        return None  # We'll return success in the view to prevent enumeration

    if hasattr(user, "profile") and user.profile.email_verified:
        raise AlreadyVerifiedException(
            detail="Account is already verified.", code="already_verified"
        )

    # Lock all OTP rows for this user to serialize resends and enforce cooldown
    otps = EmailOTP.objects.select_for_update().filter(user=user).order_by("-created_at")
    
    # We must evaluate the queryset to acquire the locks and check the latest OTP
    latest_otp = list(otps[:1])
    
    if latest_otp:
        latest = latest_otp[0]
        cooldown = timedelta(seconds=getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60))
        if timezone.now() < latest.created_at + cooldown:
            raise CooldownActiveException(
                detail="Please wait before requesting another OTP.",
                code="cooldown_active"
            )

    # Deactivate all active OTPs
    EmailOTP.objects.filter(user=user, is_active=True).update(is_active=False)

    # Generate new OTP
    otp_code = _generate_otp_code()
    EmailOTP.objects.create(
        user=user,
        otp_hash=make_password(otp_code),
        is_active=True,
    )

    return otp_code


def send_otp_email(email: str, otp_code: str):
    """
    Sends the OTP email. Called outside the atomic transaction.
    """
    send_mail(
        subject="Your Ahoum Events Platform Verification Code",
        message=f"Your verification code is: {otp_code}\n\nThis code will expire in {getattr(settings, 'OTP_TTL_MINUTES', 5)} minutes.",
        from_email="noreply@ahoum.ai",
        recipient_list=[email],
        fail_silently=False,
    )
