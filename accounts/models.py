from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """
    Extends Django's default User with role and email verification status.
    Linked via OneToOneField — one profile per user, created at signup.
    """

    class Role(models.TextChoices):
        SEEKER = "seeker", "Seeker"
        FACILITATOR = "facilitator", "Facilitator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(role__in=["seeker", "facilitator"]),
                name="userprofile_role_valid",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} ({self.role})"


class EmailOTP(models.Model):
    """
    Stores hashed one-time passwords for email verification.
    Never stores plaintext OTPs. One user can have multiple OTP records
    over time, but at most one should be active at any given moment
    (enforced in application logic, not here).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_otps",
    )
    otp_hash = models.CharField(max_length=128)
    is_used = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="emailotp_user_active_idx",
            ),
        ]

    def __str__(self):
        status = "active" if self.is_active and not self.is_used else "inactive"
        return f"OTP for {self.user.email} ({status})"
