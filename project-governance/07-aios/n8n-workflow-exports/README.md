# n8n Workflow Exports — Export, Review, Promotion

Reviewed exports of every GH-AIOS workflow. This directory is the only
durable record of what the orchestrator runs: n8n's editor lets a live workflow
change without touching this repository, so an export that drifts from the
instance is the first symptom of an unreviewed edit.

## What is here

```
nora-health-check/
├── workflow.json            reviewed export — no secret, no credential
├── capture-raw-request.js   the reviewed Code-node source, pasted into n8n
├── aios-signature.mjs       reviewed JS reference implementation of the protocol
├── aios-signature.test.mjs  the JavaScript half of the cross-language parity gate
└── README.md                this file
```

The Code-node JavaScript lives here as a **repository source file**, not only as
a string inside `workflow.json`. Code that exists only inside an export cannot be
tested by anything — keeping it here is what makes the parity gate possible.

## Controls that run in CI

`backend/tests/api/test_aios_workflow_export.py` scans every `*.json` in this
directory and fails the build if it finds:

- a Postgres, Supabase, MySQL, MongoDB or Redis node
- a Google Drive, Sheets, OneDrive or SharePoint node
- an email, Telegram, Slack, Twilio or WhatsApp node
- an Execute Command, SSH, FTP or file read/write node
- an OpenAI, chat-model, embeddings, vector-store or agent node
- any credential reference on any node
- a database connection string, service-role key, API key, JWT or private key
- the published signing test literal
- `createHmac`, `crypto.`, `$vars.` or `$env.` — the signing secret must never
  enter n8n
- an external URL outside the allow-list
- `"active": true`

It additionally asserts that the webhook still captures the raw body, that the
webhook path is versioned, and that the path matches
`app.domain.aios.workflows.NORA_HEALTH_CHECK`'s registered `webhook_path`. A
drift between those two is a 404 in production.

## Current state

| | |
|---|---|
| Workflow | `GH-AIOS / NORA / Health Check` |
| Instance | `https://thegreenhubs.app.n8n.cloud` (n8n Cloud) |
| Workflow id | `bo6U1KIJyNKjQzex` |
| Project | Personal project — **see "Project" below** |
| Active | **No.** `active: false`, `activeVersionId: null`, `triggerCount: 0` |
| Credentials | None on any node |
| Autonomy | Level 0 — read only, no mutation, no external action |

### Project

The target project is `GH-AIOS`. It does **not exist yet**, and the n8n MCP
surface available to this session exposes no project-creation operation — only
`search_projects`. The workflow was therefore created in the account's personal
project.

Moving it is a manual, non-destructive step in the n8n UI: create the team
project `GH-AIOS`, then move the workflow into it. Doing so does not change the
webhook path or the workflow id, so nothing in this repository needs to change.

### Verification endpoint URL

`Request FastAPI Verification` carries an **unset placeholder**, not a
configured URL:

```
<__PLACEHOLDER_VALUE__FastAPI internal verification endpoint, e.g. https://your-api-host/api/v1/internal/aios/verify-request__>
```

This is deliberate. The AIOS deployment URL is a Gate 10 configuration step, and
a committed URL would eventually be promoted by accident. The CI scan asserts the
placeholder is still there.

## Export procedure

1. Make the change in n8n. **Never** in this repository first — the instance is
   where a workflow actually runs, and a hand-edited export that was never
   imported is a fiction.
2. Export the workflow to JSON.
3. Strip anything the instance adds that is not part of the definition: ids,
   `versionId`, `webhookId`, timestamps, `meta`, `pinData`, `staticData`.
4. Confirm by eye that no credential value, URL or secret survived.
5. Replace the file here and review the result **as a diff**. A diff is what makes
   an added node visible; a wholesale replacement is not.
6. Run the controls:
   ```
   cd backend && python -m pytest tests/api/test_aios_workflow_export.py -q
   node --test project-governance/07-aios/n8n-workflow-exports/nora-health-check/aios-signature.test.mjs
   ```

## Promotion

Development and production use **separate credentials and separate webhook
URLs** (Founder decision, Gate 1). Native n8n environment support is not assumed
and is not used.

```
develop in dev  ->  export + review as a diff  ->  import to production inactive
                ->  run acceptance tests       ->  Founder approves activation
```

Production activation is the Founder's decision at **Gate 10** and is not
authorized. Nothing in this directory may be activated by anyone else.

## Rollback

In order of speed:

1. **Deactivate** the workflow in n8n. FastAPI returns a safe `502` immediately.
2. **Disable** at the gateway: set `AIOS_ENABLED=false`. The route answers `503`
   without attempting a dispatch.
3. **Revoke** both signing keys. Nothing else depends on them.
4. **Revert** the FastAPI commit. The AIOS surface is purely additive — no
   migration, no data to unwind.
