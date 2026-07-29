# SPDX-License-Identifier: MIT
# Database Client-Certificate TLS (NFR-S5)

BioSync-Gateway enforces **mutual-TLS** between the middleware and PostgreSQL:
the connection is encrypted (`sslmode=verify-full`) **and** the middleware
presents a client certificate signed by the BioSync CA. This satisfies
SRS NFR-S5 ("DB client-cert auth in addition to password").

This document is the R2 remediation deliverable from `REMAINING_WORK_v1.1.md`.

---

## 1. How the default is enforced

`middleware/database.py` resolves `DB_SSLMODE` with an environment-aware
default (fail-closed in production):

| `ENVIRONMENT`   | `DB_SSLMODE` default | Behavior |
|-----------------|----------------------|----------|
| `production`    | `verify-full`        | Mutual-TLS required. Connection fails fast if the server cert cannot be verified or no client cert is presented. |
| anything else (development / test / CI) | `prefer` | TLS is attempted and used when the server offers it; falls back to cleartext for local stacks without a PKI. |

`DB_SSLMODE` can always be overridden explicitly (e.g. `disable` for a bare
local Postgres with no TLS).

The `docker-compose.yml` middleware service sets `DB_SSLMODE=verify-full`
explicitly and mounts the client certificate, so the shipped stack enforces
mutual-TLS regardless of `ENVIRONMENT`.

---

## 2. Generate the certificates

```bash
./nginx/generate-certs.sh
```

This writes:

| File | Purpose |
|------|---------|
| `nginx/ssl/server.{crt,key}` | nginx TLS 1.3 termination (self-signed). |
| `certs/ca.{crt,key}` | BioSync CA — signs both client and server certs. |
| `certs/client.{crt,key}` | **Client** certificate: middleware → PostgreSQL. |
| `certs/server.{crt,key}` | **Server** certificate: PostgreSQL presents to clients (signed by the same CA so `verify-full` succeeds). |

> The `certs/` and `nginx/ssl/` directories are git-ignored (never commit
> private keys). Regenerate per environment.

---

## 3. Server-side enforcement (`pg_hba.conf`)

`database/postgres/pg_hba.conf` contains only `hostssl` network lines that
require a valid client certificate:

```
hostssl all  all  0.0.0.0/0  scram-sha-256 clientcert=verify-full
hostssl all  all  ::/0        scram-sha-256 clientcert=verify-full
```

`clientcert=verify-full` means PostgreSQL verifies the client certificate
chains to `ssl_ca_file` **and** still checks the password — two factors.
Local socket / loopback lines use `trust` for in-container admin tooling.

In `docker-compose.yml` the `db` service:

1. mounts `certs/` (read-only) and the `pg_hba.conf` (read-only),
2. copies the CA + server cert + `pg_hba.conf` into `PGDATA` at startup, and
3. launches `postgres` with `ssl=on` and the cert paths.

Because only `hostssl` lines exist, any non-TLS network connection is
rejected outright (fail-closed).

---

## 4. Running the stack

```bash
./nginx/generate-certs.sh      # required once before first `up`
cp .env.example .env           # already references the cert paths
docker compose up -d db middleware
```

The middleware container mounts `certs/` at `/etc/ssl/certs` (read-only) and
uses:

```
DB_SSLMODE=verify-full
DB_SSLROOTCERT=/etc/ssl/certs/ca.crt
DB_SSLCERT=/etc/ssl/certs/client.crt
DB_SSLKEY=/etc/ssl/certs/client.key
```

> **Permission note:** the client key (`certs/client.key`) is `0600`. The
> middleware container runs as UID 1000; ensure the key file is readable by
> that UID on your host (typically true when your dev user is UID 1000). The
> server key is copied into the db container and `chmod 600`'d there.

---

## 5. Load testing against the TLS stack (PQ-3)

`.github/workflows/pq.yml` brings up the compose stack and must present a
client certificate. It runs `generate-certs.sh` first and passes the certs
in `BIOSYNC_PQ3_DATABASE_URL`, e.g.:

```
postgresql://biosync_user:PASSWORD@localhost:5432/biosync?sslmode=verify-full&sslrootcert=certs/ca.crt&sslcert=certs/client.crt&sslkey=certs/client.key
```

---

## 6. Production guidance

- Replace the self-signed BioSync CA with an enterprise CA.
- Inject `certs/*` via Docker secrets / a secrets manager — do not bake keys
  into images or commit them.
- Keep `ENVIRONMENT=production` so the middleware enforces `verify-full` even
  if the compose override is omitted.
