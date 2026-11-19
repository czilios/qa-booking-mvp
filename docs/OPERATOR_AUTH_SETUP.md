# Operator authentication and Isbre configuration

The current application requires a valid operator password hash and an explicit
application environment before startup. It fails closed when authentication
configuration is missing or invalid. There is no default operator password.

## Runtime configuration

The Isbre wrapper at `~/apps/mvp-api/app.py` explicitly loads
`.env.isbre-test` before importing the application. Configure the variables
below in that already-loaded environment file using the server's approved
secret-handling process. The wrapper does not need to be changed. Set
`APP_ENV=test` for the test instance and `APP_ENV=production` for the live
production instance; the environment value does not select the database.

| Variable | Requirement |
| --- | --- |
| `OPERATOR_PASSWORD_HASH` | Required at startup. Must be a valid Argon2id hash with at least 65536 KiB memory, 3 iterations, and 4 lanes. |
| `APP_ENV` | Required at startup. Use `test` for the test instance and `production` for the live instance. Accepted values are `production`, `development`, `local`, and `test`. |
| `DB_HOST` | Required when the application connects to its runtime database. |
| `DB_NAME` | Required when the application connects to its runtime database. |
| `DB_USER` | Required when the application connects to its runtime database. |
| `DB_PASSWORD` | Required when the application connects to its runtime database. |
| `CSRF_TRUSTED_ORIGINS` | Required for operator login. Provide the public application origin, including scheme and optional port, without a path. |

`DB_PORT` is optional and defaults to `3306`. `SESSION_COOKIE_SECURE` is also
optional and defaults to `true`. Keep it enabled on both the HTTPS test instance
and production. The application only permits `SESSION_COOKIE_SECURE=false` in
explicit `local` and `test` environments; HTTPS deployments should not disable
it.

`PUBLIC_SITE_ORIGINS` is optional and configures CORS for browser requests to
the public API. Set it to the public website origin or comma-separated origins
if they differ from the built-in local development defaults.

For example, for an operator interface at
`https://booking.example/api`, set `CSRF_TRUSTED_ORIGINS` to
`https://booking.example`. An origin has no path, so do not include `/api`.
The app's `root_path=/api` URL handling is separate from origin validation.

`TEST_MODE` and `TEST_DB_*` belong to automated database tests. Do not configure
them as production database settings.

## Generate and transfer the password hash

On a trusted machine with the project dependencies installed, run:

```text
python -m app.auth
```

The command prompts for a password without echoing it, asks for confirmation,
and prints its Argon2id hash. Use a strong, unique operator password. Transfer
the generated hash directly to the authorized person or secure server process
that maintains `.env.isbre-test`, then set it as `OPERATOR_PASSWORD_HASH` there.
Use an approved secure channel or secret-handling procedure; do not paste the
hash into source files, chat, tickets, shell history, or a committed environment
file. Treat the hash as a secret. Never store the plaintext password on the
server or in the repository.

The application checks that the configured hash is valid Argon2id and meets the
minimum parameters above. Missing, malformed, non-Argon2id, or weaker hashes
prevent startup. There is no fallback credential.

## Login origin and session protections

`CSRF_TRUSTED_ORIGINS` is checked when the operator submits the login form. Use
the exact externally visible scheme, hostname, and non-default port where
applicable, with no path, query, or trailing slash. An empty, invalid, or
mismatching value prevents login.

Authenticated state-changing requests also require the session-bound CSRF token.
The application stores session and CSRF token hashes in the database, uses
HTTP-only session cookies, and applies idle and absolute session expiry. Keep
these authentication, authorization, and CSRF checks enabled.

`APP_ENV` must be set to an accepted value. It controls two behaviors relevant
to deployment:

- `production` disables the interactive API documentation routes `/docs`,
  `/redoc`, and `/openapi.json`.
- `test`, `development`, and `local` enable those routes. The access-control
  middleware treats them as technical routes, so they do not require an
  operator session. On a reachable test instance, use `APP_ENV=test` when that
  documentation exposure is acceptable. If it should be hidden, `production`
  disables it, but the value alone does not make the instance use a production
  database or change its data.

The environment also constrains `SESSION_COOKIE_SECURE`: disabling it is
accepted only for `local` and `test`; the default is `true` for every accepted
environment. For the HTTPS test instance at `test.wrzosowo159.pl`, use
`APP_ENV=test` and keep `SESSION_COOKIE_SECURE=true`. The selected test database
is controlled separately by `DB_NAME`.
