from django.db import transaction
from django.utils import timezone

from .exceptions import (
    ActiveEnrollmentsExistException,
    AlreadyCanceledException,
    AlreadyEnrolledException,
    CapacityTooLowException,
    EventFullException,
    EventStartedException,
    NotEnrolledException,
    NotFoundException,
)
from .models import Enrollment, Event


@transaction.atomic
def update_event_full(event_id, validated_data):
    """
    Updates the event with transactional safety, particularly validating capacity.
    """
    event = Event.objects.select_for_update().get(id=event_id)

    new_capacity = validated_data.get("capacity", event.capacity)

    if "capacity" in validated_data and new_capacity is not None:
        active_enrollments = event.enrollments.filter(status="enrolled").count()
        if new_capacity < active_enrollments:
            raise CapacityTooLowException(
                detail="Capacity cannot be reduced below current active enrollments.",
                code="capacity_too_low",
            )

    for key, value in validated_data.items():
        setattr(event, key, value)

    event.save()
    return event


@transaction.atomic
def delete_event(event_id):
    """
    Deletes an event, ensuring there are no active enrollments.
    """
    event = Event.objects.select_for_update().get(id=event_id)

    active_enrollments = event.enrollments.filter(status="enrolled").count()
    if active_enrollments > 0:
        raise ActiveEnrollmentsExistException(
            detail="Cannot delete an event with active enrollments.",
            code="active_enrollments_exist",
        )

    event.delete()


@transaction.atomic
def enroll_in_event(event_id, seeker):
    """
    Safely enroll a seeker in an event, guaranteeing capacity invariants.
    """
    try:
        event = Event.objects.select_for_update().get(id=event_id)
    except Event.DoesNotExist:
        raise NotFoundException(detail="Event not found.", code="not_found")

    if event.starts_at <= timezone.now():
        raise EventStartedException(
            detail="Cannot enroll in an event that has already started.",
            code="event_started",
        )

    enrollment = Enrollment.objects.filter(event=event, seeker=seeker).first()
    
    if enrollment and enrollment.status == "enrolled":
        raise AlreadyEnrolledException(
            detail="You are already enrolled in this event.", code="already_enrolled"
        )

    if event.capacity is not None:
        active_count = Enrollment.objects.filter(
            event=event, status="enrolled"
        ).count()
        if active_count >= event.capacity:
            raise EventFullException(
                detail="Event capacity has been reached.", code="event_full"
            )

    if enrollment:
        enrollment.status = "enrolled"
        enrollment.canceled_at = None
        enrollment.enrolled_at = timezone.now()
        enrollment.save(
            update_fields=["status", "canceled_at", "enrolled_at", "updated_at"]
        )
    else:
        enrollment = Enrollment.objects.create(
            event=event, seeker=seeker, status="enrolled"
        )

    return enrollment


@transaction.atomic
def cancel_enrollment(event_id, seeker):
    """
    Cancels an enrollment, maintaining transactional consistency with capacity updates.
    """
    try:
        event = Event.objects.select_for_update().get(id=event_id)
    except Event.DoesNotExist:
        raise NotFoundException(detail="Event not found.", code="not_found")

    enrollment = Enrollment.objects.filter(event=event, seeker=seeker).first()

    if not enrollment:
        raise NotEnrolledException(
            detail="You are not enrolled in this event.", code="not_enrolled"
        )

    if enrollment.status == "canceled":
        raise AlreadyCanceledException(
            detail="Enrollment is already canceled.", code="already_canceled"
        )

    enrollment.status = "canceled"
    enrollment.canceled_at = timezone.now()
    enrollment.save(update_fields=["status", "canceled_at", "updated_at"])

    return enrollment
