# Debugging Log

This document records real issues encountered during the implementation and verification phases of the Ahoum.ai Events Platform assignment. It details the symptoms, root causes, applied fixes, and the steps taken to verify correctness.

## Issue 1 — OTP Attempt Counter Transaction Rollback

### Symptom
Failed OTP verification attempts were not reliably persisting. When an invalid OTP or maximum-attempt condition raised an API exception, the attempt counter failed to increment in the database.

### Diagnosis
Code review of `accounts/services.py` revealed that the OTP verification logic was fully enclosed within a `transaction.atomic()` block. When a `BaseCustomException` was raised for an invalid OTP, Django automatically rolled back the entire database transaction.

### Root Cause
The mutation of the OTP failure state (incrementing the attempts counter) and the propagation of the API exception occurred within the same atomic transaction. The exception triggered a rollback, reverting the counter update.

### Fix
The `transaction.atomic()` block was scoped strictly to the lock acquisition and state mutation. Exceptions are now stored in an `error_to_raise` variable and raised explicitly after the transaction has successfully committed.

### Verification
The OTP attempt-limit tests pass, confirming that failed attempts persist correctly and that exhausted OTP records transition to an inactive state. The full 40-test suite passes successfully.

## Issue 2 — UserProfile One-To-One Test Access

### Symptom
During initial test creation for the authentication endpoints, a test attempt to access related profiles via `user.userprofile_set` failed with an `AttributeError`.

### Diagnosis
Inspection of the `User` to `UserProfile` relationship in `accounts/models.py` confirmed the relationship definition.

### Root Cause
The `UserProfile` model utilizes a `OneToOneField(User)` rather than a standard `ForeignKey(User)`. Consequently, Django maps the reverse relation as a single object (`user.profile`) rather than a QuerySet manager (`userprofile_set`).

### Fix
Corrected the test setup and assertion access patterns to reference the singular `user.profile` attribute to accurately match the `OneToOneField` relationship.

### Verification
Relevant authorization tests pass, and role-based permissions correctly evaluate the user profile attributes.

## Issue 3 — DRF Test Client with capacity=None

### Symptom
An automated test sending an event creation payload with `capacity=None` encountered an unexpected server-side error during parsing.

### Diagnosis
Debugging the request parsing revealed that the DRF test client was interpreting the `None` value inconsistently based on the default content type encoding.

### Root Cause
The DRF test client defaults to multipart form data encoding. When a payload contains explicit JSON `null` values (represented as `None` in Python), form data encoding does not reliably preserve the type, causing validation failures.

### Fix
Added the explicit argument `format="json"` to the test client's `post` call to ensure the payload was encoded as `application/json`.

### Verification
The `test_null_capacity_accepted` test successfully passes, verifying that unlimited-capacity events can be created correctly.

## Issue 4 — Datetime Query Parameter Encoding

### Symptom
A test utilizing a manually constructed URL query string containing an ISO 8601 timestamp (e.g., `2026-08-27T10:00:00+00:00`) yielded an incorrect queryset, occasionally returning a 400 Bad Request.

### Diagnosis
Inspection of the `request.query_params` dictionary within the view revealed that the timezone offset string `+00:00` was being parsed as ` 00:00` (with a leading space).

### Root Cause
The `+` character in a raw URL query string is interpreted as a space according to URL encoding standards. Because the query string was manually constructed and not explicitly URL-encoded, Django's parser incorrectly converted the timezone offset character.

### Fix
Passed the query parameters through the test client's dictionary argument (e.g., `client.get(url, {"starts_after": timestamp})`) instead of manually concatenating the string. This allows the DRF test client to handle URL encoding automatically.

### Verification
The `starts_after` and `starts_before` filter tests pass correctly and accurately filter ISO timestamp strings.

## Issue 5 — N+1 Query Discovered During Final Audit

### Symptom
During the final technical audit of the API endpoints, a review of the event discovery serialization process indicated potential database inefficiency.

### Diagnosis
The `EventListCreateView` retrieved all events and serialized them using `EventSerializer`. The serializer nested a `CreatorSerializer` which read the `created_by.id` attribute. While this specific fetch can sometimes avoid database hits, the architecture permitted unoptimized sequential queries for nested model traversal.

### Root Cause
The `get_queryset` method in `EventListCreateView` did not eagerly load the related `created_by` foreign key, leading to the potential for N+1 query execution during bulk serialization.

### Fix
Added `.select_related("created_by")` to the `Event.objects.all()` queryset in `EventListCreateView.get_queryset()`.

### Verification
The queryset now guarantees the retrieval of the related creator through a single database JOIN query instead of issuing iterative queries per event. The complete automated test suite continues to pass without degradation.
