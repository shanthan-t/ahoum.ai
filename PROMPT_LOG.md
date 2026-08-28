# AI-Assisted Development Journal

AI was used throughout this project as an implementation and reasoning assistant. However, generated output was strictly treated as a proposal. Code was reviewed, frequently modified, and rigorously tested before being merged into the codebase. 

This log details where AI was useful, where I applied engineering judgment, and what I explicitly rejected.

## Project Foundation

**Goal:** Establish the baseline Django architecture, DRF setup, and PostgreSQL connection following assignment constraints.

* **AI suggested:** Standard Django initialization with Redis caching and Docker.
* **Accepted:** Core structure, `requirements.txt`, and base routing.
* **Changed:** I required `python-dotenv` for secrets and tied `DEBUG` to environment configurations.
* **Rejected:** I rejected Docker and Redis entirely to prevent unnecessary over-engineering and keep the evaluation footprint small.
* **Verified:** I applied the initial migrations and successfully booted the server.

## Domain Model

**Goal:** Design the core domain models (`UserProfile`, `EmailOTP`, `Event`, `Enrollment`) restricted by the default `auth.User`.

* **AI suggested:** Inheriting from `AbstractUser` or using a massive custom JSON field on a related profile.
* **Accepted:** The four core models, fields, and constraints.
* **Changed:** I required explicit indexing on `event.starts_at` for faster event discovery queries.
* **Rejected:** Overriding `AbstractUser`, as it directly violates the assignment requirement to use the default `auth.User`.
* **Verified:** Generated and applied migrations cleanly.

## Authentication and OTP

**Goal:** Implement the passwordless OTP signup and verification flow using Django REST Framework.

* **AI suggested:** Standard OTP creation and validation loops.
* **Accepted:** The core password-hashing approach and JWT return.
* **Changed:** I directed the implementation to use a `pg_advisory_xact_lock` on the normalized email during signup. This was necessary to prevent race conditions from bypassing Django's lack of email uniqueness.
* **Rejected:** Standard DRF `ValidationError` shapes. I required custom `APIException` classes to ensure exact `{"detail": "...", "code": "..."}` matching for the frontend.
* **Verified:** The test suite successfully simulated concurrent verification attempts and attempt limits.

## Event APIs

**Goal:** Establish permissions, serialization, and discovery API shapes.

* **AI suggested:** Nested serializers and full-text search configurations (Elasticsearch).
* **Accepted:** The route definitions and authorization boundaries.
* **Changed:** I decoupled the capacity logic from basic event details, making `created_by` read-only, and refactored the ViewSets toward generic `ListCreateAPIView` with overridden `get_queryset` methods for clarity.
* **Rejected:** Elasticsearch and PostgreSQL GIN indexing. I enforced simple ORM `icontains` to prevent over-engineering at this scale. I also rejected the AI silently dropping invalid filter dates, forcing explicit errors instead.
* **Verified:** Filter edge-case tests were written and passed.

## Enrollment and Concurrency

This was the most critical phase, where AI suggestions required heavy supervision.

**Goal:** Design the safe enrollment lifecycle and transactional boundaries.

* **AI suggested:** A naive `count -> compare -> create` transactional flow, and later suggested optimistic concurrency versions with sequential, sleep-based testing.
* **Accepted:** The endpoint definitions, response payloads, and service abstractions.
* **Changed:** I required explicit lifecycle rules clarifying how re-enrollment clears the `canceled_at` timestamp. I also structured the `ThreadPool` to explicitly manage database connections per thread.
* **Rejected:** Naive concurrency handling. I demanded pessimistic `select_for_update()` row-level locks on the parent `Event` row. I also rejected sequential testing; real OS threads hitting PostgreSQL simultaneously were mandated.
* **Verified:** The concurrency tests passed under heavy parallel load, proving the `Event` lock effectively serialized enrollment.

## Evaluator UX Polish

**Goal:** Provide the evaluator with a frictionless way to review the project without building gimmicky dashboards or modifying application behavior.

* **AI suggested:** Fake web dashboards or simple bash scripts.
* **Accepted:** A detailed Postman collection with automatic token extraction.
* **Changed:** I required the verification script to stream real individual test names as they pass, rather than hiding the actual test execution behind a fake progress bar. I also required building `verify.py` instead of just `verify.sh` for true cross-platform Windows compatibility.
* **Rejected:** Any changes to application code or the creation of an over-engineered frontend.
* **Verified:** Executed `./verify.sh` and `python verify.py` on Linux/macOS and Windows, confirming identical output and zero dependencies.

---

# What AI Got Wrong / What I Corrected

The assignment requires explicit evidence of AI supervision. The following specific errors were caught and corrected via my engineering judgment:

### Example 1 — OTP Error Transaction Rollback

**What the generated approach did:** 
The AI mutated the attempt count and raised an `InvalidOTPException` inside the identical `transaction.atomic()` block.

**Why it was problematic:** 
In Django, exceptions escaping an `atomic()` block roll back the *entire* transaction. The incremented attempt counter was lost, completely undermining the configured 5-attempt limit.

**What was changed:** 
I ensured the attempt counter mutation was saved, the transaction was gracefully ended, and the API exception was raised *after* the transaction committed.

**How it was verified:** 
The `accounts/tests.py` loop correctly triggered the `OTPMaxAttemptsException`.

### Example 2 — N+1 Query in Event Discovery

**What the generated approach did:** 
The AI provided an `EventListSerializer` with a nested `CreatorSerializer` to return event creator details.

**Why it was problematic:** 
Extracting foreign key properties iteratively across a paginated list triggers a separate DB lookup per event (an N+1 query inefficiency).

**What was changed:** 
I required the explicit addition of `.select_related("created_by")` to the `get_queryset` pipeline, fetching all data in a single optimized JOIN.

**How it was verified:** 
Query paths were inspected manually via `connection.queries`; tests passed without degradation, reducing 21 queries down to 2.
