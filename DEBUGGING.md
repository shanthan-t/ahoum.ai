# Debugging Log

This document records the material bugs encountered and resolved during the development of the Ahoum Events Platform backend.

## Issue 1 — OTP Attempt Counter Transaction Rollback

### Symptom
When a user submitted an invalid OTP, the remaining attempt counter did not decrement reliably, potentially allowing infinite brute-force attempts.

### Root Cause
The OTP increment logic and the `raise InvalidOTPException` were executed inside the same `transaction.atomic()` block. When the exception propagated outward, Django rolled back the entire database transaction, undoing the attempt counter increment.

### Fix
The `verify_otp` service was refactored to check the OTP validity and increment the counter inside the transaction, but the API exception was raised *after* the transaction successfully committed the counter mutation to the database.

### Verification
The `test_otp_verification_failure_and_max_attempts` test confirmed that exactly 5 failed requests resulted in a persistent lockout (`OTPMaxAttemptsException`).

---

## Issue 2 — Concurrent Email Signup Race Condition

### Symptom
Submitting two simultaneous POST requests to `/api/accounts/signup/` with identical email addresses successfully created two distinct `User` records.

### Root Cause
Django's default `auth.User` model enforces uniqueness on `username`, but not on `email`. Concurrent transactions evaluating `User.objects.filter(email=email).exists()` both saw no existing user before inserting their records.

### Fix
Implemented a PostgreSQL transaction-level advisory lock (`pg_advisory_xact_lock`) utilizing a hashed integer representation of the normalized email address. This forces concurrent signups for the same email into a sequential queue.

### Verification
The `test_concurrent_signups_same_email_blocked` test utilizes a `ThreadPoolExecutor` to blast the signup endpoint concurrently, successfully returning a 409 Conflict for all but one request.

---

## Issue 3 — N+1 Query in Event Discovery List

### Symptom
When fetching a paginated list of 20 upcoming events, the Django debug toolbar indicated 21 separate database queries were executing.

### Root Cause
The `EventListSerializer` utilized a nested `CreatorSerializer` which attempted to read the `User.profile.role` property. Because the initial `Event.objects.all()` queryset did not preload the `created_by` foreign key relationship, Django executed a separate `SELECT` query for every event in the list.

### Fix
Modified `EventListCreateView.get_queryset()` to explicitly utilize `.select_related("created_by")` in the ORM chain.

### Verification
Manually verified query paths using Django's `connection.queries` property; the 21 queries were reduced to 2 (one for the page count, one heavily optimized JOIN for the results).

---

## Issue 4 — InsecureKeyLengthWarning in Tests

### Symptom
Running `python manage.py test` produced numerous warnings stating: `InsecureKeyLengthWarning: The HMAC key is 30 bytes long...`

### Root Cause
The `.env.example` file populated `DJANGO_SECRET_KEY` with the string `"change-me-to-a-real-secret-key"`, which is exactly 30 bytes long. This overrode the longer default Django fallback, triggering the SimpleJWT strict >32 byte HMAC validation warning.

### Fix
Replaced the dummy development string with `"change-me-to-a-real-secret-key-that-is-long-enough-for-jwt"` in both `.env` and `.env.example`.

### Verification
`python manage.py test` executed cleanly with zero warnings polluting the console trace.

---

## Issue 5 — SQLite Database Lock Errors During Testing

### Symptom
Running the `test_mass_enrollment_capacity_invariant` concurrency test against a local SQLite database resulted in intermittent `OperationalError: database is locked` exceptions instead of clean validation errors.

### Root Cause
SQLite handles concurrency at the file level, not the row level. When 5 OS threads simultaneously attempted `select_for_update()` transactions, SQLite rapidly exhausted its timeout thresholds.

### Fix
Transitioned the entire development and testing environment strictly to PostgreSQL, which supports genuine transaction-scoped row-level locking via `select_for_update(nowait=False)`.

### Verification
The concurrency tests executed perfectly and deterministically against the local PostgreSQL container.
