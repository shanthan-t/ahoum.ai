# Architecture and Design Decisions

This document outlines key technical decisions made while building the Ahoum Events Platform.

## 1. Default Django User

* **Problem:** The assignment required using Django's default `auth.User`, which lacks fields for 'role' or 'email verified status'.
* **Options:** Extend `AbstractUser`, monkey-patch `auth.User`, or use a `OneToOneField` profile.
* **Choice:** Created a decoupled `UserProfile` model linked via `OneToOneField`.
* **Trade-off:** Requires a `.select_related('profile')` join when querying users.
* **Verification:** `accounts/tests.py` ensures roles cannot be bypassed.

## 2. Email Uniqueness / Advisory Lock

* **Problem:** Default `auth.User` does not enforce global email uniqueness. Concurrent signups with the same email could result in duplicate accounts.
* **Options:** Unique constraint on `UserProfile`, or PostgreSQL advisory locks.
* **Choice:** Implemented PostgreSQL transaction-level advisory locks (`pg_advisory_xact_lock`) on a normalized email hash during signup.
* **Trade-off:** Ties the signup concurrency guarantee to PostgreSQL.
* **Verification:** Standard concurrent tests confirm only one account is created per email.

## 3. OTP Storage/Lifecycle

* **Problem:** Email OTPs must support 5-minute TTL, 5 attempts, and resend cooldowns.
* **Options:** Store in Redis/Cache or directly in PostgreSQL.
* **Choice:** Stored in PostgreSQL (`EmailOTP` model) linked to the user.
* **Trade-off:** Database writes for every authentication attempt, but guarantees strict transactional consistency without introducing Redis as an external dependency.
* **Verification:** Exhaustive edge-case testing in `accounts/tests.py`.

## 4. OTP Transaction/Locking

* **Problem:** Brute-force OTP attempts could bypass the attempt counter if processed concurrently.
* **Options:** Naive `update()` or row-level locking.
* **Choice:** Used `select_for_update()` during verification to serialize access to the OTP row.
* **Trade-off:** Negligible performance overhead for guaranteed security.
* **Verification:** `test_otp_verification_failure_and_max_attempts` verifies strict 5-attempt limit.

## 5. Enrollment Lifecycle

* **Problem:** Re-enrollment after cancellation conflicts with simple `UNIQUE(event, seeker)` database constraints if records are kept for historical tracking.
* **Options:** Soft-delete, delete-and-recreate, or state toggling.
* **Choice:** State toggling. The row transitions from `enrolled` → `canceled` → `enrolled`, updating timestamps.
* **Trade-off:** Simplified constraint (`UNIQUE`) but requires manual timestamp cleanup during reactivation.
* **Verification:** `test_reenrollment_behavior` confirms correct lifecycle toggling.

## 6. Event Row Locking (Concurrency)

* **Problem:** The assignment required guaranteeing enrollment limits under heavy concurrency (5 users, 1 seat remaining).
* **Options:** Optimistic concurrency control (version fields) or pessimistic row locking.
* **Choice:** Pessimistic locking. All capacity operations acquire a `select_for_update()` lock on the parent `Event`.
* **Trade-off:** Enrollment requests are strictly serialized, briefly blocking concurrent requests for the exact same event.
* **Verification:** `test_mass_enrollment_capacity_invariant` uses real threads hitting the database simultaneously to verify exactly 1 succeeds.

## 7. NULL Capacity

* **Problem:** Events may have unlimited capacity.
* **Options:** Use a magic number (e.g., `999999`) or `NULL`.
* **Choice:** `NULL` represents unlimited capacity.
* **Trade-off:** Requires conditional `capacity is None` logic in Python, but prevents arbitrary database limits.
* **Verification:** `test_capacity_validation` verifies behavior.

## 8. Search Strategy

* **Problem:** Events need to be searchable by title, description, and location.
* **Options:** PostgreSQL `SearchVector`/Elasticsearch or Django ORM `icontains`.
* **Choice:** Standard ORM `icontains`.
* **Trade-off:** Cannot handle typos or complex stemming, but prevents over-engineering for a compact assignment.
* **Verification:** Filter tests ensure exact date, text, and location matching.

## 9. Event Capacity/Deletion Rules

* **Problem:** Facilitators might attempt to reduce capacity below current enrollments or delete events with active seekers.
* **Options:** Cascade delete/cancel or block the action.
* **Choice:** Strictly block. Events cannot be deleted if enrollments exist, and capacity cannot be lowered below the active count.
* **Trade-off:** Requires facilitators to manually cancel events rather than destroying data blindly.
* **Verification:** Update/Delete endpoints tested for validation rejections.

## 10. Error Response Format

* **Problem:** Consistent error formatting is critical for frontend integrations.
* **Options:** Default DRF errors or custom exception handling.
* **Choice:** Overrode `drf_exceptions` to guarantee a consistent `{"detail": "...", "code": "..."}` shape.
* **Trade-off:** Requires domain-specific exception classes (e.g., `EventCapacityFullException`).
* **Verification:** All tests assert against the `code` key for deterministic validation.
