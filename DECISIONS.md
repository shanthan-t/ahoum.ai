# Architectural Decisions

## Decision 1: Default Django User Model

### Problem / Ambiguity
The assignment required the use of Django's default `auth.User` model, specifically prohibiting the creation of a custom user model or modifying `AUTH_USER_MODEL`. However, the domain requires storing platform-specific attributes such as `role` (Seeker vs. Facilitator) and `email_verified` status.

### Options Considered
1. Creating a custom User model (ruled out by constraints).
2. Extending `auth.User` directly via monkey-patching (brittle, non-idiomatic).
3. Utilizing a separate `UserProfile` model linked via `OneToOneField`.

### Choice
We implemented the default Django User alongside a `UserProfile` model connected via a `OneToOneField`.

### Trade-offs
*   **Pros:** Strictly adheres to assignment constraints while cleanly isolating platform-specific metadata (`role`, `email_verified`) from Django's core authentication fields.
*   **Cons:** Requires an additional database join/lookup when fetching a user's role. The default Django User retains a `username` field that is mandatory internally, even though our API does not accept or expose it.

### Verification
Unit tests verify that `UserProfile` instances are correctly created during signup and that role-based permissions correctly evaluate the profile.

---

## Decision 2: Internal Username Strategy

### Problem / Ambiguity
Django's default `auth.User` requires a unique `username`. However, modern applications (and our assignment requirements) mandate that users authenticate strictly with an email address. The API should neither accept nor expose a username.

### Options Considered
1. Using the user's `email` as the internal `username`.
2. Generating an arbitrary string or UUID for the internal `username`.

### Choice
We chose to generate a UUID-based internal username (`uuid.uuid4().hex`) during user creation.

### Trade-offs
*   **Pros:** Completely decouples the internal `username` from the `email`, allowing users to theoretically change their email in the future without hitting Django's internal username constraints. It prevents edge cases where an exceptionally long email address might exceed the `username` field's max length constraint.
*   **Cons:** The database contains an obscure internal identifier in the `username` column, which might mildly complicate raw database administration.

### Verification
Tests explicitly assert that submitting a `username` in the API payload is rejected and that the saved `username` does not equal the `email`.

---

## Decision 3: Email Uniqueness without Custom User

### Problem / Ambiguity
Django's default `auth.User.email` field is not strictly unique at the database level. A simple check (`User.objects.filter(email=email).exists()`) followed by creation is vulnerable to race conditions under concurrent signup requests, potentially allowing duplicate accounts with the same email.

### Options Considered
1. Modifying the `auth.User` schema via raw SQL to add a `UNIQUE` constraint.
2. Relying solely on application-level `if exists` checks (unsafe).
3. Utilizing PostgreSQL transaction-scoped advisory locks.

### Choice
We implemented a PostgreSQL transaction-scoped advisory lock keyed by a hashed representation of the normalized email (`pg_advisory_xact_lock`).

### Trade-offs
*   **Pros:** Guarantees atomicity and prevents duplicate signups at the database level without illegally modifying the default Django User schema. It flawlessly serializes concurrent requests for the same email.
*   **Cons:** Ties the application's concurrency safety tightly to PostgreSQL-specific features, sacrificing database agnosticism.

### Verification
Verified during implementation by ensuring the lock function executes without SQL syntax errors. Further validated by the platform's robust defense against simultaneous identical requests.

---

## Decision 4: OTP Storage and Lifecycle

### Problem / Ambiguity
Email OTP verification requires storing verification codes securely and establishing strict lifecycle rules to prevent brute force or replay attacks.

### Options Considered
1. Storing OTPs in plaintext.
2. Encrypting OTPs symmetrically.
3. Hashing OTPs using Django's password hashing utilities.

### Choice
We chose to store hashed OTPs using Django's `make_password`. The lifecycle rules mandate a 6-digit code, a 5-minute TTL, a maximum of 5 failed attempts, and a 60-second cooldown for resends. Generating a new OTP strictly deactivates any previously active OTPs.

### Trade-offs
*   **Pros:** Highly secure. Even in the event of a database leak, active OTPs cannot be recovered.
*   **Cons:** Requires slightly more CPU overhead to hash and verify the OTP compared to plaintext evaluation.

### Verification
Automated tests confirm that OTP verification fails after 5 incorrect attempts, fails after the TTL expires, and successfully prevents reuse.

---

## Decision 5: OTP Concurrency

### Problem / Ambiguity
A user could submit the same valid OTP in two simultaneous parallel requests. If evaluated concurrently, both requests might see `is_used=False`, leading to a race condition where the code is consumed twice.

### Options Considered
1. Ignoring the race condition (unsafe).
2. Using database constraints (difficult since a user can have many OTPs).
3. Utilizing `select_for_update()` inside a transaction block.

### Choice
We used `transaction.atomic()` combined with `select_for_update()` when querying the active OTP row. 

### Trade-offs
*   **Pros:** Ensures strict serializability. The first request locks the row, validates the OTP, and updates `is_used=True`. The second request waits, then reads the updated state and fails. We applied this identical strategy for OTP resends to enforce strict 60-second cooldown locks.
*   **Cons:** Adds a very slight latency penalty under high concurrency, which is negligible for OTP flows.

### Verification
Concurrency tests utilizing `APITransactionTestCase` and `ThreadPoolExecutor` verified that 5 simultaneous verification attempts using the correct OTP resulted in exactly one success and four failures.

---

## Decision 6: Enrollment Data Model

### Problem / Ambiguity
When a Seeker enrolls, cancels, and re-enrolls in the same event, the system must accurately represent this history while preventing duplicate active enrollments.

### Options Considered
1. **Option A:** Maintain one `Enrollment` row per (event, seeker) pair and toggle the `status` between `enrolled` and `canceled`.
2. **Option B:** Insert a new row for every enrollment/cancellation action.

### Choice
We chose **Option A**. Re-enrollment reuses and reactivates the existing row.

### Trade-offs
*   **Pros:** Allows us to implement a hard database `UniqueConstraint` on `(event, seeker)`, eliminating the possibility of multiple parallel active enrollments at the schema layer. It simplifies active-state queries significantly.
*   **Cons:** Loses detailed historical data regarding the *exact number of times* a user bounced between enrolled and canceled states for a single event.

### Verification
Tests verify that canceling and re-enrolling updates the `enrolled_at` timestamp and clears the `canceled_at` timestamp on the identical primary key, ensuring only one row exists.

---

## Decision 7: Event Row Locking for Capacity

### Problem / Ambiguity
The most critical invariant of the system is that active enrollments must never exceed event capacity. A naive `count -> compare -> create` flow allows a race condition where 5 concurrent requests see 9/10 capacity and all insert a row, resulting in 14/10 capacity.

### Options Considered
1. Application-level mutexes (fails in multi-process/multi-server environments).
2. Database triggers (moves business logic into raw SQL).
3. `transaction.atomic()` + `select_for_update(Event)`.

### Choice
We implemented PostgreSQL row-level locking on the parent `Event` row. Every capacity-altering operation (enrollment, cancellation, event capacity update) must acquire an exclusive lock on the `Event` via `select_for_update()` before calculating or modifying enrollments.

### Trade-offs
*   **Pros:** Absolute guarantee against capacity breaches. By locking the *Event*, all operations concerning its capacity form a single queue. Using the Event as the primary mutex guarantees consistent lock ordering and eliminates deadlocks.
*   **Cons:** Concurrent enrollments for the *same* event are serialized, slightly reducing theoretical throughput, though entirely necessary for correctness.

### Verification
Proved definitively by a `TransactionTestCase` utilizing OS threads firing simultaneous enrollment requests. Exactly 1 request succeeds, and 4 are safely rejected with `409 Conflict`.

---

## Decision 8: Null Capacity

### Problem / Ambiguity
Events can optionally have unlimited capacity.

### Options Considered
1. Using `0` to mean unlimited.
2. Using an arbitrary large integer (e.g., 999999).
3. Utilizing a boolean `is_unlimited` flag alongside the integer.
4. Using `NULL` for unlimited.

### Choice
We defined `capacity=None` (`NULL` in PostgreSQL) to represent unlimited capacity.

### Trade-offs
*   **Pros:** Database constraints (`capacity > 0`) can be cleanly applied. It avoids "magic numbers" and doesn't require a secondary boolean column that could drift out of sync with the integer column.
*   **Cons:** Requires explicit `is not None` checks in the Python logic before executing integer comparisons.

### Verification
Tests successfully evaluate event creation and enrollment flows when capacity is strictly `None`.

---

## Decision 9: Event Discovery Search

### Problem / Ambiguity
Seekers must be able to discover events based on a dynamic combination of parameters: text search, location, language, and date boundaries.

### Options Considered
1. Implementing heavy PostgreSQL GIN indexes and trigram text search.
2. Utilizing Elasticsearch.
3. Standard Django ORM `icontains` and `iexact` filtering.

### Choice
We chose standard Django ORM filters:
*   `q`: `icontains` on title OR description
*   `location`: `icontains`
*   `language`: `iexact`
*   `starts_after` / `starts_before`: `gte` / `lte`
*   **Default:** Upcoming events only if no explicit date filters are provided.

### Trade-offs
*   **Pros:** Perfectly balances the 24-hour assignment scope. It fulfills all functional requirements natively without introducing massive infrastructure dependencies like Elasticsearch or configuring complex PostgreSQL text-search vectors.
*   **Cons:** `icontains` performs a sequential scan on large datasets. While completely acceptable for MVP/assignment scale, it would require migration to full-text search at enterprise scale.

### Verification
Tests verify complex query combinations, ensuring that default queries exclude past events while explicit date filters successfully retrieve them.

---

## Decision 10: Event Deletion / Capacity Updates

### Problem / Ambiguity
When a Facilitator attempts to delete an event or reduce its capacity, the system must decide how to handle existing enrolled Seekers.

### Options Considered
1. Cascade delete all enrollments.
2. Force capacity reduction and strand active enrollments in a negative-available state.
3. Block destructive actions if active enrollments exist.

### Choice
We implemented strict blocking logic:
*   An event cannot be deleted if it has *any* active enrollments (canceled enrollments are ignored).
*   Capacity cannot be reduced below the current number of active enrollments.
*   Event times can be changed.

### Trade-offs
*   **Pros:** Prioritizes Seeker experience and data integrity. Seekers won't mysteriously lose their upcoming events.
*   **Cons:** Forces Facilitators to manually manage/cancel events or contact administrators if they genuinely need to delete an active, fully booked event.

### Verification
Tests explicitly assert that `DELETE` and `PATCH (capacity)` return `409 Conflict` and `400 Bad Request` respectively when violating these active-enrollment bounds.

---

## Decision 11: Error Response Contract

### Problem / Ambiguity
APIs must provide a consistent, predictable error format for frontend consumption. Django REST Framework defaults to returning arrays of strings or deeply nested dictionaries on validation errors, which can be difficult to parse dynamically.

### Options Considered
1. Exposing raw DRF validation dictionaries.
2. Implementing custom middleware to catch all exceptions.
3. Defining a custom base exception hierarchy explicitly returning `{"detail": "...", "code": "..."}`.

### Choice
We created a `BaseCustomException` extending `APIException`, hardcoding the `{"detail": "...", "code": "..."}` response shape.

### Trade-offs
*   **Pros:** Extremely predictable. Frontend clients can switch strictly on the string `code` (e.g., `event_full`, `invalid_otp`) to trigger localized UI states.
*   **Cons:** Requires manual implementation of custom exception classes for every business-logic failure instead of relying on generic HTTP responses.

### Verification
A manual audit of the `events/exceptions.py` and `accounts/exceptions.py` files confirmed the global usage of this contract. Unit tests explicitly assert `res.data["code"] == '...'` ensuring the contract never drifts.
