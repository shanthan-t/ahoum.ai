"""
URL configuration for ahoum project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from events.views import EnrollmentListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/events/", include("events.urls")),
    path("api/enrollments/", EnrollmentListView.as_view(), name="enrollment-list"),
]
