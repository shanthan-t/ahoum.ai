from django.conf import settings
from django.db import models


class Event(models.Model):
    """
    An event created by a Facilitator. Seekers can enroll in events.
    capacity=NULL means unlimited capacity.
    """

    title = models.CharField(max_length=255)
    description = models.TextField()
    language = models.CharField(max_length=50)
    location = models.CharField(max_length=255)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["starts_at"],
                name="event_starts_at_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(ends_at__gt=models.F("starts_at")),
                name="event_ends_after_starts",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(capacity__isnull=True)
                    | models.Q(capacity__gt=0)
                ),
                name="event_capacity_positive_or_null",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.starts_at:%Y-%m-%d %H:%M} UTC)"


class Enrollment(models.Model):
    """
    Records a Seeker's enrollment in an Event.
    One row per (event, seeker) pair — re-enrollment reactivates the row.
    """

    class Status(models.TextChoices):
        ENROLLED = "enrolled", "Enrolled"
        CANCELED = "canceled", "Canceled"

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    seeker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "seeker"],
                name="enrollment_unique_event_seeker",
            ),
            models.CheckConstraint(
                check=models.Q(status__in=["enrolled", "canceled"]),
                name="enrollment_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event", "status"],
                name="enrollment_event_status_idx",
            ),
            models.Index(
                fields=["seeker", "status"],
                name="enrollment_seeker_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.seeker.email} → {self.event.title} ({self.status})"
