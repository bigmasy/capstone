#!/bin/sh
# Creates a self-signed TLS certificate for local development in CERT_DIR (a named volume in
# the compose file). The private key is generated here, inside the volume, and exists nowhere
# else: it is never part of the repository or of an image.
#
# Idempotent: an existing certificate is kept while it covers PUBLIC_HOSTNAME and has more than
# 30 days left. To use a real certificate instead, put tls.crt and tls.key into the volume and
# stop running this service.
set -eu

dir="${CERT_DIR:-/certs}"
host="${PUBLIC_HOSTNAME:-localhost}"
days="${CERT_DAYS:-365}"
crt="$dir/tls.crt"
key="$dir/tls.key"

# An IPv4 literal needs an IP entry in subjectAltName; anything else is a DNS name.
case "$host" in
    *[!0-9.]*) host_entry="DNS:$host" ;;
    *) host_entry="IP:$host" ;;
esac

if [ -s "$crt" ] && [ -s "$key" ] \
    && openssl x509 -checkend 2592000 -noout -in "$crt" >/dev/null 2>&1 \
    && openssl x509 -noout -ext subjectAltName -in "$crt" 2>/dev/null | grep -q "${host_entry#*:}"; then
    echo "gen-dev-cert: keeping the existing certificate"
    exit 0
fi

# Owner-only permissions from the first byte; the proxy runs as the same user.
umask 077
tmp_key="$key.tmp"
tmp_crt="$crt.tmp"
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -keyout "$tmp_key" -out "$tmp_crt" -days "$days" \
    -subj "/O=adaptive-sport development/CN=$host" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1,$host_entry" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature" \
    -addext "extendedKeyUsage=serverAuth" >/dev/null 2>&1
mv "$tmp_key" "$key"
mv "$tmp_crt" "$crt"
chmod 644 "$crt"
echo "gen-dev-cert: generated a self-signed certificate for $host (valid $days days)"
