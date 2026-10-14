-- Roll back only the empty PostgreSQL foundation in a dedicated testing database.
DROP TABLE sampe.webhook_logs;
DROP TABLE sampe.lynk_email_locks;
DROP TABLE sampe.settings;
DROP TABLE sampe.entries;
DROP TABLE sampe.kpi_config;
DROP TABLE sampe.login_attempts;
DROP TABLE sampe.lynk_orders;
DROP TABLE sampe.licenses;
DROP TABLE sampe.user_sessions;
DROP TABLE sampe.members;
DROP TABLE sampe.users;
DROP SCHEMA sampe;
