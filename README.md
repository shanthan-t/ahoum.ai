# Ahoum Events Platform — Django REST Backend

A compact Django REST backend implementing authentication, email OTP verification, JWT authentication, role-based access, event discovery, event management, and enrollment with PostgreSQL concurrency protection. 

This platform leverages Django, Django REST Framework, PostgreSQL, and SimpleJWT.

## Quick Evaluation

After setup, run:
```bash
python manage.py check
python manage.py test
```
The current suite contains 52 tests.

The most important concurrency scenario is:
- capacity = 10
- active enrollments = 9
- 5 concurrent seekers
- → 1 succeeds
- → 4 receive 409
- → final active enrollments = 10

*Note: This concurrency test requires PostgreSQL.*

## Assignment Overview

This project implements the Ahoum.ai Events Platform Backend Developer Intern assignment. It provides a robust backend facilitating two core user roles:
- **Facilitators:** Can create, update, and manage capacity for their own events.
- **Seekers:** Can discover, filter, and enroll in upcoming events.

The system relies on email OTP verification followed by password-based JWT authentication and enforces the capacity invariant by serializing capacity-sensitive operations on the Event row.

## Key Engineering Highlights

### PostgreSQL Enrollment Concurrency
To enforce that active enrollments never exceed an event's capacity, the system employs strict database-level serialization:

`transaction.atomic()` -> `select_for_update(Event)` -> `active enrollment count` -> `capacity check` -> `create/reactivate enrollment` -> `commit`

This approach enforces the capacity invariant by serializing capacity-sensitive operations on the Event row. The implementation is verified by a PostgreSQL concurrency test covering the assignment's required scenario.

### OTP Security
The OTP flow verifies the user's email before password-based JWT login is permitted:
- 6-digit hashed OTP (using Django password utilities)
- 5-minute TTL
- 5-attempt brute-force limit
- 60-second resend cooldown
- Latest OTP invalidates previous active OTPs
- Transactional verification and row locking

### Default Django User
As strictly required, the default Django `auth.User` model forms the authentication foundation. Platform-specific metadata (roles, email verification status) is abstracted into a decoupled `UserProfile` model via a `OneToOneField`.

### AI-Assisted Engineering
AI was utilized for brainstorming, implementation assistance, test generation, and auditing. Key architectural decisions and human engineering corrections are formally documented in:
- `PROMPT_LOG.md`
- `DECISIONS.md`
- `DEBUGGING.md`

## Technology Stack

| Technology | Version |
| :--- | :--- |
| Python | 3.10+ |
| Django | 4.2.30 |
| djangorestframework | 3.17.2 |
| djangorestframework-simplejwt | 5.5.1 |
| psycopg2-binary | 2.9.12 |
| python-dotenv | 1.2.3 |

## Project Structure

```text
ahoum-project-root/
├── accounts/          # Authentication, OTP services, User roles
├── events/            # Event CRUD, Search, Enrollment services
├── ahoum/             # Core settings and URL routing
├── manage.py
├── requirements.txt
├── .env.example
├── README.md
├── DECISIONS.md
├── DEBUGGING.md
└── PROMPT_LOG.md
```

## Setup

### Prerequisites
- Python 3.10+
- PostgreSQL
- Git

### Database Setup
Ensure PostgreSQL is installed and the service is running according to your operating system.
Create the database (the exact authentication method may depend on your OS/distribution):
```sql
CREATE DATABASE ahoum;
```
Ensure you have a PostgreSQL user configured, and place the corresponding credentials into your `.env` file.

### Linux & macOS

```bash
# Clone the repository
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```
*(On Debian/Ubuntu use `apt` for PostgreSQL installation. On Fedora/RHEL use `dnf`. On macOS, Homebrew is an optional but convenient method to install PostgreSQL.)*

### Windows

Open PowerShell:
```powershell
# Clone the repository
# Create and activate virtual environment
py -m venv venv
.\venv\Scripts\Activate.ps1

# (Alternative Command Prompt activation: venv\Scripts\activate.bat)

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Configure environment variables
Copy-Item .env.example .env
```
*(Use the official PostgreSQL installer or service wrapper for Windows to set up your database.)*

### Migrations and Server

Once your `.env` file is configured with your database credentials, run:
```bash
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver
```

## Environment Variables

The `.env` file drives configuration. Never expose real production secrets in version control.

| Variable | Purpose | Example / Default |
| :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | Django cryptographic signing | `django-insecure-...` |
| `DJANGO_DEBUG` | Enables detailed error pages | `True` |
| `DJANGO_ALLOWED_HOSTS` | Accepted host headers | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name | `ahoum` |
| `DB_USER` | PostgreSQL user | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | `postgres` |
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `5432` |

## API Endpoints

All endpoints route through `/api/`.

| Endpoint | Method | Purpose | Auth Required | Allowed Role |
| :--- | :--- | :--- | :--- | :--- |
| `/api/accounts/signup/` | POST | Create unverified account | No | Any |
| `/api/accounts/verify-email/` | POST | Verify OTP, grant verified status | No | Any |
| `/api/accounts/resend-otp/` | POST | Request new OTP email | No | Any |
| `/api/accounts/login/` | POST | Exchange verified email/password for JWT | No | Any (Verified) |
| `/api/accounts/token/refresh/` | POST | Refresh JWT access token | No | Any |
| `/api/events/` | GET | Discover upcoming/filtered events | Yes | Seeker / Facilitator |
| `/api/events/` | POST | Create a new event | Yes | Facilitator |
| `/api/events/mine/` | GET | List events created by the user | Yes | Facilitator |
| `/api/events/{id}/` | GET | Retrieve event details | Yes | Seeker / Facilitator |
| `/api/events/{id}/` | PATCH | Update event (times, capacity) | Yes | Facilitator (Owner) |
| `/api/events/{id}/` | DELETE | Delete event (if no enrollments) | Yes | Facilitator (Owner) |
| `/api/events/{id}/enroll/` | POST | Enroll in an event | Yes | Seeker |
| `/api/events/{id}/cancel/` | POST | Cancel an enrollment | Yes | Seeker |
| `/api/enrollments/` | GET | List the user's upcoming/past enrollments | Yes | Seeker |

## Search / Filtering

The `GET /api/events/` endpoint supports extensive discovery parameters:
- `q`: Case-insensitive partial match across `title` OR `description`.
- `location`: Case-insensitive partial match.
- `language`: Case-insensitive exact match.
- `starts_after`: Greater-than-or-equal ISO timestamp filtering.
- `starts_before`: Less-than-or-equal ISO timestamp filtering.

**Defaults:** If neither `starts_after` nor `starts_before` is provided, the API automatically filters for strictly *upcoming* events (starting after the current UTC time).
**Ordering:** Results default to `starts_at ASC, id ASC`.
**Pagination:** The API implements standard page number pagination yielding: `count`, `next`, `previous`, and `results`.

## Authentication Flow

```text
Signup -> Unverified Account -> OTP Email -> Verify OTP -> email_verified=True -> Login -> Access + Refresh JWT
```
*Note: The raw OTP is strictly hashed and never returned in API payloads. During local development, the Django console email backend displays the OTP in the terminal window.*

## Enrollment Lifecycle

```text
NO ENROLLMENT -> ENROLLED -> CANCELED -> ENROLLED
```
A database unique constraint guarantees only a single `Enrollment` row exists per event/seeker pairing. Re-enrollment gracefully reactivates the original row.

**Listing Enrollments (`GET /api/enrollments/`):**
List the user's upcoming/past enrollments, including canceled enrollment history.
- `period=upcoming` (default)
- `period=past`

**Capacity Enforcement:**
*   `capacity = NULL` represents an unlimited event.
*   Otherwise, the invariant `active enrolled count <= capacity` is strictly enforced.

## Concurrency Design

A naive capacity check involves counting active enrollments, comparing them to the capacity, and creating the enrollment row. This is inherently unsafe under high concurrency; parallel requests can observe the identical "available" seat and breach the limit.

**The Solution:**
`transaction.atomic()` + `select_for_update(Event)`

All capacity-sensitive operations (enrollment, cancellation, capacity modification) use the Event row as the serialization point, preventing the enrollment race condition addressed by the assignment. This is verified by a real PostgreSQL concurrency test covering the assignment's required scenario.

## Testing

The project maintains a comprehensive automated test suite.

```bash
python manage.py check
python manage.py test
```
The suite thoroughly validates:
- Authentication & Roles
- OTP cooldowns and brute-force defenses
- Authorization boundaries (Seekers cannot manage events)
- Event discovery and complex filtering
- Enrollment boundaries and validations
- Re-enrollment lifecycle transitions
- Concurrency behavior

*Explicit Note: Concurrency testing requires genuine PostgreSQL.*

## Database Integrity

Critical invariants are pushed directly to PostgreSQL utilizing constraints:
- `event_ends_after_starts`: Events cannot end before they begin.
- `event_capacity_positive_or_null`: Capacity must be strictly positive or unbounded (`NULL`).
- `enrollment_unique_event_seeker`: Eliminates duplicate parallel enrollments.
- `enrollment_status_valid`: Status must be 'enrolled' or 'canceled'.

Indexes optimize primary queries (`event_starts_at_idx`).

## Error Format

The API standardizes error responses utilizing custom `APIException` classes, guaranteeing consistent frontend parsing:
```json
{
    "detail": "The event has already started.",
    "code": "event_started"
}
```

## Known Limitations

- **Email Delivery:** Currently leverages the development console email backend rather than an external production provider like SendGrid.
- **Concurrency Setup:** Concurrency protection relies exclusively on PostgreSQL row-level locking. 
- **Search Robustness:** Relies on Django's default `icontains` filters rather than dedicated PostgreSQL full-text/trigram vectors.

## What I Would Improve With Another Day

1.  **Production Email Provider:** Integrate SendGrid/AWS SES for reliable transactional OTP delivery.
2.  **API Documentation:** Introduce `drf-spectacular` to automatically generate Swagger/OpenAPI v3 documentation for rapid frontend consumption.
3.  **Deployment Configuration:** Author a `Dockerfile` and `docker-compose.yml` defining the Django application and PostgreSQL database for containerized deployment.
4.  **Richer Search Indexing:** Transition the `q` search parameter to utilize PostgreSQL `SearchVector` and `TrigramSimilarity` for typo-tolerant event discovery.
5.  **Extensive Load Testing:** Execute locust/k6 test suites to benchmark throughput under extreme multi-tenant enrollment pressure.

## Documentation

- `DECISIONS.md`: Records explicit architectural choices, rejected alternatives, and applied trade-offs.
- `DEBUGGING.md`: Documents genuine technical challenges encountered during implementation and their respective resolutions.
- `PROMPT_LOG.md`: Demonstrates the AI supervision, detailing AI-assisted phases and applied human engineering corrections.
