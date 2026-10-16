-- Owner Report is scoped to the existing license-backed tenant.
CREATE TABLE sampe.owner_report_links (
    tenant_id text PRIMARY KEY REFERENCES sampe.licenses(id) ON DELETE CASCADE,
    slug text NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    token_seed bytea NOT NULL CHECK (octet_length(token_seed) = 32),
    link_hash char(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    rotated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sampe.owner_report_rate_limits (
    bucket char(64) PRIMARY KEY,
    hits integer NOT NULL DEFAULT 0 CHECK (hits >= 0),
    window_started_at timestamptz NOT NULL DEFAULT now()
);
