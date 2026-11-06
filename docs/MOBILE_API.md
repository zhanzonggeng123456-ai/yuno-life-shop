# Native App API

All responses under `/api/v1` are JSON. Existing HTML routes remain available.
The API validates input then calls the same existing business entry points.
No schema migration is introduced by the mobile adapter.

## Authentication

`POST /api/v1/actions/register` accepts email, display_name, password and optional
phone. `POST /api/v1/actions/login` accepts email and password. Both return a
random session token and a user object without password hashes or salts.

Send `Authorization: Bearer <token>` for authenticated reads and commands.
Tokens reuse the existing expiring sessions table. Logout revokes the session.
Cookie-only authentication is rejected by the native API.

## Configuration and reads

- `GET /api/v1/config` returns categories with attribute definitions, active regions,
  the three service prices, simulation flags and command field descriptions.
- `GET /api/v1/me` returns the signed-in user.
- `GET /api/v1/listings` supports q, category, region, price_min, price_max,
  owned, mine, offset and limit. Listing responses include the ordered photo URLs.
- `GET /api/v1/{resource}` and `/{resource}/{id}` support listings, orders,
  offers, auctions, buybacks, drafts, deliveries, services, refunds, disputes and jobs.
  Private resources enforce ownership or an appropriate operations role.
- `GET /api/v1/threads` and `/threads/{listing_id}/{buyer_id}` return
  participant-only messages.
- `GET /api/v1/market` returns per-product gainers/losers, category statistics,
  top listings, weekly prices and collectible statistics from the existing logic.
- `GET /api/v1/profiles/{id}` returns public profile and review information.
- `GET /api/v1/rules/{terms|privacy|returns|prohibited}` returns authored rules
  as plain text for native display.
- `GET /api/v1/admin/{resource}` enforces operations roles. Users and settings
  require admin. High-value reviews also allow the appraiser role.

## Commands

`POST /api/v1/actions/{name}` accepts a JSON object using the named parameters
reported by config. Commands with photos use multipart form data with the
reported photo field. Each file is limited to 5MB and each listing/draft to
10 photos. The first photo is the cover.

The allowlist covers publishing, photo editing, one-click recognition/model
confirmation/publishing, AI jobs, purchase, offers, auction bids/proxy limits,
buybacks, simulated payment, orders, reviews, delivery, the three services,
refunds/disputes, messages and role-restricted operations actions.

Redirect-based business outcomes are mapped into JSON containing message,
resource and id. Business refusals return 409. Invalid input returns 400,
missing/expired bearer authentication returns 401 and denied operations return
403 or a private-resource 404. Unknown commands return 404.

Payment callers supply a stable idempotency key for retries of one order.
The Flutter client derives a stable operation identifier for that order/user.
Successful retries reuse the existing mock-payment checks and do not add charges.
Commands are serialized within the single-process SQLite deployment. Run one
Uvicorn worker, as in the supplied startup, for this internal trial deployment.

## AI

Create `ai_job_create` with kind `oneclick_recognize` or `oneclick_valuation`
and draft_id, then poll `GET /api/v1/jobs/{id}`. The owner can retrieve queued,
running, done or failed state. The app also exposes the task history.

Only existing local heuristics and exact-model market search are used.
An unconfirmed model or missing reliable market samples produces an explicit
no-quote result. The client requires a user-confirmed price before publishing.
Market-source status, sample counts, evidence and the required disclaimer are
displayed with the result. No paid model API is added.

## Operational scope

Payments, delivery actions and deposits are simulated. Fees remain governed by
existing business functions. Runtime databases, uploads and tokens are excluded
from version control. Use a separate database/upload directory for acceptance
tests so test transactions never become platform market statistics.
