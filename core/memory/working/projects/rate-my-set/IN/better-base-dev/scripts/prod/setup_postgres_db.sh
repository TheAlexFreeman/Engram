sudo -u postgres psql

# Within `psql`

# * DevOps_Server_Setup_TODO: Fill in password and uncomment.
-- CREATE ROLE better_base_backend WITH LOGIN PASSWORD '<TODO_FILL_IN__SECRET__DB_BACKEND_USER>';
-- ALTER ROLE better_base_backend SET client_encoding TO 'utf8';
-- ALTER ROLE better_base_backend SET default_transaction_isolation TO 'read committed';
-- ALTER ROLE better_base_backend SET timezone TO 'UTC';

# * DevOps_Server_Setup_TODO: Fill in password and uncomment.
-- CREATE ROLE better_base_external WITH LOGIN PASSWORD '<TODO_FILL_IN__SECRET__DB_EXTERNAL_USER>';
-- ALTER ROLE better_base_external SET client_encoding TO 'utf8';
-- ALTER ROLE better_base_external SET default_transaction_isolation TO 'read committed';
-- ALTER ROLE better_base_external SET timezone TO 'UTC';

CREATE DATABASE better_base_prod OWNER better_base_backend;

\c better_base_prod

GRANT ALL PRIVILEGES ON DATABASE better_base_prod TO better_base_backend;
GRANT ALL PRIVILEGES ON DATABASE better_base_prod TO better_base_external;

GRANT ALL ON SCHEMA public TO better_base_backend;
GRANT ALL ON SCHEMA public TO better_base_external;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO better_base_backend;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO better_base_external;

GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO better_base_backend;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO better_base_external;

GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO better_base_backend;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO better_base_external;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO better_base_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO better_base_external;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO better_base_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO better_base_external;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO better_base_backend;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO better_base_external;
