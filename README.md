# Ahoum Events Platform

A Django REST backend for an events platform featuring:
- authentication
- email verification
- JWT authentication
- Seeker / Facilitator roles
- event discovery
- event management
- enrollment
- cancellation / re-enrollment
- PostgreSQL-backed concurrency protection

## Quick Evaluation

### Option 1 — Clone and Run
Clone the repository and set up the environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
*(Ensure PostgreSQL is configured and credentials match your `.env`.)*

Run migrations:
```bash
python manage.py migrate
```

### Verify the installation

After configuring PostgreSQL and running migrations:
```bash
./verify.sh
```
This runs Django system checks, migration consistency verification, and the complete automated test suite. Expected output:
```text
========================================
 Ahoum Events Platform — Verification
========================================

[1/3] Django system check ... PASS
[2/3] Database migrations ... PASS
[3/3] Automated tests ... 52 tests passed

========================================
 VERIFICATION PASSED
========================================
```

`verify.sh` is provided for Linux/macOS environments. Windows users can run the equivalent Django commands individually:
```powershell
python manage.py check
python manage.py migrate --check
python manage.py test
```

Start the development server:
```bash
python manage.py runserver
```

### Option 2 — Import Postman Collection
The repository contains `Ahoum_API.postman_collection.json`. You can import this collection into Postman and use the preconfigured requests to evaluate the API without manually constructing request bodies.

---

## Using Postman
Follow this exact sequence to quickly evaluate the platform.

### Step 1 — Import
1. Open Postman.
2. Select **Import**.
3. Select `Ahoum_API.postman_collection.json` from the repository root.
4. The collection will appear in your sidebar, organized into three folders:
   - 1. Authentication
   - 2. Events
   - 3. Enrollment

### Step 2 — Start Django
Ensure your local server is running:
```bash
python manage.py runserver
```
The collection uses a collection variable `{{base_url}}` which defaults to `http://127.0.0.1:8000`.

### Step 3 — Signup
Open **1. Authentication → Signup** and click Send.
The request body contains:
```json
{
    "email": "seeker@example.com",
    "password": "SecurePass123!",
    "role": "seeker"
}
```
*Note: `username` is intentionally NOT included in this platform. The `role` can be either `seeker` or `facilitator`.*

### Step 4 — Retrieve OTP
After sending Signup, Django's console email backend prints the OTP directly to the terminal where `runserver` is running.
**The OTP is NOT automatically available inside Postman.** You must manually copy the 6-digit OTP from your terminal window.

### Step 5 — Verify Email
Open **1. Authentication → Verify Email**.
Go to the **Body** tab (raw JSON) and enter:
```json
{
    "email": "seeker@example.com",
    "otp": "REPLACE_ME"
}
```
**Replace `"REPLACE_ME"`** with the 6-digit OTP you copied from the Django terminal.

### Step 6 — Login
Open **1. Authentication → Login**.
Use the exact same email and password from Signup:
```json
{
    "email": "seeker@example.com",
    "password": "SecurePass123!"
}
```
A successful response returns your access and refresh tokens.
**The collection automatically saves the returned access token into the `access_token` collection variable.** This means you do NOT need to manually copy the JWT into every subsequent request.

### Step 7 — Authenticated Requests
All authenticated requests in the collection are preconfigured to use:
`Authorization: Bearer {{access_token}}`
After Login, you can move directly to the Events and Enrollment folders!

### Step 8 — Create an Event
*(Note: Creating an event requires a Facilitator account. If you just signed up as a Seeker, repeat Steps 3-6 using a new email and `"role": "facilitator"`).*
Open **2. Events → Create Event**.
```json
{
    "title": "Advanced Python Workshop",
    "description": "Deep dive into Django and concurrency.",
    "language": "English",
    "location": "Remote",
    "starts_at": "2026-10-01T10:00:00Z",
    "ends_at": "2026-10-01T14:00:00Z",
    "capacity": 10
}
```
When successful, a Postman script automatically saves the generated event ID into the `{{event_id}}` variable for future requests.

### Step 9 — Event Discovery
Open **2. Events → List/Search Events**.
`GET /api/events/` supports combining multiple query parameters:
`?q=python`
`?location=Remote`
`?language=English`
`?starts_after=2026-09-01T00:00:00Z`
Results are paginated and ordered upcoming-first.

### Step 10 — Enrollment
*(Note: Enrollment requires a Seeker account).*
Open **3. Enrollment → Enroll in Event**.
`POST /api/events/{{event_id}}/enroll/`
Returns a 201 Created if capacity allows.

### Step 11 — Cancellation
Open **3. Enrollment → Cancel Enrollment**.
`POST /api/events/{{event_id}}/cancel/`
Cancellation changes the existing enrollment state to `canceled` rather than deleting the historical database row.

### Step 12 — Re-enrollment
If you **Enroll → Cancel → Enroll** again, the API reacts properly to the edge case by reactivating the existing historical row:
* Status becomes `enrolled`.
* `canceled_at` becomes null.
* `enrolled_at` timestamp is refreshed.

### Step 13 — Enrollment Listing
Open **3. Enrollment → List My Enrollments**.
`GET /api/enrollments/`
Supports filtering by time:
* `?period=upcoming`
* `?period=past`

---

## Quick Postman Flow Summary

```text
START DJANGO
    ↓
IMPORT POSTMAN
    ↓
SIGNUP
    ↓
COPY OTP FROM DJANGO TERMINAL
    ↓
PUT OTP IN VERIFY EMAIL → Body → raw JSON
    ↓
LOGIN
    ↓
ACCESS TOKEN AUTOMATICALLY STORED
    ↓
CREATE / DISCOVER EVENTS
    ↓
USE SEEKER ACCOUNT
    ↓
ENROLL
    ↓
CANCEL
    ↓
RE-ENROLL
```

---

## Key Features

| Feature | What it does |
| :--- | :--- |
| **Authentication** | Default Django `auth.User` expanded with `UserProfile` roles. |
| **OTP Verification** | Verifies email ownership before password-based JWT login. |
| **JWT** | Access and refresh tokens manage stateless sessions securely. |
| **Roles** | Strict 'Seeker' and 'Facilitator' boundaries enforced across APIs. |
| **Events** | Facilitators can CRUD their own events and manage capacities. |
| **Search** | Seekers can filter events by text, location, language, and date. |
| **Enrollment** | Seekers can enroll/cancel with automated re-enrollment lifecycle logic. |
| **Concurrency** | PostgreSQL row-level locking serializes capacity-sensitive enrollment operations and prevents the tested capacity race condition. |

---

## Architecture

```text
Client
  ↓
Django REST Framework Views
  ↓
Serializers / Permissions
  ↓
Service Layer
  ↓
PostgreSQL
```
* **Views** handle HTTP concerns.
* **Serializers** validate request/response data.
* **Permissions** enforce role/ownership boundaries.
* **Services** contain transactional business logic.
* **PostgreSQL** enforces database constraints and concurrency.

---

## Authentication Flow

1. Signup creates an unverified user.
2. A 6-digit OTP is generated and stored hashed.
3. OTP expires after the configured TTL.
4. OTP is invalidated after 5 failed verification attempts.
5. Resend has a cooldown.
6. A new OTP invalidates the previous active OTP.
7. Email verification activates the account.
8. Login requires email + password.
9. Login returns access + refresh JWTs.

---

## Enrollment / Concurrency

Simply counting active enrollments is unsafe:
```text
Unsafe:
Request A → count = 9 → seat available
Request B → count = 9 → seat available
Request A → enroll
Request B → enroll (Breach!)
```

This implementation serializes the check:
```text
Current:
Request A → lock Event → count → enroll → commit
Request B → waits for Event lock → count again → reject if full
```
The automated concurrency test verifies this exact behavior.

---

## API Overview

**Authentication**
| Method | Path | Role | Purpose |
| :--- | :--- | :--- | :--- |
| POST | `/api/accounts/signup/` | Any | Create unverified account |
| POST | `/api/accounts/verify-email/` | Any | Verify OTP |
| POST | `/api/accounts/resend-otp/` | Any | Request new OTP |
| POST | `/api/accounts/login/` | Any | Exchange email/password for JWT |
| POST | `/api/accounts/token/refresh/` | Any | Refresh JWT |

**Events**
| Method | Path | Role | Purpose |
| :--- | :--- | :--- | :--- |
| GET | `/api/events/` | Both | Search upcoming/filtered events |
| POST | `/api/events/` | Facilitator | Create event |
| GET | `/api/events/mine/` | Facilitator | List created events |
| GET | `/api/events/{id}/` | Both | Retrieve event details |
| PATCH | `/api/events/{id}/` | Facilitator | Update event |
| DELETE | `/api/events/{id}/` | Facilitator | Delete event |

* Facilitators can create events.
* Facilitators can modify/delete only their own events.
* Reducing capacity below active enrollments is rejected.
* Events with active enrollments cannot be deleted.
* Seekers can discover events.
* Event discovery is ordered by `starts_at` and `id`.

**Enrollment**
| Method | Path | Role | Purpose |
| :--- | :--- | :--- | :--- |
| POST | `/api/events/{id}/enroll/` | Seeker | Enroll in event |
| POST | `/api/events/{id}/cancel/` | Seeker | Cancel enrollment |
| GET | `/api/enrollments/` | Seeker | List upcoming/past enrollments |

---

## Search

| Parameter | Behavior |
| :--- | :--- |
| `q` | Partial match across title or description |
| `location` | Partial match |
| `language` | Exact match |
| `starts_after` | ISO timestamp filtering (>=) |
| `starts_before` | ISO timestamp filtering (<=) |

Example:
`GET /api/events/?q=python&location=Remote`
Results are paginated and ordered strictly upcoming-first by default.

---

## Database Integrity

* `CHECK` constraints (e.g. event ends after starts).
* Capacity is positive or `NULL`.
* Enrollment status is constrained.
* `UNIQUE(event, seeker)`
* Indexes (e.g. `starts_at`)
* Timezone-aware UTC timestamps
* PostgreSQL transaction boundaries

---

## Testing

```bash
python manage.py check
python manage.py test
```
**52 tests passing.**

### Authentication / OTP
* signup, verification, expiry, attempt limits, resend behavior, JWT login.

### Events
* CRUD, permissions, ownership, filtering, pagination, validation.

### Enrollment
* enrollment, capacity, cancellation, re-enrollment.

### Concurrency
* 5 concurrent requests
* 9 existing enrollments
* capacity 10
* exactly 1 success
* 4 `409 event_full` responses
* final active enrollment count = 10

*(Note: Concurrency tests require PostgreSQL).*

---

## Limitations

* Console email backend is used for the assignment scope.
* Concurrency tests rely on PostgreSQL row locking.
* Search uses ORM filters rather than specialized text-search indexes.

---

## Documentation

* `README.md` → setup and evaluation guide
* `DECISIONS.md` → important architecture decisions and trade-offs
* `DEBUGGING.md` → real issues encountered and how they were fixed
* `PROMPT_LOG.md` → material AI prompts, rejected approaches, and verification
