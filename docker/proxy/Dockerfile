# Build context: docker/proxy.  docker build --target proxy docker/proxy
# Two targets: "certs" is a one-shot generator of the development certificate, "proxy" is nginx.

FROM alpine:3.22 AS certs

RUN apk add --no-cache openssl \
    && mkdir /certs \
    && chown 101:101 /certs
COPY --chmod=0755 gen-dev-cert.sh /usr/local/bin/gen-dev-cert.sh

# The same numeric user as the nginx-unprivileged image, so the proxy can read what is written.
# A new named volume inherits the owner of /certs from this image.
USER 101:101
ENTRYPOINT ["/usr/local/bin/gen-dev-cert.sh"]


FROM nginxinc/nginx-unprivileged:1.28-alpine AS proxy

# Rendered at start by the image entrypoint; only variables named PUBLIC_* are substituted.
ENV NGINX_ENVSUBST_FILTER=^PUBLIC_
COPY templates /etc/nginx/templates

EXPOSE 8080 8443
