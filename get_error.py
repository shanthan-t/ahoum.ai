import os
import django
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ahoum.settings")
django.setup()

from django.test import Client
from django.utils import timezone
from events.models import Event
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import UserProfile

User = get_user_model()

try:
    seeker = User.objects.create_user(username="testseeker", email="test@a.com", password="pwd")
    UserProfile.objects.create(user=seeker, role="seeker", email_verified=True)
    token = str(RefreshToken.for_user(seeker).access_token)
    
    c = Client()
    now = timezone.now()
    try:
        res = c.get(f"/api/events/?starts_before={now.isoformat()}", HTTP_AUTHORIZATION=f"Bearer {token}")
        print("Status:", res.status_code)
    except Exception as e:
        traceback.print_exc()
except Exception as e:
    traceback.print_exc()
