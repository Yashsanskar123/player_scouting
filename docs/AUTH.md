# Authentication, roles and audit trail

Login is **off by default**, so local development and existing deployments behave exactly as before.

## Switch it on
```
SCOUTIQ_AUTH_MODE=on
SCOUTIQ_AUTH_SECRET=<at least 32 random characters>      # python -c "import secrets;print(secrets.token_urlsafe(48))"
SCOUTIQ_BOOTSTRAP_ADMIN_USER=admin                        # optional: creates the first admin when no users exist
SCOUTIQ_BOOTSTRAP_ADMIN_PASSWORD=<10+ characters>         # remove both variables after first sign-in
SCOUTIQ_TOKEN_TTL_MINUTES=480                             # optional, default 8 hours
```
The server refuses to start in `on` mode without a proper secret. Users can also be managed from the command line:
`python -m src.auth.manage create-user alice --role admin`, `set-password alice`, `list`.

## Roles
| Role | Can do |
|---|---|
| analyst | View everything and run analytics (search, compare, optimizer, audit) |
| scout | Analyst + create shortlists, move players, write scout notes |
| director | Scout + edit the club profile |
| admin | Director + manage users, view the audit log, reload data |

Any state-changing endpoint not listed above requires admin (deny by default). Roles are read from the database on every request, so a role change or deactivation applies immediately, even to people already signed in.

## Audit trail
Every shortlist/note/club-profile/user/reload change, every sign-in, failed sign-in, lock-out and denied request is recorded (who, role, action, target, status, request id, IP). Request contents, notes and passwords are never stored. Admins view it under **Audit log**.

## Known limits (by design for this stage)
- Sign-in throttling (5 failures / 5 minutes per username) is per server process; use a gateway/WAF rate limit when running several instances.
- Tokens are stored in the browser's local storage and there is no server-side sign-out revocation; they expire after the configured lifetime, and disabling a user stops them immediately.
- Single sign-on (SAML/OIDC) is not included.
- If `SCOUTIQ_API_KEY` is also set, API clients must send `X-API-Key`; browser users should rely on login instead.
