CREATE TABLE IF NOT EXISTS gh_disposable_test_database (
    marker text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO gh_disposable_test_database (marker)
VALUES ('GH_SIP_DISPOSABLE_TEST_DB_DO_NOT_CREATE_ELSEWHERE')
ON CONFLICT (marker) DO NOTHING;

COMMENT ON TABLE gh_disposable_test_database IS
    'Disposable local/CI integration-test marker, never create through Alembic';
