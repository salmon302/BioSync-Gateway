#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Generate TLS certificates for BioSync-Gateway (SRS NFR-S4).
#
# Produces:
#   nginx/ssl/server.key, nginx/ssl/server.crt
#       Self-signed server certificate for the nginx TLS 1.3 reverse proxy.
#   certs/ca.key, certs/ca.crt
#       Local certificate authority used to issue the PostgreSQL client cert.
#   certs/client.key, certs/client.crt
#       Client certificate for mutual-TLS to PostgreSQL (DB_SSLMODE=verify-full).
#
# For production, replace these with certificates from a trusted CA
# (e.g. Let's Encrypt) and never commit the private keys.
#
# Usage:
#   ./nginx/generate-certs.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_SSL_DIR="${SCRIPT_DIR}/ssl"
CERTS_DIR="${SCRIPT_DIR}/../certs"

mkdir -p "${NGINX_SSL_DIR}" "${CERTS_DIR}"

echo "==> Generating nginx server certificate (self-signed, CN=localhost)"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "${NGINX_SSL_DIR}/server.key" \
    -out "${NGINX_SSL_DIR}/server.crt" \
    -subj "/C=US/ST=State/L=City/O=BioSync/CN=localhost"

echo "==> Generating PostgreSQL client-certificate CA"
openssl genrsa -out "${CERTS_DIR}/ca.key" 2048
openssl req -x509 -new -nodes -days 365 \
    -key "${CERTS_DIR}/ca.key" \
    -out "${CERTS_DIR}/ca.crt" \
    -subj "/C=US/ST=State/L=City/O=BioSync/CN=biosync-ca"

echo "==> Issuing PostgreSQL client certificate (signed by CA)"
openssl genrsa -out "${CERTS_DIR}/client.key" 2048
openssl req -new -key "${CERTS_DIR}/client.key" \
    -out "${CERTS_DIR}/client.csr" \
    -subj "/C=US/ST=State/L=City/O=BioSync/CN=biosync-client"
openssl x509 -req -in "${CERTS_DIR}/client.csr" \
    -CA "${CERTS_DIR}/ca.crt" -CAkey "${CERTS_DIR}/ca.key" -CAcreateserial \
    -out "${CERTS_DIR}/client.crt" -days 365

echo "==> Issuing PostgreSQL SERVER certificate (signed by CA)"
# The middleware presents ca.crt as sslrootcert, so the server cert the
# database presents must chain to that same CA for verify-full to succeed.
openssl genrsa -out "${CERTS_DIR}/server.key" 2048
openssl req -new -key "${CERTS_DIR}/server.key" \
    -out "${CERTS_DIR}/server.csr" \
    -subj "/C=US/ST=State/L=City/O=BioSync/CN=biosync-db"
openssl x509 -req -in "${CERTS_DIR}/server.csr" \
    -CA "${CERTS_DIR}/ca.crt" -CAkey "${CERTS_DIR}/ca.key" -CAcreateserial \
    -out "${CERTS_DIR}/server.crt" -days 365

echo "==> Setting restrictive permissions on private keys"
# Server key is copied into the db container's PGDATA at startup and re-chmod'd
# 600 there; 644 here keeps it readable by the postgres (uid 70) container user
# regardless of host UID. Client key stays 600 (libpq enforces 0600/0640).
chmod 600 "${NGINX_SSL_DIR}/server.key" "${CERTS_DIR}/ca.key" "${CERTS_DIR}/client.key"
chmod 644 "${CERTS_DIR}/server.key"
chmod 644 "${NGINX_SSL_DIR}/server.crt" "${CERTS_DIR}/ca.crt" "${CERTS_DIR}/client.crt" "${CERTS_DIR}/server.crt"

echo "Done. Certificates written to nginx/ssl and certs/."
echo "  - nginx/ssl/server.{crt,key}      : nginx TLS 1.3 termination (self-signed)"
echo "  - certs/ca.{crt,key}              : BioSync CA (signs client + server certs)"
echo "  - certs/client.{crt,key,csr,srl}  : PostgreSQL CLIENT cert (middleware -> db)"
echo "  - certs/server.{crt,key,csr}      : PostgreSQL SERVER cert (db presents to clients)"
