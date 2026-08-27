from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import InvalidPeriodException
from .models import Enrollment, Event
from .permissions import IsEventOwner, IsFacilitator, IsSeeker
from .serializers import (
    EnrollmentSerializer,
    EventSerializer,
    FacilitatorEventSerializer,
)
from .services import (
    cancel_enrollment,
    delete_event,
    enroll_in_event,
    update_event_full,
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class EventListCreateView(generics.ListCreateAPIView):
    serializer_class = EventSerializer
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsFacilitator()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Event.objects.select_related("created_by").all().order_by("starts_at", "id")

        q = self.request.query_params.get("q")
        location = self.request.query_params.get("location")
        language = self.request.query_params.get("language")
        starts_after = self.request.query_params.get("starts_after")
        starts_before = self.request.query_params.get("starts_before")

        has_date_filter = False

        if starts_after:
            has_date_filter = True
            queryset = queryset.filter(starts_at__gte=starts_after)

        if starts_before:
            has_date_filter = True
            queryset = queryset.filter(starts_at__lte=starts_before)

        if not has_date_filter:
            queryset = queryset.filter(starts_at__gte=timezone.now())

        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(description__icontains=q)
            )

        if location:
            queryset = queryset.filter(location__icontains=location)

        if language:
            queryset = queryset.filter(language__iexact=language)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class EventDetailUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EventSerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsFacilitator(), IsEventOwner()]
        return super().get_permissions()

    def get_queryset(self):
        return Event.objects.all()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)

        updated_instance = update_event_full(instance.id, serializer.validated_data)

        return Response(self.get_serializer(updated_instance).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_event(instance.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FacilitatorEventListView(generics.ListAPIView):
    serializer_class = FacilitatorEventSerializer
    permission_classes = [IsFacilitator]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return (
            Event.objects.filter(created_by=self.request.user)
            .annotate(
                enrollment_count=Count(
                    "enrollments", filter=Q(enrollments__status="enrolled")
                )
            )
            .order_by("-created_at")
        )


class EnrollView(APIView):
    permission_classes = [IsSeeker]

    def post(self, request, pk, *args, **kwargs):
        enrollment = enroll_in_event(event_id=pk, seeker=request.user)
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CancelEnrollmentView(APIView):
    permission_classes = [IsSeeker]

    def post(self, request, pk, *args, **kwargs):
        enrollment = cancel_enrollment(event_id=pk, seeker=request.user)
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EnrollmentListView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsSeeker]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Enrollment.objects.filter(seeker=self.request.user).select_related("event")
        period = self.request.query_params.get("period", "upcoming")

        if period == "upcoming":
            queryset = queryset.filter(event__starts_at__gte=timezone.now()).order_by(
                "event__starts_at", "id"
            )
        elif period == "past":
            queryset = queryset.filter(event__starts_at__lt=timezone.now()).order_by(
                "-event__starts_at", "-id"
            )
        else:
            raise InvalidPeriodException(
                detail="Invalid enrollment period.", code="invalid_period"
            )

        return queryset
