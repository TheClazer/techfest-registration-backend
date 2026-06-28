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

## Architecture

**Request flow:** `client → Uvicorn → request-context middleware (assigns X-Request-ID) → router → service → SQLAlchemy/SQLite`, with a single exception layer wrapping everything so every failure returns the same JSON envelope.

**Layering (why it's organised this way):**
- `routers/` — HTTP only: validate input, call a service, shape the response. Thin and readable.
- `services/` — business logic and transactions (registration, payments, check-in). All state changes and the atomic/idempotent logic live here.
- `models.py` vs `schemas.py` — database models are kept separate from API request/response contracts.
- `security.py` / `deps.py` — hashing + tokens, and the auth/RBAC dependencies.
- `errors.py` — one uniform error envelope (with a traceable `request_id`) for the whole app.

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

**Make shortcuts** (optional): `make install` · `make run` · `make run-prod` · `make test` · `make volunteer` · `make docker`.

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

42 tests cover registration, login, tickets/QR, payments + idempotency, atomic check-in, RBAC,
capacity, and **real-concurrency races** (duplicate registration, double check-in, last-seat) in
`tests/test_concurrency.py`. (Argon2 cost is lowered in tests for speed; rate limiting is disabled in
tests since its store is process-global — the 429 path is verified separately.)

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

## End-to-end test (copy-paste)

Three ways to test, pick one:

1. **Swagger UI** — open `http://localhost:8000/docs`, click **Authorize**, and "Try it out" on each endpoint.
2. **Postman** — import `postman/techfest.postman_collection.json` (tokens, ids, and the webhook signature are handled automatically).
3. **curl** — the full flow below (bash; works in Git Bash on Windows). It uses the project's own Python to parse JSON and sign the webhook, so no extra tools are needed.

```bash
BASE=http://localhost:8000

# 1) Register a student  ->  capture the JWT
TOKEN=$(curl -s -X POST $BASE/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Asha","email":"asha@rvce.edu","password":"password123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2) Create a payment order  ->  capture the order id
ORDER=$(curl -s -X POST $BASE/payments/order -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;print(json.load(sys.stdin)['order_id'])")

# 3) Sign + send the gateway webhook to confirm payment
SIG=$(python -c "import hmac,hashlib;print(hmac.new(b'dev-webhook-secret-change-me', b'$ORDER:paid', hashlib.sha256).hexdigest())")
curl -s -X POST $BASE/payments/webhook -H 'Content-Type: application/json' \
  -d "{\"order_id\":\"$ORDER\",\"status\":\"paid\",\"signature\":\"$SIG\"}"

# 4) View the now-confirmed ticket  ->  capture the QR's signed code
CODE=$(curl -s $BASE/tickets/me -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;print(json.load(sys.stdin)['ticket_code'])")

# 5) Create a volunteer (CLI) and log in  ->  capture the volunteer JWT
python -m scripts.create_volunteer --email volunteer@rvce.edu --password password123 --name "Gate Vol"
VTOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"volunteer@rvce.edu","password":"password123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 6) Check the student in at the gate
curl -s -X POST $BASE/checkin -H "Authorization: Bearer $VTOKEN" \
  -H 'Content-Type: application/json' -d "{\"ticket_code\":\"$CODE\"}"

# 7) Volunteer dashboard
curl -s $BASE/stats -H "Authorization: Bearer $VTOKEN"
curl -s "$BASE/registrations?page=1&page_size=50" -H "Authorization: Bearer $VTOKEN"
```

Verify the edge cases respond gracefully (prints just the status code):

```bash
# 409 duplicate registration | 422 invalid input | 401 bad login
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/auth/register -H 'Content-Type: application/json' -d '{"name":"A","email":"asha@rvce.edu","password":"password123"}'
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/auth/register -H 'Content-Type: application/json' -d '{"name":"A","email":"bad","password":"x"}'
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/auth/login    -H 'Content-Type: application/json' -d '{"email":"asha@rvce.edu","password":"nope"}'

# 403 student hitting a volunteer endpoint | 409 double check-in
curl -s -o /dev/null -w "%{http_code}\n" $BASE/registrations -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/checkin -H "Authorization: Bearer $VTOKEN" -H 'Content-Type: application/json' -d "{\"ticket_code\":\"$CODE\"}"
```

**Async registration variant** (the bonus path — accept instantly, then poll):

```bash
JOB=$(curl -s -X POST $BASE/auth/register-async -H 'Content-Type: application/json' \
  -d '{"name":"Bo","email":"bo@rvce.edu","password":"password123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
curl -s $BASE/auth/register/status/$JOB    # poll until "status":"completed"
```

> Re-running the happy path needs a fresh email (or delete `techfest.db` to reset the database).

---

## API reference

Base URL: `http://localhost:8000`. Auth: send `Authorization: Bearer <token>`.
All errors share one shape:

```json
{ "error": { "code": "machine_code", "message": "Human readable.", "details": null } }
```

Summary of every endpoint:

| # | Method | Path | Auth |
| --- | --- | --- | --- |
| 1 | POST | `/auth/register` | public |
| 2 | POST | `/auth/login` | public |
| 3 | GET | `/tickets/me` | student |
| 4 | GET | `/tickets/me/qr` | student |
| 5 | POST | `/payments/order` | student |
| 6 | POST | `/payments/webhook` | HMAC signature |
| 7 | POST | `/checkin` | volunteer |
| 8 | GET | `/registrations` | volunteer |
| 9 | GET | `/stats` | volunteer |
| 10 | GET | `/health` | public |
| 11 | GET | `/docs`, `/openapi.json` | public |

_Plus an additive async path (bonus — see [SCALE.md](SCALE.md)): **`POST /auth/register-async`** returns `202 {job_id}`, then poll **`GET /auth/register/status/{job_id}`**. Documented at the end of this section._

---

### 1. `POST /auth/register`

Create a student account and its `pending_payment` ticket. Public (rate-limited).

**Request body**

```json
{ "name": "Asha", "email": "asha@rvce.edu", "password": "password123" }
```

`name` (1–120 chars), `email` (valid, unique — case-insensitive), `password` (8–128 chars).

**Response `201`**

```json
{
  "user": { "id": 1, "name": "Asha", "email": "asha@rvce.edu", "role": "student", "created_at": "2026-06-28T09:00:00Z" },
  "ticket": { "id": 1, "status": "pending_payment", "created_at": "2026-06-28T09:00:00Z",
              "confirmed_at": null, "checked_in_at": null, "ticket_code": null, "qr_png_base64": null },
  "access_token": "eyJhbGciOi...", "token_type": "bearer"
}
```

**Errors** — `422` invalid input · `409` `email_taken` · `429` `rate_limited`

---

### 2. `POST /auth/login`

Authenticate and receive a JWT. Public (rate-limited).

**Request body**

```json
{ "email": "asha@rvce.edu", "password": "password123" }
```

**Response `200`**

```json
{
  "access_token": "eyJhbGciOi...", "token_type": "bearer",
  "user": { "id": 1, "name": "Asha", "email": "asha@rvce.edu", "role": "student", "created_at": "2026-06-28T09:00:00Z" }
}
```

**Errors** — `401` `invalid_credentials` (generic, no user enumeration) · `422` · `429`

---

### 3. `GET /tickets/me`

The authenticated student's own ticket. `ticket_code` and `qr_png_base64` are populated only once the
ticket is `confirmed`. **Request:** no body; `Authorization: Bearer <student token>`.

**Response `200`** (after payment)

```json
{
  "id": 1, "status": "confirmed",
  "created_at": "2026-06-28T09:00:00Z", "confirmed_at": "2026-06-28T09:05:00Z", "checked_in_at": null,
  "ticket_code": "InRpZCI6...signed-token...",
  "qr_png_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Errors** — `401` unauthorized · `404` `no_ticket`

---

### 4. `GET /tickets/me/qr`

The ticket QR as a downloadable image. **Request:** no body; student bearer token.

**Response `200`** — binary body, `Content-Type: image/png`.

**Errors** — `401` · `404` `no_ticket` · `409` `ticket_not_confirmed`

---

### 5. `POST /payments/order`

Create (or fetch the existing open) payment order for the caller's ticket. **Request:** no body;
student bearer token. Idempotent — repeat calls return the same open order.

**Response `200`**

```json
{ "order_id": "order_3f2a...", "amount": 50000, "currency": "INR", "status": "created" }
```

`amount` is in paise (`50000` = ₹500.00).

**Errors** — `401` · `404` `no_ticket` · `409` `already_paid`

---

### 6. `POST /payments/webhook`

Mock payment-gateway callback. Authenticated by an HMAC signature (not a JWT), and idempotent — a
replayed webhook never double-confirms. See **Payment webhook signing** above for the signature.

**Request body**

```json
{ "order_id": "order_3f2a...", "status": "paid", "signature": "9c1f...hex-hmac-sha256" }
```

`status` is `"paid"` or `"failed"`.

**Response `200`**

```json
{ "order_id": "order_3f2a...", "payment_status": "paid", "ticket_status": "confirmed" }
```

**Errors** — `400` `invalid_signature` · `404` `order_not_found` · `409` `sold_out`

---

### 7. `POST /checkin`

Volunteer scans a ticket QR at the gate. Atomic — a ticket can be checked in exactly once.
**Auth:** volunteer bearer token.

**Request body**

```json
{ "ticket_code": "InRpZCI6...signed-token..." }
```

`ticket_code` is the value from the student's `/tickets/me` (`ticket_code`), i.e. the QR contents.

**Response `200`**

```json
{
  "ticket_id": 1, "status": "checked_in",
  "student": { "id": 1, "name": "Asha", "email": "asha@rvce.edu" },
  "checked_in_at": "2026-06-28T18:30:00Z"
}
```

**Errors** — `400` `invalid_ticket` (forged/tampered) · `401` · `403` (not a volunteer) ·
`404` `ticket_not_found` · `409` `already_checked_in` / `not_confirmed`

---

### 8. `GET /registrations`

List all registrations. **Auth:** volunteer bearer token.

**Query parameters** — `status` (optional: `pending_payment` | `confirmed` | `checked_in`),
`page` (default `1`), `page_size` (default `50`, max `200`).

**Response `200`**

```json
{
  "items": [
    { "user_id": 1, "name": "Asha", "email": "asha@rvce.edu", "ticket_id": 1,
      "ticket_status": "checked_in", "registered_at": "2026-06-28T09:00:00Z",
      "checked_in_at": "2026-06-28T18:30:00Z" }
  ],
  "total": 1, "page": 1, "page_size": 50
}
```

**Errors** — `401` · `403`

---

### 9. `GET /stats`

Event totals. **Auth:** volunteer bearer token. **Request:** no body.

**Response `200`**

```json
{ "event": "TechFest 2026", "capacity": 500, "total_registered": 1, "paid": 1, "checked_in": 1, "remaining": 499 }
```

**Errors** — `401` · `403`

---

### 10. `GET /health`

Liveness check. Public, no body.

**Response `200`**

```json
{ "status": "ok", "service": "Tech Fest Registration API", "environment": "development" }
```

---

### 11. `GET /docs` and `GET /openapi.json`

Auto-generated **Swagger UI** and the **OpenAPI schema** documenting every endpoint and model. Public.

---

### Bonus: async registration path

For the registration spike (see [SCALE.md](SCALE.md)), an **additive**, non-blocking path is also
available. The synchronous `/auth/register` above is unchanged; this one accepts instantly and a
bounded background worker pool does the (memory-hard) hashing off the request path.

**`POST /auth/register-async`** — public (rate-limited). Same body as `/auth/register`. Returns `202`:

```json
{ "job_id": "676ea358e8004bd0ba239ab0d931f767", "status": "pending",
  "status_url": "/auth/register/status/676ea358e8004bd0ba239ab0d931f767" }
```

Errors — `409` `email_taken` · `422` · `429` · `503` `overloaded` (queue full).

**`GET /auth/register/status/{job_id}`** — poll until done. Returns `200`; while processing
`status` is `"pending"`, and on completion `result` holds the same payload as the synchronous register:

```json
{ "job_id": "...", "status": "completed",
  "result": { "user": { "...": "..." }, "ticket": { "...": "..." }, "access_token": "eyJ...", "token_type": "bearer" },
  "error": null }
```

Errors — `404` `job_not_found`.

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
