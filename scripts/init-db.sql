-- TRACE PostgreSQL setup (run as postgres superuser)
-- psql -U postgres -f scripts/init-db.sql

CREATE USER trace WITH PASSWORD 'trace';
CREATE DATABASE trace OWNER trace;
GRANT ALL PRIVILEGES ON DATABASE trace TO trace;
