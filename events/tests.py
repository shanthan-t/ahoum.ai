from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Enrollment, Event
from accounts.models import UserProfile

User = get_user_model()


class EventAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.seeker = User.objects.create_user(
            username="seeker", email="seeker@example.com", password="password"
        )
        UserProfile.objects.create(user=self.seeker, role="seeker", email_verified=True)

        self.facilitator1 = User.objects.create_user(
            username="fac1", email="fac1@example.com", password="password"
        )
        UserProfile.objects.create(user=self.facilitator1, role="facilitator", email_verified=True)

        self.facilitator2 = User.objects.create_user(
            username="fac2", email="fac2@example.com", password="password"
        )
        UserProfile.objects.create(user=self.facilitator2, role="facilitator", email_verified=True)

        # Generate tokens
        self.seeker_token = str(RefreshToken.for_user(self.seeker).access_token)
        self.fac1_token = str(RefreshToken.for_user(self.facilitator1).access_token)
        self.fac2_token = str(RefreshToken.for_user(self.facilitator2).access_token)

        # Base URLs
        self.list_create_url = reverse("events:list_create")
        self.mine_url = reverse("events:mine")

        # Create some events
        now = timezone.now()
        self.past_event = Event.objects.create(
            title="Past Event",
            description="A past event.",
            language="English",
            location="Bangalore",
            starts_at=now - timedelta(days=2),
            ends_at=now - timedelta(days=1),
            capacity=10,
            created_by=self.facilitator1,
        )

        self.future_event = Event.objects.create(
            title="Future Event Python",
            description="Learn advanced python.",
            language="English",
            location="Remote",
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=3),
            capacity=10,
            created_by=self.facilitator1,
        )

        self.fac2_event = Event.objects.create(
            title="Fac2 Event",
            description="Desc.",
            language="Hindi",
            location="Mumbai",
            starts_at=now + timedelta(days=5),
            ends_at=now + timedelta(days=6),
            capacity=None,
            created_by=self.facilitator2,
        )

        self.valid_payload = {
            "title": "New Event",
            "description": "Desc",
            "language": "French",
            "location": "Paris",
            "starts_at": (now + timedelta(days=10)).isoformat(),
            "ends_at": (now + timedelta(days=11)).isoformat(),
            "capacity": 50,
        }

    # ==========================
    # AUTHORIZATION
    # ==========================
    def test_unauthenticated_rejected(self):
        res = self.client.get(self.list_create_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_seeker_cannot_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.post(self.list_create_url, self.valid_payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_seeker_cannot_update_delete(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        url = reverse("events:detail_update_delete", kwargs={"pk": self.future_event.pk})
        self.assertEqual(self.client.patch(url, {}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

    def test_facilitator_can_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        res = self.client.post(self.list_create_url, self.valid_payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["title"], "New Event")

    def test_facilitator_can_update_own(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        url = reverse("events:detail_update_delete", kwargs={"pk": self.future_event.pk})
        res = self.client.patch(url, {"title": "Updated Title"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], "Updated Title")

    def test_facilitator_cannot_update_other(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        url = reverse("events:detail_update_delete", kwargs={"pk": self.fac2_event.pk})
        res = self.client.patch(url, {"title": "Hack"})
        # Should return 404 to hide resource existence
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ==========================
    # VALIDATION
    # ==========================
    def test_ends_at_before_starts_at_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        payload = self.valid_payload.copy()
        payload["ends_at"] = (timezone.now() + timedelta(days=9)).isoformat()
        res = self.client.post(self.list_create_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "invalid_date_range")

    def test_negative_capacity_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        payload = self.valid_payload.copy()
        payload["capacity"] = -5
        res = self.client.post(self.list_create_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_capacity_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        payload = self.valid_payload.copy()
        payload["capacity"] = 0
        res = self.client.post(self.list_create_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_null_capacity_accepted(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        payload = self.valid_payload.copy()
        payload["capacity"] = None
        res = self.client.post(self.list_create_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_empty_strings_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        payload = self.valid_payload.copy()
        payload["title"] = "   "
        res = self.client.post(self.list_create_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ==========================
    # DISCOVERY & SEARCH
    # ==========================
    def test_default_discovery_excludes_past(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_create_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        titles = [r["title"] for r in res.data["results"]]
        self.assertNotIn("Past Event", titles)
        self.assertIn("Future Event Python", titles)

    def test_search_q_title_and_desc(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_create_url + "?q=python")
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], "Future Event Python")

    def test_location_partial_match(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_create_url + "?location=mumb")
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], "Fac2 Event")

    def test_language_exact_case_insensitive(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_create_url + "?language=hindi")
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], "Fac2 Event")

    def test_starts_before_includes_historical(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        now = timezone.now()
        res = self.client.get(self.list_create_url, {"starts_before": now.isoformat()})
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], "Past Event")

    def test_upcoming_ordering(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.seeker_token}")
        res = self.client.get(self.list_create_url)
        results = res.data["results"]
        self.assertTrue(results[0]["starts_at"] < results[1]["starts_at"])

    # ==========================
    # COUNTS & EDGE CASES
    # ==========================
    def test_facilitator_mine_counts(self):
        # Enroll seeker in future_event
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")
        
        # Cancelled enrollment shouldn't count
        Enrollment.objects.create(event=self.future_event, seeker=self.facilitator2, status="canceled")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        res = self.client.get(self.mine_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        event_data = next(e for e in res.data["results"] if e["id"] == self.future_event.id)
        self.assertEqual(event_data["enrollment_count"], 1)
        self.assertEqual(event_data["available_seats"], 9)

    def test_capacity_reduction_below_active_rejected(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")
        Enrollment.objects.create(event=self.future_event, seeker=self.facilitator2, status="enrolled")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        url = reverse("events:detail_update_delete", kwargs={"pk": self.future_event.pk})
        
        # Try to reduce to 1 (below 2 active)
        res = self.client.patch(url, {"capacity": 1})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "capacity_too_low")
        
        # Reduce to 2 is allowed
        res = self.client.patch(url, {"capacity": 2})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_delete_with_active_enrollments_rejected(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="enrolled")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        url = reverse("events:detail_update_delete", kwargs={"pk": self.future_event.pk})
        
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data["code"], "active_enrollments_exist")

    def test_delete_with_canceled_enrollments_allowed(self):
        Enrollment.objects.create(event=self.future_event, seeker=self.seeker, status="canceled")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.fac1_token}")
        url = reverse("events:detail_update_delete", kwargs={"pk": self.future_event.pk})
        
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
