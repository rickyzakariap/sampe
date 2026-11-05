CREATE TABLE sampe.ai_analyses (
    tenant_id text NOT NULL REFERENCES sampe.licenses(id) ON DELETE CASCADE,
    month text NOT NULL CHECK (month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    scope text NOT NULL DEFAULT 'overall' CHECK (scope = 'overall'),
    source_hash char(64) NOT NULL,
    analysis text NOT NULL,
    reds jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(reds) = 'array'),
    model text NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, month, scope)
);
