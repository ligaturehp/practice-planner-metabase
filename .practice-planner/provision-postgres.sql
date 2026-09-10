\set ON_ERROR_STOP on
\getenv reader_password ANALYTICS_READER_PASSWORD
\getenv writer_password ANALYTICS_WRITER_PASSWORD
\getenv metabase_password METABASE_APP_PASSWORD

SELECT 'CREATE ROLE analytics_reader LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_reader') \gexec
SELECT 'CREATE ROLE analytics_writer LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_writer') \gexec
SELECT 'CREATE ROLE metabase_app LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'metabase_app') \gexec

SELECT format('ALTER ROLE analytics_reader PASSWORD %L', :'reader_password') \gexec
SELECT format('ALTER ROLE analytics_writer PASSWORD %L', :'writer_password') \gexec
SELECT format('ALTER ROLE metabase_app PASSWORD %L', :'metabase_password') \gexec

SELECT 'CREATE DATABASE metabase_app OWNER metabase_app'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'metabase_app') \gexec

REVOKE ALL ON DATABASE analytics FROM PUBLIC;
REVOKE ALL ON DATABASE metabase_app FROM PUBLIC;
GRANT CONNECT ON DATABASE analytics TO analytics_reader, analytics_writer;

\connect analytics
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA analytics TO analytics_reader, analytics_writer;
GRANT INSERT ON analytics.events TO analytics_writer;
GRANT SELECT ON analytics.daily_accounts, analytics.daily_logins,
 analytics.daily_usage, analytics.daily_day_plans,
 analytics.daily_request_outcomes, analytics.raw_interactions TO analytics_reader;
ALTER ROLE analytics_reader SET default_transaction_read_only = on;
ALTER ROLE analytics_reader SET statement_timeout = '15s';
