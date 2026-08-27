# AI-Assisted Development Prompt Log

This document records the AI-assisted development phases during the implementation of the Ahoum Events Platform backend, highlighting explicit engineering supervision.

## Prompt 1 — Project Foundation & Architecture

**Goal:** Establish the baseline Django architecture, DRF setup, and PostgreSQL connection following assignment constraints.

* **AI proposed:** Standard Django initialization with Redis caching and Docker.
* **Accepted:** Core structure, `requirements.txt`, and base routing.
* **Changed:** Required `python-dotenv` for secrets and tied `DEBUG` to environment configurations.
* **Rejected:** Docker and Redis (preventing unnecessary over-engineering).
* **Verified:** Applied initial migrations and successfully booted the server.

## Prompt 2 — Domain Model Design

**Goal:** Design the core domain models (`UserProfile`, `EmailOTP`, `Event`, `Enrollment`) restricted by the default `auth.User`.

* **AI proposed:** Inherit from `AbstractUser` or use a massive custom JSON field.
* **Accepted:** The four core models, fields, and constraints.
* **Changed:** Required explicit indexing on `event.starts_at`.
* **Rejected:** `AbstractUser` override (violates the assignment requirement).
* **Verified:** Generated and applied migrations cleanly.

## Prompt 3 — Auth & OTP Implementation

**Goal:** Implement the passwordless OTP signup and verification flow using Django REST Framework.

* **AI proposed:** Standard OTP creation and validation loops.
* **Accepted:** The core password-hashing approach and JWT return.
* **Changed:** Directed the implementation to use a `pg_advisory_xact_lock` on the normalized email during signup to prevent race conditions bypassing Django's email non-uniqueness.
* **Rejected:** Standard DRF `ValidationError` shapes. Required custom `APIException` shapes for exact `{"detail": "...", "code": "..."}` matching.
* **Verified:** Test suite simulated concurrent verification attempts.

## Prompt 4 — Event API Design

**Goal:** Establish permissions, serialization, and discovery API shapes.

* **AI proposed:** Nested serializers and full-text search configurations.
* **Accepted:** The route definitions and authorization model.
* **Changed:** Required decoupling capacity logic from basic event details and making `created_by` read-only.
* **Rejected:** Elasticsearch / PostgreSQL GIN indexing. Enforced simple ORM `icontains` for this scale.
* **Verified:** Confirmed API shapes manually via DRF console.

## Prompt 5 — Event API Implementation

**Goal:** Implement the Event views, filters, and business validations.

* **AI proposed:** ViewSets with extensive custom action overrides.
* **Accepted:** Validation logic for `ends_at > starts_at` and permission boundaries.
* **Changed:** Directed the refactoring toward generic API views (`ListCreateAPIView`) overriding `get_queryset` for clarity.
* **Rejected:** AI silently dropping invalid filter dates; forced explicit errors instead.
* **Verified:** Filter edge-case tests written and passed.

## Prompt 6 — Enrollment Concurrency Design

**Goal:** Design the safe enrollment lifecycle and transactional boundaries.

* **AI proposed:** Naive `count -> compare -> create` transactional flow.
* **Accepted:** The endpoint definitions and response payloads.
* **Changed:** Required explicit lifecycle rules clarifying how re-enrollment clears the `canceled_at` timestamp.
* **Rejected:** Naive concurrency handling. Demanded `select_for_update()` row-level locks on the parent `Event` row.
* **Verified:** Approved architecture plan before proceeding to code.

## Prompt 7 — Enrollment Implementation

**Goal:** Write the transactional enrollment services and tests.

* **AI proposed:** Optimistic concurrency versions and sequential tests.
* **Accepted:** The service abstraction and exception classes.
* **Changed:** Required adding missing timezone imports and structured the `ThreadPool` to manage DB connections per thread explicitly.
* **Rejected:** Sequential/sleep-based testing. Real OS threads hitting PostgreSQL were mandated.
* **Verified:** Concurrency tests passed under heavy parallel load.

## Prompt 8 — Evaluator UX Polish

**Goal:** Provide the evaluator with a frictionless way to review the project without building gimmicky dashboards or modifying application behavior.

* **AI proposed:** Fake web dashboards or simple bash scripts.
* **Accepted:** A detailed Postman collection with automatic token extraction and a one-command verification script.
* **Changed:** Required the verification script to stream real individual test names as they pass, rather than hiding the actual test execution behind a fake progress bar. Required building `verify.py` instead of just `verify.sh` for true cross-platform Windows compatibility.
* **Rejected:** Any changes to application code or the creation of an over-engineered frontend.
* **Verified:** Executed `./verify.sh` and `python verify.py` on Linux/macOS and Windows, confirming identical output and zero dependencies.

---

# What AI Got Wrong / What I Corrected

The following specific errors were caught and corrected via human supervision:

### Error 1: OTP Error Transaction Rollback
* **Goal:** Increment failed OTP attempts.
* **AI proposed:** Mutate attempt count and raise `InvalidOTPException` inside the same `transaction.atomic()` block.
* **Why It Was Wrong:** In Django, exceptions escaping an `atomic()` block rollback the *entire* transaction. The incremented attempt counter was lost, undermining the configured attempt limit.
* **Correction:** I ensured the attempt counter mutation was saved, the transaction was gracefully ended, and the API exception was raised *after* the transaction committed.
* **Verified:** `accounts/tests.py` loop correctly triggered the `OTPMaxAttemptsException`.

### Error 2: N+1 Query in Event Discovery
* **Goal:** Return events with creator details.
* **AI proposed:** A nested `CreatorSerializer` within the Event listing.
* **Why It Was Wrong:** Extracting foreign key properties iteratively across a list triggers a separate DB lookup per event (N+1 query inefficiency).
* **Correction:** I required the explicit addition of `.select_related("created_by")` to the `get_queryset` pipeline, fetching all data in a single optimized JOIN.
* **Verified:** Query paths inspected manually; tests passed without degradation.
