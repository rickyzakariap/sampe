DO $$ BEGIN
    RAISE EXCEPTION 'Google identity links must not be deleted by rollback; disable direct login instead';
END $$;
