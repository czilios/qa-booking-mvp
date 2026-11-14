# Operator authentication configuration

The application requires `OPERATOR_PASSWORD_HASH` to start operator authentication.
Configure it in the server's secret/environment manager; do not put a password or
hash in source control, migrations, or a committed `.env` file. There is no default
credential. Startup fails if the setting is missing, malformed, or not Argon2id.
The Argon2id hash must meet at least the `argon2-cffi` RFC 9106 low-memory
profile used by the application: 64 MiB (`memory_cost=65536` KiB), three
iterations, and four lanes (`parallelism=4`). The hash generator uses the
library's current defaults, and startup rejects weaker configured hashes.

To generate a hash locally, run `python -m app.auth` in an environment with the
project dependencies installed. The command reads the password without echoing it
and prints only its Argon2id hash. Transfer that hash directly to the server's
secret manager.

Set `APP_ENV` explicitly to one of `production`, `development`, `local`, or
`test`; startup rejects missing or unknown values. `SESSION_COOKIE_SECURE`
defaults to `true`, and production cannot disable it. For local HTTP only, set
`APP_ENV=local` (or `test`) and explicitly set
`SESSION_COOKIE_SECURE=false`. Production must use HTTPS.

The login attempt limiter currently runs in process memory and applies
independently in each application worker. It is a basic per-worker throttle, not
a complete production brute-force defense. A future shared limiter can use the
existing MariaDB with an atomic counter table keyed by action and a normalized
client IP plus a fixed time bucket, updated using an upsert. It should have a
bounded retention/cleanup policy and must only trust forwarded client IP headers
when they are set by a trusted proxy. This shared limiter is not implemented in
Stage 1.1; the existing limiter behavior for other routes is unchanged.

Migration `010_operator_sessions.sql` creates only the `operator_sessions` table.
It is part of the repository migration sequence but was not applied as part of
Stage 1 implementation.

Stage 1 adds login/session primitives only. It does not protect existing routes;
do not treat a deployment of Stage 1 alone as an access-control release. Global
route protection and CSRF are a later stage.
