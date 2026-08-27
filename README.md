# Ahoum Events Platform

A robust Django REST backend supporting authentication, email OTP verification, JWT session management, role-based access, event discovery, and concurrent enrollment processing with strict database serialization.

## Quick Start

Assuming Python 3.10+ and PostgreSQL are installed:

```bash
# Clone the repository & enter it
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Migrate and run tests
python manage.py migrate
python manage.py check
python manage.py test

# Start the server
python manage.py runserver
```

> **Note:** The current suite verifies **52 tests passing**, covering authentication, search, and concurrency edge-cases.

## Two Ways to Evaluate

### Option 1 — Clone and Run
Clone the repository, configure PostgreSQL in `.env`, install requirements, run migrations, and execute `python manage.py test` to review the automated verification of the platform's constraints.

### Option 2 — Import the Postman Collection
Import `Ahoum_API.postman_collection.json` into Postman to utilize the preconfigured requests.
**Basic Flow:**
1. Run **Signup**.
2. Retrieve the 6-digit OTP from the Django terminal output.
3. Run **Verify Email**.
4. Run **Login**. (The script automatically stores your `access_token`).
5. Use the token to create, discover, and enroll in events.

## Key Features

| Feature | What it does |
| :--- | :--- |
| **Authentication** | Default Django `auth.User` expanded with `UserProfile` roles. |
| **OTP Verification** | Replaces passwords for email validation with strict TTL/attempt limits. |
| **JWT** | Access and refresh tokens manage stateless sessions securely. |
| **Roles** | Strict 'Seeker' and 'Facilitator' boundaries enforced across APIs. |
| **Events** | Facilitators can CRUD their own events and manage capacities. |
| **Search** | Seekers can filter events by text, location, language, and date. |
| **Enrollment** | Seekers can enroll/cancel with automated re-enrollment lifecycle logic. |
| **Concurrency Protection** | Row-level locking guarantees capacities are never breached. |

## Enrollment Capacity

The API locks the Event row inside a database transaction before checking active enrollments.

```text
lock Event
    ↓
count active enrollments
    ↓
check capacity
    ↓
create/reactivate enrollment
    ↓
commit
```

This prevents concurrent enrollment requests from observing the same remaining seat.
*Tested with PostgreSQL using 5 concurrent seekers, 9 existing enrollments, and capacity 10: 1 request succeeds and 4 receive event_full.*

## Authentication

```text
Signup
  ↓
Email OTP
  ↓
Verify email
  ↓
Login with password
  ↓
Access + Refresh JWT
```
* OTP strictly expires after 5 minutes.
* Accounts are locked from verification after 5 failed attempts.
* Requests require a 60-second cooldown.
* A new OTP invalidates the previous active OTP.

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
| GET | `/api/events/mine/` | Facilitator | List created events with metrics |
| GET | `/api/events/{id}/` | Both | Retrieve event details |
| PATCH | `/api/events/{id}/` | Facilitator | Update event |
| DELETE | `/api/events/{id}/` | Facilitator | Delete event |

**Enrollment**
| Method | Path | Role | Purpose |
| :--- | :--- | :--- | :--- |
| POST | `/api/events/{id}/enroll/` | Seeker | Enroll in event |
| POST | `/api/events/{id}/cancel/` | Seeker | Cancel enrollment |
| GET | `/api/enrollments/` | Seeker | List upcoming/past enrollments |

## Search

| Parameter | Behavior |
| :--- | :--- |
| `q` | Partial match across title or description |
| `location` | Partial match |
| `language` | Exact match |
| `starts_after` | ISO timestamp filtering (>=) |
| `starts_before` | ISO timestamp filtering (<=) |

## Database Integrity

* Event must end after it starts.
* Capacity is positive or NULL.
* Enrollment status is constrained.
* One Enrollment row per event/seeker.
* Important event/enrollment indexes are present.

## Testing

```bash
python manage.py check
python manage.py test
```
The suite currently contains **52 tests** validating:
* authentication / OTP
* event APIs
* permissions
* enrollment lifecycle
* re-enrollment
* concurrency

*(Note: Real concurrency assertions require PostgreSQL.)*

## Limitations / Next Day

* Email currently logs to the terminal instead of via an external provider (e.g. SendGrid).
* Concurrency protection requires PostgreSQL; migrating to SQLite will break transaction locks.
* Search relies on basic ORM filters rather than PostgreSQL full-text/trigram indexing.

## Documentation

* `README.md` → setup and evaluation guide
* `DECISIONS.md` → important architecture decisions and trade-offs
* `DEBUGGING.md` → real issues encountered and how they were fixed
* `PROMPT_LOG.md` → material AI prompts, rejected approaches, and verification
