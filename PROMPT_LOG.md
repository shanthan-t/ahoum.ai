# AI-Assisted Development Prompt Log

This document records the material AI-assisted development phases during the implementation of the Ahoum.ai Events Platform backend. It details the engineering supervision applied to the AI's suggestions, including what was accepted, modified, or rejected.

## Phase 1: Project Foundation / Django Architecture

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Establish the baseline Django architecture, DRF setup, and PostgreSQL connection following the assignment's technical constraints.

### Key AI Output / Approach
The AI suggested standard Django project initialization, setting up a virtual environment, installing dependencies, configuring PostgreSQL in `settings.py`, and implementing JWT authentication defaults.

### What I Accepted
The overall project structure, `requirements.txt` dependencies, and the `ahoum` core routing setup.

### What I Changed
Ensured that environment variables loaded correctly via `python-dotenv` and restricted `DEBUG` mode to be environment-driven instead of hardcoded.

### What I Rejected
The AI initially proposed setting up Docker and Redis for caching. This was rejected to prevent over-engineering a 24-hour assignment that only required a foundational setup.

### Verification
Ran `manage.py check`, applied initial migrations, and verified server startup.

---

## Phase 2: Domain Model Design

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Design the core domain models (`UserProfile`, `EmailOTP`, `Event`, `Enrollment`) while adhering strictly to the constraint of using Django's default `auth.User`.

### Key AI Output / Approach
Proposed a `UserProfile` linked to the default `User` via `OneToOneField`, hashed `EmailOTP` storage, and standard relational links for `Event` and `Enrollment`. It suggested creating a new row for every enrollment cycle.

### What I Accepted
The `UserProfile` connection, the hashed OTP strategy, and the event capacity structures.

### What I Changed
Refined constraints and indexes (e.g., ensuring `event_ends_after_starts` check constraints) to push invariants to the database layer. 

### What I Rejected
**Enrollment Model (Example 5):** The AI proposed creating a new database row for every enrollment cycle (enroll -> cancel -> enroll). I explicitly rejected this (Option B) in favor of Option A: maintaining a single row per seeker/event and toggling the status. This enabled a hard `UNIQUE(event, seeker)` database constraint, drastically simplifying active-state queries.

### Verification
Applied migrations to PostgreSQL, inspected the schema to ensure constraints and indexes were successfully created.

---

## Phase 3: Authentication + OTP Implementation

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Implement secure user signup, email OTP verification, and JWT issuance without exposing the internal username.

### Key AI Output / Approach
The AI generated the `SignupView`, `VerifyEmailView`, and `LoginView`, including serializers and the service layer for processing OTPs.

### What I Accepted
The core logic for checking passwords, generating the 6-digit code, and returning JWT tokens.

### What I Changed
I required the implementation of a `pg_advisory_xact_lock` based on the normalized email during signup to prevent race conditions that could bypass Django's lack of uniqueness on the email field.

### What I Rejected
**DRF Error Shape (Example 2):** The AI initially leaned towards standard DRF `ValidationError` responses. I rejected this approach because the response did not reliably match the required `{"detail": "...", "code": "..."}` contract. I directed the implementation toward custom `APIException`-based business exceptions instead.

### Verification
Comprehensive test suite (`accounts/tests.py`) and simulated concurrent verification attempts.

---

## Phase 4: Event API Design

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Design the API contracts for Event CRUD operations and discovery for Facilitators and Seekers.

### Key AI Output / Approach
Proposed standard RESTful routes, permission classes (`IsFacilitator`, `IsSeeker`, `IsEventOwner`), and filtering arguments.

### What I Accepted
The route definitions and the overall role-based authorization model.

### What I Changed
I directed the implementation to explicitly decouple the `capacity` field logic from basic event details and ensure `created_by` was read-only.

### What I Rejected
**Search Indexing (Example 4):** The AI considered heavy PostgreSQL trigram/GIN indexing and external tools like Elasticsearch for the discovery endpoint. This was rejected as unnecessary over-engineering for this scale. Standard Django ORM filtering (`icontains`, `iexact`) was selected instead.

### Verification
Manual review of the generated design document (`event_api_design.md`).

---

## Phase 5: Event API Implementation

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Translate the approved Event API design into serializers, views, and services.

### Key AI Output / Approach
Generated the ViewSets/APIViews and serializer validation logic for date ranges and capacity requirements.

### What I Accepted
The validation logic for `ends_at > starts_at` and the permission checks.

### What I Changed
I directed the refactoring of views to use generic API views (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`) for cleaner code organization, overriding `get_queryset` for search parameters.

### What I Rejected
I rejected the AI's attempt to silently drop invalid filter dates, forcing an explicit error if parameters are malformed.

### Verification
Executed the 21 automated tests specifically targeting Event CRUD, discovery filtering, and pagination.

---

## Phase 6: Enrollment/Concurrency Design

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Design a robust, concurrency-safe enrollment strategy that mathematically prevents capacity breaches.

### Key AI Output / Approach
The AI drafted the endpoints (`POST /enroll`, `POST /cancel`) and outlined the transactional boundaries.

### What I Accepted
The endpoint definitions and the response payloads.

### What I Changed
I required explicit lifecycle rules defining how re-enrollment should clear the `canceled_at` timestamp rather than just flipping the status flag.

### What I Rejected
**Enrollment Concurrency (Example 3):** The AI initially documented a naive `count -> compare -> create` approach. I rejected this because concurrent requests could all observe the same available seat. The selected solution demanded:
`transaction.atomic()` -> `select_for_update(Event)` -> count active -> capacity check -> create/reactivate.

### Verification
Analyzed the locking sequence to confirm all operations use the Event row as the unified synchronization mutex, preventing deadlocks.

---

## Phase 7: Enrollment Implementation

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Implement the enrollment services, views, and strict PostgreSQL multi-threading concurrency tests.

### Key AI Output / Approach
Generated the `enroll_in_event` service wrapping the `select_for_update()` logic, and the `TransactionTestCase` utilizing `ThreadPoolExecutor`.

### What I Accepted
The overall service logic and the thread-based testing methodology.

### What I Changed
I required adding `django.utils.timezone` imports that the AI missed and structured the ThreadPool to explicitly manage database connections per worker thread.

### What I Rejected
I rejected implementing concurrency tests merely as sequential calls or using `sleep` statements. Real OS threads were mandated to hit PostgreSQL concurrently.

### Verification
Ran `manage.py test events`. The threads properly blocked on the row lock, yielding exactly 1 success and 4 conflicts when testing the last available seat.

---

## Phase 8: Final Technical Audit

### Tool / Model
Claude / Gemini (Antigravity Assistant)

### Objective
Conduct a final review of the codebase for missed requirements, security flaws, concurrency gaps, and performance issues.

### Key AI Output / Approach
The AI methodically reviewed the files and summarized the findings against the rubric.

### What I Accepted
The audit structure and confirmation of implemented requirements.

### What I Changed
Nothing in the audit summary itself, but it led to a code correction (documented below).

### What I Rejected
N/A

### Verification
Ran the full 40-test suite a final time.

---

# What AI Got Wrong / What I Corrected

### Example 1: OTP Error Transaction Rollback (Example 1)
**What AI Initially Proposed:** The AI placed the OTP attempt increment logic and the `raise InvalidOTPException` inside the same `transaction.atomic()` block.
**Why It Was Wrong:** In Django, if an exception propagates out of an `atomic()` block, the entire database transaction is rolled back. Consequently, the incremented attempt counter was lost, which could undermine the configured attempt limit.
**Correction:** I corrected the engineering approach by ensuring the attempt counter mutation was saved, the transaction was ended gracefully, and the custom API exception was raised *after* the transaction committed.
**Verification:** Verified via `accounts/tests.py` where a loop of 5 failed OTP requests successfully triggered the `OTPMaxAttemptsException`.

### Example 2: N+1 Query in Event Discovery
**What AI Initially Proposed:** The AI implemented `EventListCreateView` utilizing a nested `CreatorSerializer` but queried events simply with `Event.objects.all()`.
**Why It Was Wrong:** Because `CreatorSerializer` accesses `created_by` to extract the ID (even though it's technically a foreign key), DRF could trigger a separate database lookup for the user per event in the list, resulting in an N+1 query inefficiency.
**Correction:** During the final audit, this was identified and I required the explicit addition of `.select_related("created_by")` to the `get_queryset` pipeline to fetch the data in a single optimized JOIN.
**Verification:** Verified manually by inspecting the query execution path during the audit; automated tests continued to pass without degradation.

---

# Supervision Principles

Throughout this assignment, AI was utilized primarily for:
- Rapid prototyping and brainstorming.
- Evaluating design alternatives (e.g., locking strategies, models).
- Generating boilerplate implementations and robust test scaffolding.
- Conducting comprehensive code audits.

However, strict human engineering judgment was continuously applied to:
- Actively reject unsafe concurrency architectures (e.g., naive counting).
- Enforce rigid assignment constraints (e.g., maintaining the default Django User model).
- Scrutinize raw database behavior and locking mechanisms.
- Inspect, refactor, and correct generated code (e.g., transaction boundary scoping).
- Ensure error formatting adhered to the strict API contract.
- Make the final, definitive architectural decisions.

This project represents responsible, AI-assisted engineering where the developer retains responsibility for the final architecture, implementation, security, and verification.
