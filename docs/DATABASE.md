# Database schema

MySQL 8, character set `utf8mb4`. Full SQL: [`database/schema.sql`](../database/schema.sql). Diagram: [ER_DIAGRAM.md](ER_DIAGRAM.md).

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Every account (customer, provider, admin) | `email` (unique), `password_hash` (bcrypt), `role`, `location_id` |
| `locations` | City / area / pincode, shared by users and requests | unique (`city`, `area`, `pincode`) |
| `provider_profiles` | Extra details of providers | `user_id` (unique), `description`, `experience_years`, `service_mode`, `pricing_info` |
| `categories` | Groups of skills (Electrician, Tutor...) | `name` (unique) |
| `skills` | Individual skills | `category_id`, `name` (unique), `created_by_id` (NULL = official) |
| `provider_skills` | Which provider offers which skill (many-to-many) | unique (`provider_profile_id`, `skill_id`) |
| `availability` | Weekly time slots of a provider | `day_of_week`, `start_time`, `end_time` |
| `service_requests` | A customer's request to a provider | `customer_id`, `provider_id`, `skill_id`, `service_mode`, `status`, one-time or regular fields |
| `messages` | Chat messages of one request | `service_request_id`, `sender_id`, `body` |
| `reviews` | One rating + comment per completed request | `service_request_id` (unique), `rating` 1 to 5 |

**Integrity rules:** a customer cannot send a request to themselves (`CHECK`), ratings are 1 to 5 (`CHECK`), one review per request (`UNIQUE`), deleting a user deletes their requests, messages and reviews (`ON DELETE CASCADE`), skills in use cannot be deleted (`ON DELETE RESTRICT`).
