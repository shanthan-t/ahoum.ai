import concurrent.futures
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Enrollment, Event
from accounts.models import UserProfile

User = get_user_model()


class EnrollmentAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.seeker = User.objects.create_user(username="seeker", email="s@a.com", password="password")
        UserProfile.objects.create(user=self.seeker, role="seeker", email_verified=True)

        self.seeker2 = User.objects.create_user(username="seeker2", email="s2@a.com", password="password")
        UserProfile.objects.create(user=self.seeker2, role="seeker", email_verified=True)

        self.facilitator = User.objects.create_user(username="fac", email="f@a.com", password="password")
        UserProfile.objects.create(user=self.facilitator, role="facilitator", email_verified=True)

        self.seeker_token = str(RefreshToken.for_user(self.seeker).access_token)
        self.fac_token = str(RefreshToken.for_user(self.facilitator).access_token)

        now = timezone.now()
        
        self.future_event = Event.objects.create(
            title="Future", description="D", location="L", language="En",
            starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=3),
            capacity=10, created_by=self.facilitator
        )
        
        self.future_unlimited = Event.objects.create(
            title="Unlimited", description="D", location="L", language="En",
            starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=3),
            capacity=None, created_by=self.facilitator
        )
        
        self.past_event = Event.objects.create(
            title="Past", description="D", location="L", language="En",
            starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1),
            capacity=10, created_by=self.facilitator
        )
        
        self.enroll_url = reverse("events:enroll", kwargs={"pk": self.future_event.pk})
        self.cancel_url = reverse("events:cancel", kwargs={"pk": self.future_event.pk})
        self.list_url = reverse("enrollment-list")

    # ==========================
    # AUTHORIZATION
    # ==========================
    def test_unauthenticated_cannot_enroll(self):
        res = self.client.post(self.enroll_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_facilitator_cannot_enroll(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac_token}")
        res = self.client.post(self.enroll_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ==========================
    # ENROLLMENT RULES
    # ==========================
    def test_seeker_can_enroll(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.enroll_url)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "enrolled")
        self.assertIsNotNone(res.data["enrolled_at"])
        self.assertIsNone(res.data["canceled_at"])

    def test_enroll_event_not_found(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        url = reverse("events:enroll", kwargs={"pk": 9999})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_enroll_past_event_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        url = reverse("events:enroll", kwargs={"pk": self.past_event.pk})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "event_started")

    def test_already_enrolled_rejected(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.enroll_url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "already_enrolled")

    def test_unlimited_capacity_accepted(self):
        url = reverse("events:enroll", kwargs={"pk": self.future_unlimited.pk})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_full_event_rejected(self):
        # Fill capacity to 10
        for i in range(10):
            u = User.objects.create_user(username=f"u{i}", email=f"{i}@a.com", password="password")
            Enrollment.objects.create(event=self.future_event, seeker=u, status="enrolled")
            
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.enroll_url)
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data["code"], "event_full")

    # ==========================
    # CANCELLATION
    # ==========================
    def test_successful_cancel(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.cancel_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "canceled")
        self.assertIsNotNone(res.data["canceled_at"])

    def test_already_canceled(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="canceled")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.cancel_url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "already_canceled")

    def test_not_enrolled_cancel(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.cancel_url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(res.data["code"], "not_enrolled")
        
    def test_cancel_frees_capacity(self):
        # Fill to 10
        for i in range(9):
            u = User.objects.create_user(username=f"u{i}", email=f"{i}@a.com", password="password")
            Enrollment.objects.create(event=self.future_event, seeker=u, status="enrolled")
        e = Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")
        
        # Seeker 2 tries, fails
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(self.seeker2).access_token)}")
        self.assertEqual(self.client.post(self.enroll_url).status_code, status.HTTP_409_CONFLICT)
        
        # Seeker 1 cancels
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        self.assertEqual(self.client.post(self.cancel_url).status_code, status.HTTP_200_OK)
        
        # Seeker 2 tries, succeeds
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(self.seeker2).access_token)}")
        self.assertEqual(self.client.post(self.enroll_url).status_code, status.HTTP_201_CREATED)

    # ==========================
    # RE-ENROLLMENT
    # ==========================
    def test_reenrollment_behavior(self):
        e = Enrollment.objects.create(
            event=self.future_event, seeker=self.seeker, status="canceled",
            enrolled_at=timezone.now() - timedelta(days=1),
            canceled_at=timezone.now()
        )
        old_pk = e.pk
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.enroll_url)
        
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["id"], old_pk)
        self.assertEqual(res.data["status"], "enrolled")
        self.assertIsNone(res.data["canceled_at"])
        
        e.refresh_from_db()
        self.assertEqual(e.status, "enrolled")
        self.assertIsNone(e.canceled_at)

    # ==========================
    # LISTING
    # ==========================
    def test_list_upcoming(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")
        Enrollment.objects.create(event=self.past_event, seeker=self.seeker, status="enrolled")
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_url) # defaults to upcoming
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["event"]["id"], self.future_event.id)

    def test_list_past(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")
        Enrollment.objects.create(event=self.past_event, seeker=self.seeker, status="canceled")
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_url, {"period": "past"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["event"]["id"], self.past_event.id)
        # Canceled should remain visible
        self.assertEqual(res.data["results"][0]["status"], "canceled")
        
    def test_list_invalid_period(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_url, {"period": "future"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "invalid_period")


class ConcurrencyTests(APITransactionTestCase):
    """
    Tests requiring threads for PostgreSQL concurrency testing.
    """
    def setUp(self):
        self.facilitator = User.objects.create_user(username="fac", email="f@a.com", password="password")
        UserProfile.objects.create(user=self.facilitator, role="facilitator", email_verified=True)
        
        now = timezone.now()
        self.event = Event.objects.create(
            title="Popular Event", description="D", location="L", language="En",
            starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=3),
            capacity=10, created_by=self.facilitator
        )
        
        # Create 9 active enrollments
        for i in range(9):
            u = User.objects.create_user(username=f"old_{i}", email=f"old{i}@a.com", password="password")
            UserProfile.objects.create(user=u, role="seeker", email_verified=True)
            Enrollment.objects.create(event=self.event, seeker=u, status="enrolled")
            
        self.enroll_url = reverse("events:enroll", kwargs={"pk": self.event.pk})
        self.cancel_url = reverse("events:cancel", kwargs={"pk": self.event.pk})

    def _worker_enroll(self, user):
        """Worker function for threads that uses its own db connection"""
        from rest_framework.test import APIClient
        client = APIClient()
        token = str(RefreshToken.for_user(user).access_token)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = client.post(self.enroll_url)
        connection.close()
        return res.status_code

    def _worker_cancel(self, user):
        from rest_framework.test import APIClient
        client = APIClient()
        token = str(RefreshToken.for_user(user).access_token)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = client.post(self.cancel_url)
        connection.close()
        return res.status_code

    def test_mass_enrollment_capacity_invariant(self):
        # 5 distinct seekers
        seekers = []
        for i in range(5):
            u = User.objects.create_user(username=f"new_{i}", email=f"new{i}@a.com", password="password")
            UserProfile.objects.create(user=u, role="seeker", email_verified=True)
            seekers.append(u)
            
        # Fire 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._worker_enroll, s) for s in seekers]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            
        # Check exactly 1 succeeds and 4 fail with 409
        successes = [r for r in results if r == status.HTTP_201_CREATED]
        conflicts = [r for r in results if r == status.HTTP_409_CONFLICT]
        
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 4)
        
        active_count = Enrollment.objects.filter(event=self.event, status="enrolled").count()
        self.assertEqual(active_count, 10)

    def test_duplicate_concurrent_enrollment(self):
        # 1 seeker, 2 concurrent requests
        seeker = User.objects.create_user(username="dup", email="dup@a.com", password="password")
        UserProfile.objects.create(user=seeker, role="seeker", email_verified=True)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._worker_enroll, seeker) for _ in range(2)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            
        successes = [r for r in results if r == status.HTTP_201_CREATED]
        alreadys = [r for r in results if r == status.HTTP_400_BAD_REQUEST]
        
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(alreadys), 1)
        
        # Only one row exists
        self.assertEqual(Enrollment.objects.filter(event=self.event, seeker=seeker).count(), 1)

    def test_cancellation_and_enrollment_concurrency(self):
        # Fill capacity to exactly 10
        user10 = User.objects.create_user(username="u10", email="u10@a.com", password="password")
        UserProfile.objects.create(user=user10, role="seeker", email_verified=True)
        Enrollment.objects.create(event=self.event, seeker=user10, status="enrolled")
        self.assertEqual(Enrollment.objects.filter(event=self.event, status="enrolled").count(), 10)
        
        seeker_new = User.objects.create_user(username="new11", email="new11@a.com", password="password")
        UserProfile.objects.create(user=seeker_new, role="seeker", email_verified=True)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # u10 cancels, new11 enrolls concurrently
            f_cancel = executor.submit(self._worker_cancel, user10)
            f_enroll = executor.submit(self._worker_enroll, seeker_new)
            
            c_res = f_cancel.result()
            e_res = f_enroll.result()
            
        self.assertEqual(c_res, status.HTTP_200_OK)
        # Because we use transaction locks, enrollment might happen *before* cancel completes and get 409
        # or *after* cancel completes and get 201. Both are valid states.
        self.assertIn(e_res, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT])
        
        # Capacity is guaranteed <= 10
        active_count = Enrollment.objects.filter(event=self.event, status="enrolled").count()
        self.assertLessEqual(active_count, 10)
