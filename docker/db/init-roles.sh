#!/bin/sh
# Runs once, when the database volume is created (docker-entrypoint-initdb.d), as the bootstrap
# superuser. Splits the database into two roles:
#   adaptive_owner  owns the schema and runs the migrations (DDL);
#   adaptive_api    is what the running API connects as: data manipulation only, no DDL, no
#                   superuser, no right to create objects or read other databases.
# The superuser is never used by the application. Passwords come from the container environment.
set -eu

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v owner_password="$DB_OWNER_PASSWORD" \
    -v api_password="$DB_API_PASSWORD" <<'SQL'
CREATE ROLE adaptive_owner LOGIN PASSWORD :'owner_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE adaptive_api LOGIN PASSWORD :'api_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

REVOKE ALL ON DATABASE :"DBNAME" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"DBNAME" TO adaptive_owner, adaptive_api;
-- The maintenance database is open to every role by default; the application roles do not
-- need it.
REVOKE ALL ON DATABASE postgres FROM PUBLIC;

-- PostGIS needs a superuser to be installed; the owner then only uses it. The migration that
-- enables it is idempotent.
CREATE EXTENSION IF NOT EXISTS postgis;

ALTER SCHEMA public OWNER TO adaptive_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO adaptive_api;

-- Tables and sequences the owner creates later (the migrations) become usable by the API
-- without any further grant, and only for data manipulation.
ALTER DEFAULT PRIVILEGES FOR ROLE adaptive_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO adaptive_api;
ALTER DEFAULT PRIVILEGES FOR ROLE adaptive_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO adaptive_api;
SQL
