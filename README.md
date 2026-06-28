# Tech Fest Registration — Backend API

Backend for the IEEE Student Branch RVCE tech fest registration system: a student signs up,
pays, receives a QR ticket, and a volunteer scans them in at the gate. Built for the Backend
Development Hiring Challenge.

- **Live, interactive API docs:** run the app and open **http://localhost:8000/docs** (Swagger UI, auto-generated).
- **Scaling answer:** see [SCALE.md](SCALE.md).

---

## Stack & why

| Area | Choice | Reason |
| --- | --- | --- |
| Language / framework | **Python 3.11 + FastAPI** | Auto-generated OpenAPI/Swagger docs; Pydantic request validation out of the box. |
| Server | **Uvicorn** (ASGI) | Async; cheap concurrent connections. |
| Database | **SQLite** + **SQLAlchemy 2.0** | Zero-setup, file-based; WAL mode + atomic SQL for safe concurrency. |
| Auth | **JWT (HS256)** + **Argon2id** | Stateless tokens; memory-hard password hashing (OWASP). |
| Tickets | **Signed token → QR PNG** | The QR encodes an HMAC-signed token, so it cannot be forged or guessed. |
| Payments | **Mock gateway + signed webhook** | Fully testable without real keys; demonstrates signature verification + idempotency. |

---

## Features

**Mandatory**

1. **Authentication** — register + login, JWT, role-based access (student / volunteer).
2. **Registration** — creates a student account and a `pending_payment` ticket.
3. **Tickets** — a student views their own ticket and downloads a QR once confirmed.
4. **Check-in** — a volunteer scans the QR; atomic, no double-entry.
5. **Payment** — order + idempotent signed webhook; confirms the ticket on success.

**Extras built on top**

- Race-free **capacity / sold-out** enforcement (no overselling the last seat).
- Volunteer **`/registrations`** (paginated, filterable) and **`/stats`** dashboard.
- **Bounded-concurrency** password hashing (the implemented core of [SCALE.md](SCALE.md)).
- Per-IP **rate limiting**, **idempotency**, uniform **error envelope**, **request-id** logging.
- **34 automated tests** covering the edge cases, a **Dockerfile**, and a **Postman collection**.

---

## Project structure

```
app/
  main.py            app factory: middleware, error handlers, routers, startup
  config.py          settings from environment / .env
  database.py        engine + SQLite pragmas (WAL, FK, busy_timeout), session, init_db
  models.py          User, Ticket, Payment, EventSeats (seat counter)
  schemas.py         Pydantic request/response models
  security.py        bounded Argon2id, JWT, signed ticket tokens
  deps.py            get_current_user, require_role (RBAC)
  errors.py          uniform error envelope + exception handlers
  qr.py              ticket token -> QR PNG
  ratelimit.py       slowapi limiter
  logging_mw.py      request-id + access logging
  routers/           auth, tickets, payments, checkin, registrations, health
  services/          registration, payments, checkin (transactional logic)
scripts/
  create_volunteer.py  CLI to create a volunteer account
tests/                 pytest edge-case suite
postman/               Postman collection
```

---

## Quick start (local)

Prerequisites: **Python 3.11+**.

```bash
# 1. Clone and enter
git clone https://github.com/TheClazer/techfest-registration-backend.git
cd techfest-registration-backend

# 2. Create a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (defaults are fine for local dev)
cp .env.example .env        # Windows: copy .env.example .env

# 5. Run
uvicorn app.main:app --reload
```

Now open **http://localhost:8000/docs** for the interactive API, or `GET http://localhost:8000/health`.

### Run with Docker

```bash
docker build -t techfest .
docker run -p 8000:8000 --env-file .env techfest
```

---

## Create a volunteer account (for testing)

Volunteers cannot be created through the public API (privileged role). Use the CLI from the
project root, with your virtualenv active and the same `.env` as the server:

```bash
python -m scripts.create_volunteer --email volunteer@rvce.edu --password "password123" --name "Gate Volunteer"
```

Then log in via `POST /auth/login` with those credentials to get a volunteer JWT. (Re-running the
command on an existing user promotes them to volunteer.)

---

## Running the tests

```bash
pytest
```

34 tests cover registration, login, tickets/QR, payments + idempotency, check-in, RBAC, and
capacity. (Argon2 cost is lowered in tests for speed; rate limiting is disabled in tests because
its store is process-global — the 429 path is exercised manually.)

---

## Assumptions

- **No real email/SMS** — the ticket (status + QR) is delivered through the API (`/tickets/me`).
- **No real payment gateway** — a mock simulates it via an HMAC-signed webhook (see below). In a
  real deployment, `/payments/webhook` would be the gateway's callback URL.
- **Single event.** Capacity (`CAPACITY`) is configurable; a seat is consumed at **payment
  confirmation** (you "have a seat" only once paid).
- **One ticket per user.** Registration auto-creates the `pending_payment` ticket.
- **Volunteers via CLI**, not public signup.
- **In-memory rate limiting** (single instance) — the multi-instance path is in [SCALE.md](SCALE.md).
- **Secrets via environment.** `.env.example` ships safe placeholders; change them in production.

---

## Payment webhook signing

The mock gateway authenticates its callback with an HMAC-SHA256 signature:

```
signature = HMAC_SHA256(key = PAYMENT_WEBHOOK_SECRET, message = "<order_id>:<status>")   # hex
```

Compute it in Python:

```python
import hmac, hashlib
sig = hmac.new(b"dev-webhook-secret-change-me", b"order_xxx:paid", hashlib.sha256).hexdigest()
```

The included Postman collection computes this automatically in a pre-request script.

---

## API reference

Base URL: `http://localhost:8000`. Auth: send `Authorization: Bearer <token>`.
All errors share one shape:

```json
{ "error": { "code": "machine_code", "message": "Human readable.", "details": null } }
```

### Auth

| Method | Path | Auth | Body | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/register` | — | `{name, email, password}` | `201` user + ticket + `access_token` | `422` invalid · `409` `email_taken` · `429` |
| POST | `/auth/login` | — | `{email, password}` | `200` `access_token` + user | `401` `invalid_credentials` · `422` · `429` |

`POST /auth/register` request:

```json
{ "name": "Asha", "email": "asha@rvce.edu", "password": "password123" }
```

Response `201`:

```json
{
  "user": { "id": 1, "name": "Asha", "email": "asha@rvce.edu", "role": "student", "created_at": "..." },
  "ticket": { "id": 1, "status": "pending_payment", "created_at": "...", "ticket_code": null, "qr_png_base64": null },
  "access_token": "eyJ...", "token_type": "bearer"
}
```

### Tickets (student)

| Method | Path | Auth | Success | Errors |
| --- | --- | --- | --- | --- |
| GET | `/tickets/me` | student | `200` ticket (with `ticket_code` + `qr_png_base64` once confirmed) | `401` · `404` `no_ticket` |
| GET | `/tickets/me/qr` | student | `200` `image/png` | `401` · `404` · `409` `ticket_not_confirmed` |

### Payments

| Method | Path | Auth | Body | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/payments/order` | student | — | `200` `{order_id, amount, currency, status}` | `401` · `404` `no_ticket` · `409` `already_paid` |
| POST | `/payments/webhook` | signature | `{order_id, status, signature}` | `200` `{order_id, payment_status, ticket_status}` | `400` `invalid_signature` · `404` `order_not_found` · `409` `sold_out` |

`amount` is in paise (e.g. `50000` = ₹500.00). `/payments/order` is idempotent (returns the existing
open order). `/payments/webhook` is idempotent (replays do not double-confirm).

### Check-in (volunteer)

| Method | Path | Auth | Body | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/checkin` | volunteer | `{ticket_code}` | `200` `{ticket_id, status, student, checked_in_at}` | `400` `invalid_ticket` · `401` · `403` · `404` · `409` `already_checked_in` / `not_confirmed` |

`ticket_code` is the signed token from the student's QR (the `ticket_code` field of `/tickets/me`).

### Volunteer dashboard

| Method | Path | Auth | Query | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/registrations` | volunteer | `status`, `page`, `page_size` | `200` `{items, total, page, page_size}` | `401` · `403` |
| GET | `/stats` | volunteer | — | `200` `{event, capacity, total_registered, paid, checked_in, remaining}` | `401` · `403` |

### Misc

| Method | Path | Auth | Success |
| --- | --- | --- | --- |
| GET | `/health` | — | `200 {status:"ok"}` |
| GET | `/docs`, `/openapi.json` | — | Swagger UI / OpenAPI schema |

---

## How edge cases are handled

| Scenario | Response |
| --- | --- |
| Duplicate email registration | `409 email_taken` (case-insensitive; UNIQUE constraint is the hard guard) |
| Invalid / missing fields | `422` (Pydantic) |
| Wrong password or unknown email | `401 invalid_credentials` (generic; timing-equalized to prevent enumeration) |
| Missing / invalid / expired JWT | `401` |
| Student calls a volunteer endpoint | `403` |
| Forged or tampered QR | `400 invalid_ticket` |
| Checking in an unpaid ticket | `409 not_confirmed` |
| Checking in twice | `409 already_checked_in` (atomic conditional UPDATE) |
| Replayed payment webhook | Idempotent — no double confirm |
| Invalid webhook signature | `400 invalid_signature` |
| Last-seat race / capacity reached | `409 sold_out` (atomic seat counter — no oversell) |
| Registration spike | Hashing bounded by a semaphore → fixed memory ceiling (see SCALE.md) |
| Unexpected error | `500` uniform envelope, no stack trace leaked, logged with request id |

---

## Testing with Postman

Import `postman/techfest.postman_collection.json`. Set the `base_url` variable
(`http://localhost:8000`). Requests auto-capture the student token, volunteer token, `order_id`,
and `ticket_code` into collection variables, and the webhook request signs itself. Suggested order:
**Register → Create Order → Webhook Confirm → Get My Ticket → (create volunteer via CLI) →
Login as Volunteer → Check In → Stats.**
