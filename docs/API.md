# API documentation

Interactive docs with a **Try it out** button: `/docs` (Swagger) and `/redoc` on any running server.

All endpoints except the *Public* ones need the header `Authorization: Bearer <token>`. Errors are JSON: `{"detail": "..."}`. Common status codes: 400 bad input, 401 not logged in, 403 wrong role, 404 not found (or not yours), 409 conflict (e.g. wrong request status), 422 validation error, 429 too many attempts.


## Auth

| Method | Path | Who | What |
|---|---|---|---|
| POST | `/api/auth/register` | Public | Create customer or provider account |
| POST | `/api/auth/login` | Public | Log in, returns JWT |
| GET | `/api/auth/me` | Any user | Current user |
| POST | `/api/auth/logout` | Any user | Log out |

## Health

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/health` | Public | Server and database status |
| GET | `/api/db/tables` | Admin | List database tables |

## Profile

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/users/me/profile` | Any user | My profile |
| PUT | `/api/users/me/profile` | Any user | Update name, phone, bio, city |
| POST | `/api/users/me/photo` | Any user | Upload photo (JPG/PNG/WEBP, 2 MB) |
| DELETE | `/api/users/me/photo` | Any user | Remove photo |

## Provider

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/providers/me` | Provider | My provider profile |
| PUT | `/api/providers/me` | Provider | Save description, experience, pricing |
| PUT | `/api/providers/me/skills` | Provider | Choose skills (max 15) |
| PUT | `/api/providers/me/availability` | Provider | Weekly time slots |
| GET | `/api/providers/{id}` | Public | Public profile with rating and recent reviews |
| GET | `/api/providers/{id}/reviews` | Public | Reviews of a provider |

## Services

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/services/categories` | Public | Categories with skills |
| GET | `/api/services/skills` | Public | Search skills |
| POST | `/api/services/skills` | Provider | Add a custom skill |

## Search

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/search/providers` | Public (near_me needs login) | Search by skill, category, city, rating, time |

## Requests

| Method | Path | Who | What |
|---|---|---|---|
| POST | `/api/requests/short-term` | Customer | One-time request |
| POST | `/api/requests/regular` | Customer | Regular (long-term) request |
| GET | `/api/requests/mine` | Customer / Provider | My requests (filter by status) |
| GET | `/api/requests/{id}` | Customer / Provider of that request | One request |
| POST | `/api/requests/{id}/accept` | Provider of the request | Accept |
| POST | `/api/requests/{id}/reject` | Provider of the request | Reject |
| POST | `/api/requests/{id}/complete` | Provider of the request | Mark completed (after start time) |
| POST | `/api/requests/{id}/cancel` | Customer / Provider of the request | Cancel |

## Messages

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/messages/inbox` | Customer / Provider | My conversations |
| GET | `/api/requests/{id}/messages` | Customer / Provider of the request | Chat history (`after_id` for new ones) |
| POST | `/api/requests/{id}/messages` | Customer / Provider of the request | Send message (max 1000 chars) |

## Reviews

| Method | Path | Who | What |
|---|---|---|---|
| POST | `/api/requests/{id}/review` | Customer of a completed request | Rate 1 to 5 + comment, once |
| GET | `/api/reviews/mine` | Customer | Reviews I wrote |

## Dashboard

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/dashboard/customer` | Customer | Customer dashboard data |
| GET | `/api/dashboard/provider` | Provider | Provider dashboard data |
| GET | `/api/dashboard/admin` | Admin | Platform numbers |

## Admin

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/api/admin/users` | Admin | All users |
| GET | `/api/admin/providers` | Admin | Providers with ratings |
| GET | `/api/admin/requests` | Admin | All requests |
| GET | `/api/admin/skills` | Admin | All skills |
| DELETE | `/api/admin/skills/{id}` | Admin | Delete a custom skill |

## Example

```bash
curl -X POST https://YOUR-SITE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "YourPassword1"}'
# -> {"access_token": "...", "token_type": "bearer", "role": "CUSTOMER", "full_name": "..."}
```
