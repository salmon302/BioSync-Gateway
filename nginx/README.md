# Nginx TLS Configuration

This directory contains the Nginx reverse proxy configuration for TLS 1.3 termination.

## Files

- `nginx.conf` - Main Nginx configuration with TLS 1.3 support
- `ssl/` - SSL certificate directory (add your certificates here)

## TLS 1.3 Configuration

The nginx configuration implements:
- TLS 1.3 protocol only (TLS 1.2 and below disabled)
- Strong cipher suites (AES-256-GCM, CHACHA20-POLY1305, AES-128-GCM)
- Perfect Forward Secrecy via ECDH curve secp384r1
- HSTS (HTTP Strict Transport Security)
- OCSP stapling for certificate validation

## SSL Certificates

Place your SSL certificates in the `ssl/` directory:
- `server.crt` - Server certificate (public)
- `server.key` - Server private key (keep secure)
- `ca.crt` - CA certificate for client verification (optional, for mTLS)

### Generating Self-Signed Certificates (Development)

```bash
# Generate server certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/server.key \
  -out ssl/server.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Set proper permissions
chmod 600 ssl/server.key
chmod 644 ssl/server.crt
```

### Production Certificate Setup

For production, use Let's Encrypt or your organization's CA:

```bash
# Using certbot with Let's Encrypt
certbot certonly --nginx -d your-domain.com

# Or copy your organization's certificates
cp /path/to/your/cert.pem ssl/server.crt
cp /path/to/your/key.pem ssl/server.key
cp /path/to/your/ca.pem ssl/ca.crt
```

## Database Client Certificates (Optional)

For mutual TLS authentication with PostgreSQL:

1. Generate client certificate signed by your CA
2. Place in `ssl/` directory:
   - `client.crt` - Client certificate
   - `client.key` - Client private key
   - `ca.crt` - CA certificate for verification

## Environment Variables

Configure these environment variables in `docker-compose.yml`:

- `DB_SSLMODE` - SSL mode (prefer, require, verify-ca, verify-full)
- `DB_SSLROOTCERT` - Path to CA certificate
- `DB_SSLCERT` - Path to client certificate
- `DB_SSLKEY` - Path to client key

## Usage

```bash
# Start with TLS
docker-compose up -d nginx middleware db

# Access via HTTPS
curl -k https://localhost/api/health

# Access via HTTP (redirects to HTTPS)
curl http://localhost/api/health
```

## Security Notes

- Never commit private keys to version control
- Use environment variables for sensitive configuration
- In production, use proper certificates from a trusted CA
- Consider using Docker secrets for certificate management