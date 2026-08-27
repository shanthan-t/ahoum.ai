from django.urls import path

from .views import (
    CancelEnrollmentView,
    EnrollView,
    EventDetailUpdateDeleteView,
    EventListCreateView,
    FacilitatorEventListView,
)

app_name = "events"

urlpatterns = [
    path("", EventListCreateView.as_view(), name="list_create"),
    path("mine/", FacilitatorEventListView.as_view(), name="mine"),
    path("<int:pk>/", EventDetailUpdateDeleteView.as_view(), name="detail_update_delete"),
    path("<int:pk>/enroll/", EnrollView.as_view(), name="enroll"),
    path("<int:pk>/cancel/", CancelEnrollmentView.as_view(), name="cancel"),
]
