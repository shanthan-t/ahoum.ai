import concurrent.futures
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import EmailOTP, UserProfile
from .services import _generate_otp_code

User = get_user_model()


class AuthTests(APITestCase):
    def setUp(self):
        self.signup_url = reverse("accounts:signup")
        self.verify_url = reverse("accounts:verify-email")
        self.resend_url = reverse("accounts:resend-otp")
        self.login_url = reverse("accounts:login")
        self.refresh_url = reverse("accounts:token_refresh")
        
        self.valid_payload = {
            "email": " Test@Example.COM  ",
            "password": "StrongPassword123!",
            "role": "seeker"
        }
        self.normalized_email = "test@example.com"

    def test_signup_valid(self):
        response = self.client.post(self.signup_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(email=self.normalized_email)
        self.assertNotEqual(user.username, self.normalized_email)
        self.assertFalse(user.profile.email_verified)
        self.assertEqual(EmailOTP.objects.count(), 1)
        
    def test_signup_rejects_username(self):
        payload = {**self.valid_payload, "username": "bad"}
        response = self.client.post(self.signup_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_signup_duplicate_verified(self):
        self.client.post(self.signup_url, self.valid_payload)
        user = User.objects.get(email=self.normalized_email)
        user.profile.email_verified = True
        user.profile.save()

        response = self.client.post(self.signup_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "email_already_registered")

    def test_signup_unverified_reregistration(self):
        self.client.post(self.signup_url, self.valid_payload)
        # Attempt again
        payload2 = {
            "email": "test@example.com",
            "password": "NewPassword123!",
            "role": "facilitator"
        }
        response = self.client.post(self.signup_url, payload2)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(email=self.normalized_email)
        self.assertEqual(user.profile.role, "facilitator")
        self.assertTrue(user.check_password("NewPassword123!"))
        
        otps = EmailOTP.objects.filter(user=user)
        self.assertEqual(otps.count(), 2)
        self.assertEqual(otps.filter(is_active=True).count(), 1)

    @mock.patch("accounts.services._generate_otp_code", return_value="123456")
    def test_otp_verification_success(self, mock_generate):
        self.client.post(self.signup_url, self.valid_payload)
        response = self.client.post(self.verify_url, {
            "email": self.valid_payload["email"],
            "otp": "123456"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email=self.normalized_email)
        self.assertTrue(user.profile.email_verified)
        
        otp = EmailOTP.objects.get(user=user)
        self.assertTrue(otp.is_used)
        self.assertFalse(otp.is_active)

    @mock.patch("accounts.services._generate_otp_code", return_value="123456")
    def test_otp_verification_failure_and_max_attempts(self, mock_generate):
        self.client.post(self.signup_url, self.valid_payload)
        
        for _ in range(5):
            res = self.client.post(self.verify_url, {
                "email": self.valid_payload["email"],
                "otp": "000000"
            })
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 6th attempt should return max attempts error even with correct OTP
        res = self.client.post(self.verify_url, {
            "email": self.valid_payload["email"],
            "otp": "123456"
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "invalid_otp")
        
        otp = EmailOTP.objects.get(user__email=self.normalized_email)
        self.assertEqual(otp.attempts, 5)
        self.assertFalse(otp.is_active)

    @mock.patch("accounts.services._generate_otp_code", return_value="123456")
    def test_otp_cannot_be_reused(self, mock_generate):
        self.client.post(self.signup_url, self.valid_payload)
        self.client.post(self.verify_url, {"email": self.normalized_email, "otp": "123456"})
        
        # Try again
        res = self.client.post(self.verify_url, {"email": self.normalized_email, "otp": "123456"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "already_verified")

    def test_resend_otp_behavior(self):
        self.client.post(self.signup_url, self.valid_payload)
        
        # Fake created_at to bypass cooldown
        otp = EmailOTP.objects.first()
        from django.utils import timezone
        import datetime
        otp.created_at = timezone.now() - datetime.timedelta(seconds=70)
        otp.save()

        res = self.client.post(self.resend_url, {"email": self.normalized_email})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        otps = EmailOTP.objects.filter(user__email=self.normalized_email)
        self.assertEqual(otps.count(), 2)
        self.assertEqual(otps.filter(is_active=True).count(), 1)
        self.assertFalse(otps.get(id=otp.id).is_active)

    def test_resend_cooldown(self):
        self.client.post(self.signup_url, self.valid_payload)
        res = self.client.post(self.resend_url, {"email": self.normalized_email})
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(res.data["code"], "cooldown_active")

    def test_resend_unknown_email(self):
        res = self.client.post(self.resend_url, {"email": "nobody@example.com"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_login_flow(self):
        self.client.post(self.signup_url, self.valid_payload)
        
        login_payload = {"email": self.normalized_email, "password": self.valid_payload["password"]}
        
        # Unverified
        res = self.client.post(self.login_url, login_payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data["code"], "email_not_verified")
        
        # Verify
        user = User.objects.get(email=self.normalized_email)
        user.profile.email_verified = True
        user.profile.save()
        
        # Valid login
        res = self.client.post(self.login_url, login_payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        
        # Wrong password
        res = self.client.post(self.login_url, {"email": self.normalized_email, "password": "wrong"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.data["code"], "invalid_credentials")
        
        # Unknown email
        res = self.client.post(self.login_url, {"email": "no@example.com", "password": "password"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class ConcurrencyTests(TransactionTestCase):
    """
    Real concurrency tests against PostgreSQL using TransactionTestCase
    (so database locks actually block other threads).
    """

    def setUp(self):
        self.email = "concurrent@example.com"
        self.password = "StrongPass123!"
        
        # Do initial setup in the main thread
        from .services import process_signup
        self.user, self.otp = process_signup(self.email, self.password, "seeker")

    def _verify_worker(self):
        # We need to manually manage DB connections in threads
        import django
        django.setup()
        from .services import process_verify_email
        from .exceptions import BaseCustomException
        
        try:
            process_verify_email(self.email, self.otp)
            return "success"
        except BaseCustomException as e:
            return e.detail["code"]
        except Exception as e:
            return str(e)
        finally:
            connection.close()

    def test_concurrent_otp_verification(self):
        # Fire 5 concurrent verification requests with the correct OTP
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._verify_worker) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # Exactly one should succeed, others should hit 'already_verified' or 'invalid_otp'
        successes = [r for r in results if r == "success"]
        self.assertEqual(len(successes), 1, f"Expected 1 success, got results: {results}")

        otp_obj = EmailOTP.objects.get(user=self.user)
        self.assertTrue(otp_obj.is_used)
        self.assertEqual(otp_obj.attempts, 0)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.email_verified)
