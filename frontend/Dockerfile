# Build from the repository root so the OpenAPI contract is part of the context:
#   docker build -f frontend/Dockerfile .

FROM node:24-alpine AS build

WORKDIR /app/frontend

# Dependencies first, so a source change does not reinstall them.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
# scripts/gen-api.mjs reads ../docs/api/openapi.json relative to the frontend directory.
COPY docs/api/openapi.json /app/docs/api/openapi.json
RUN npm run gen:api && npm run build


FROM nginxinc/nginx-unprivileged:1.28-alpine AS runtime

# The default server block is replaced; the unprivileged image listens on 8080 as user nginx.
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
