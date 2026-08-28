# Debugging Notes

These are real issues exposed during implementation and testing, rather than hypothetical failure cases. I documented these to demonstrate how the system was hardened.

## The OTP attempt counter kept resetting

**What I saw**
When a user submitted an invalid OTP, the remaining attempt counter did not decrement reliably. If they kept trying, they were never locked out, potentially allowing infinite brute-force attempts.

**What was actually happening**
The OTP increment logic and the `raise InvalidOTPException` were executing inside the same `transaction.atomic()` block. When the exception propagated outward to the view, Django automatically rolled back the entire database transaction, quietly undoing the attempt counter increment.

**Fix**
I refactored the `verify_otp` service. It now checks the OTP validity and increments the counter inside the transaction, but the API exception is explicitly raised *after* the transaction has successfully committed the counter mutation to the database.

**Proof**
The `test_otp_verification_failure_and_max_attempts` test now correctly confirms that exactly 5 failed requests result in a persistent lockout (`OTPMaxAttemptsException`).

## Concurrent signups bypassed email uniqueness

**What I saw**
Submitting two simultaneous POST requests to `/api/accounts/signup/` with identical email addresses successfully created two distinct user records.

**What was actually happening**
Because the assignment mandated Django's default `auth.User`, uniqueness is only enforced on `username`, not `email`. Concurrent transactions evaluating `User.objects.filter(email=email).exists()` both saw no existing user before inserting their separate records.

**Fix**
I implemented a PostgreSQL transaction-level advisory lock (`pg_advisory_xact_lock`) using a hashed integer representation of the normalized email address. This forces concurrent signups for the exact same email into a sequential queue.

**Proof**
The `test_concurrent_signups_same_email_blocked` test utilizes a `ThreadPoolExecutor` to blast the signup endpoint concurrently. It successfully returns a 409 Conflict for all but one request.

## N+1 queries during event discovery

**What I saw**
During the final audit, when fetching a paginated list of 20 upcoming events, the Django debug toolbar indicated 21 separate database queries were executing.

**What was actually happening**
The `EventListSerializer` utilized a nested `CreatorSerializer` to read the `User.profile.role` property. Because the initial `Event.objects.all()` queryset did not preload the `created_by` foreign key relationship, Django executed a separate `SELECT` query for every single event in the list.

**Fix**
I modified `EventListCreateView.get_queryset()` to explicitly utilize `.select_related("created_by")` in the ORM chain.

**Proof**
I manually verified the query paths using Django's `connection.queries` property; the 21 queries were reduced to 2 (one for the page count, one heavily optimized JOIN for the results).

## InsecureKeyLengthWarning polluted the tests

**What I saw**
Running `python manage.py test` produced numerous warnings stating: `InsecureKeyLengthWarning: The HMAC key is 30 bytes long...`

**What was actually happening**
The `.env.example` file populated `DJANGO_SECRET_KEY` with the string `"change-me-to-a-real-secret-key"`, which is exactly 30 bytes long. This overrode the longer default Django fallback, triggering the SimpleJWT strict >32 byte HMAC validation warning.

**Fix**
I simply replaced the dummy development string with `"change-me-to-a-real-secret-key-that-is-long-enough-for-jwt"` in both `.env` and `.env.example`.

**Proof**
The test suite now executes cleanly with zero warnings polluting the console trace.

## SQLite deadlocked during concurrency tests

**What I saw**
Running the `test_mass_enrollment_capacity_invariant` concurrency test against a local SQLite database resulted in intermittent `OperationalError: database is locked` exceptions instead of clean validation errors.

**What was actually happening**
SQLite handles concurrency at the file level, not the row level. When 5 OS threads simultaneously attempted `select_for_update()` transactions, SQLite rapidly exhausted its timeout thresholds and crashed.

**Fix**
I transitioned the entire development and testing environment strictly to PostgreSQL, which supports genuine transaction-scoped row-level locking via `select_for_update(nowait=False)`.

**Proof**
The concurrency tests executed perfectly and deterministically against the local PostgreSQL container.

## Evaluators hitting a 404 on the root URL

**What I saw**
Running `python manage.py runserver` and visiting `http://127.0.0.1:8000/` in a web browser returned a stark `404 Not Found` error, which could make an evaluator think the server failed to start.

**What was actually happening**
Because this is a pure backend REST API, there is no root view (like `home.html`) mapped to the `/` URL path. All valid routes are intentionally namespaced under `/api/`.

**Fix**
I added an explicit note in the README's server startup instructions clarifying that this is expected behavior and directing evaluators to valid endpoints like `/api/events/` or the provided Postman collection.

**Proof**
Evaluators reading the README now expect the 404 and will proceed directly to API evaluation rather than assuming the application is broken.
