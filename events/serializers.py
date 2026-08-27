from rest_framework import serializers

from .exceptions import InvalidCapacityException, InvalidDateRangeException
from .models import Event, Enrollment


class CreatorSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class EventSerializer(serializers.ModelSerializer):
    created_by = CreatorSerializer(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "language",
            "location",
            "starts_at",
            "ends_at",
            "capacity",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Title cannot be empty.")
        return val

    def validate_description(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Description cannot be empty.")
        return val

    def validate_language(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Language cannot be empty.")
        return val

    def validate_location(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Location cannot be empty.")
        return val

    def validate(self, attrs):
        # Handle partial updates gracefully
        if self.instance:
            starts_at = attrs.get("starts_at", self.instance.starts_at)
            ends_at = attrs.get("ends_at", self.instance.ends_at)
        else:
            starts_at = attrs.get("starts_at")
            ends_at = attrs.get("ends_at")

        if starts_at and ends_at and ends_at <= starts_at:
            raise InvalidDateRangeException(
                detail="Event must end after it starts.", code="invalid_date_range"
            )

        if "capacity" in attrs:
            capacity = attrs.get("capacity")
            if capacity is not None and capacity <= 0:
                raise InvalidCapacityException(
                    detail="Capacity must be greater than 0 or unlimited.",
                    code="invalid_capacity",
                )

        return attrs


class FacilitatorEventSerializer(EventSerializer):
    enrollment_count = serializers.IntegerField(read_only=True)
    available_seats = serializers.SerializerMethodField()

    class Meta(EventSerializer.Meta):
        fields = EventSerializer.Meta.fields + [
            "enrollment_count",
            "available_seats",
        ]

    def get_available_seats(self, obj):
        if obj.capacity is not None:
            count = getattr(obj, "enrollment_count", 0)
            return obj.capacity - count
        return None


class EventBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "starts_at", "ends_at", "location"]


class EnrollmentSerializer(serializers.ModelSerializer):
    event = EventBasicSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = ["id", "status", "enrolled_at", "canceled_at", "event"]
