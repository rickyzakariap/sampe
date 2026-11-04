CREATE TABLE sampe.google_identities (
    google_sub text PRIMARY KEY,
    user_id text NOT NULL UNIQUE REFERENCES sampe.members(user_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sampe.google_login_challenges (
    nonce_hash text PRIMARY KEY,
    expires_at timestamptz NOT NULL
);
