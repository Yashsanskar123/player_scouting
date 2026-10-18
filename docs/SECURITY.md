# Security

ScoutIQ is secure-by-configuration: the defaults keep local development frictionless, and a handful of
environment variables harden a shared deployment. **Admins can see the current state under Admin -> Security**
(or `GET /api/admin/security-status`), and the server logs a warning at start-up for every high or medium gap.

## Checklist for a shared deployment
1. **Sign-in:** `SCOUTIQ_AUTH_MODE=on` with a 32+ character `SCOUTIQ_AUTH_SECRET` (see `docs/AUTH.md`). Remove the bootstrap admin password after first sign-in.
2. **Database:** PostgreSQL (`docker-compose.yml`), with a strong `POSTGRES_PASSWORD`. The database port is not published to the host.
3. **Browser access:** `SCOUTIQ_CORS_ORIGINS=https://your-web-app` (comma separated). A wildcard is flagged as high risk.
4. **HTTPS:** terminate TLS in front of the API (reverse proxy / load balancer) and set `SCOUTIQ_HSTS=on`.
5. **API docs:** `SCOUTIQ_ENABLE_DOCS=false` so `/docs` and `/openapi.json` are not served.
6. **Behind a proxy:** `SCOUTIQ_TRUST_PROXY=on` only when your own proxy sets `X-Forwarded-For`, so rate limits apply per real client.
7. **Secrets:** keep them in `.env` (never committed; see `.env.example`) or your platform's secret store.

## What is built in
| Protection | Behaviour |
|---|---|
| Access control | Opt-in sign-in with four roles; deny-by-default for unknown write endpoints; every change, sign-in, denial and export is audited |
| Passwords | scrypt with per-user salt; sign-in throttling and lock-out; identical error for unknown user and wrong password |
| API key | Optional shared key for machine clients, compared in constant time |
| Rate limiting | Per client IP: `SCOUTIQ_RATE_LIMIT_PER_MINUTE` (default 600) and a tighter `SCOUTIQ_HEAVY_RATE_LIMIT_PER_MINUTE` (default 30) for exports and the optimizer; `/health` is exempt; replies 429 with `Retry-After` |
| Request size | Bodies over `SCOUTIQ_MAX_BODY_BYTES` (default 1 MB) get 413, including streamed bodies with no declared length |
| Input limits | Field lengths are validated (clear 422) instead of failing inside the database; players must exist before they are shortlisted |
| Response headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, API responses `no-store` with a locked-down CSP, optional HSTS |
| Containers | Non-root user, health check, no database port exposed |
| Supply chain | Pinned dependency ranges and a lock file; CI runs an informational `pip-audit` / `npm audit` |

## Known limits
- Rate limiting and sign-in throttling are per server process. For several API instances, also rate-limit at your gateway.
- Tokens live in the browser's local storage and cannot be revoked before they expire (disabling a user does stop them immediately).
- No single sign-on (SAML/OIDC), no field-level encryption, and no malware scanning: add them at the platform level if your policy requires.
- Data is not encrypted at rest by the application; use your database / disk encryption.
