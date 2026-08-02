# Phase 1A Slice 1 Test Database Safety

Evidence IDs: **EV-TEST-DB-01**, **EV-TEST-DB-02**, **EV-CI-01**

Verification date: 2026-08-02 (Asia/Riyadh)

## Isolated architecture

| Property | Verified value |
| --- | --- |
| Compose file | `docker-compose.test.yml` only |
| Service/container | `test-postgres` / `green-hubs-slice1-test-postgres` |
| Image tag | `pgvector/pgvector:pg16` |
| Immutable digest | `sha256:a36250871de0833b8757561c72f2477ef1ddd1101afa4e617fb552e0de514c6b` |
| Database | `green_hubs_test` |
| Port | `127.0.0.1:55432 -> 5432` |
| Health | `healthy` via `pg_isready` |
| Volume | `green-hubs-slice1-test-db-data`, labelled disposable-test |
| Network | `green-hubs-slice1-test-network`, labelled disposable-test |
| Marker table | `public.gh_disposable_test_database` |
| Marker value | `GH_SIP_DISPOSABLE_TEST_DB_DO_NOT_CREATE_ELSEWHERE` |
| PostgreSQL | 16.14 |
| pgvector available/installed | 0.8.6 / 0.8.6 |
| Alembic head | `da0298a9c722` |

No API container is present. The Compose file has no `env_file` entry and never loads `backend/.env`. Credentials are synthetic and local/CI-only. The port binds to loopback only. The image uses both a non-`latest` tag and an immutable digest.

## Layered target validation

Before any application import or database connection, the guard requires all of the following:

1. `GH_INTEGRATION_TEST_MODE` explicitly enabled.
2. `GH_TEST_DATABASE_URL` present; ordinary `DATABASE_URL` is not accepted as the source.
3. `ENVIRONMENT=test`; production and staging aliases are rejected.
4. Exact `postgresql+asyncpg` scheme.
5. Database name ending in `_test`.
6. Host not matching Supabase, pooler, RDS, Neon, Azure, Render, Railway, PlanetScale, or another listed shared-provider pattern.
7. Local host by default; a remote host requires both an explicit enable flag and exact allowlist membership.
8. Connected database identity matches the guarded name.
9. Marker table contains the exact disposable marker.
10. Alembic head equals `da0298a9c722` before integration execution.
11. pgvector is installed.
12. Expected application tables exist.

Guard errors do not include the URL, username, password, query parameters, or tokens. A direct negative command confirmed a missing URL fails before collection. Unit tests cover every required rejection and redaction case.

## Migration and schema proof

All eight existing Alembic revisions applied without modification:

```text
eeb31636c877
12c7b2051fc6
693e23cf7797
73688728b480
81a7fdde2d19
233e7656bf79
3f3acc7fc556
da0298a9c722
```

Verified public tables were:

```text
ai_analysis_results, alembic_version, analysis_runs,
analysis_source_references, document_chunk_embeddings, document_chunks,
documents, engagements, extracted_text, gh_disposable_test_database,
organizations, users
```

The functional proof created a temporary `vector(1536)` table, inserted a synthetic nonzero vector, and evaluated the pgvector cosine-distance operator. No historical migration was edited.

## External-service containment

- The 15 historical integration modules were inspected before execution.
- JWKS fetches, Supabase Storage, embedding providers, and LLM gateways are replaced by local fakes in API integration tests.
- The official runner removes Supabase credential variables, Storage configuration, `OPENAI_API_KEY`, and `OPENROUTER_API_KEY` from the pytest subprocess.
- It supplies only a loopback URL (`127.0.0.1:9`) where app construction requires an issuer. An accidental request cannot reach a shared provider.
- No Supabase database or Storage endpoint was contacted.
- No OpenAI or OpenRouter request was made.
- Test rows used synthetic identifiers/content only.

## CI gate

The separate `backend-integration` job starts the same digest-pinned pgvector service with synthetic CI credentials, waits for Docker health, bootstraps and verifies the marker, applies migrations, verifies Alembic and pgvector, collects the suite through the guarded runner, then runs it through the same fail-closed outcome check. Existing backend and frontend jobs were not changed.

Hosted CI was not started at evidence creation because the branch was not yet pushed; no hosted success is claimed here.

## Teardown and rollback

Disposable teardown, from the repository root:

```powershell
docker compose -f docker-compose.test.yml down -v
```

This removes only the Slice 1 container, network, and named disposable volume. The pinned image and unrelated Docker resources remain.

Code rollback after delivery should use normal revert commits, not reset or force-push:

```powershell
git revert 090ae91bb4dda50dc558a69cf1e09d4396daa844
git revert 42ba0197d7cfa939a387c8200d74386c8d0b2707
```

The evidence commit can be reverted separately after its final hash is known.
