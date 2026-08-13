# AIOS Foundation — Architecture and Decision Record

| Field | Value |
|---|---|
| Document ID | GH-AIOS-ARCH-001 |
| Status | **Gates 2–5 implemented. Workflow inactive. Awaiting manual review.** |
| Baseline commit | `4cc960e` (Merge PR #11, MVP Slice 4 Evidence Lifecycle) |
| Branch | `feat/aios-nora-health-check` |
| Supersedes | Gate 0 preparation audit §11 (internal authentication) |

---

## 1. Recorded Founder decisions (Gate 1)

These are binding on everything below.

- **n8n is approved as the permanent AIOS orchestration layer.**
- **The official instance is `https://thegreenhubs.app.n8n.cloud`.**
- **Hosting is n8n Cloud.**
- **FastAPI authenticates, authorizes, resolves tenants and controls product actions.**
- **n8n orchestrates but carries no independent product authority.**
- **Direct PostgreSQL/Supabase service-role access from n8n is prohibited.**
- **The account is currently in a trial period, and production continuity beyond
  the trial is not yet confirmed.**

Additional decisions recorded at Gate 1 and applied here: the monorepo holds the
AIOS foundation with records and exports under `project-governance/07-aios/`;
Google Drive is ratified as the shared-folder platform but **no Drive credential,
folder, register or Master Inbox integration may exist until Gate 7**; the Founder
is the production-activation approver and the Level 3 approver; autonomy begins at
Levels 0–2; no OpenAI/OpenRouter credential is required for the Health Check;
development and production use separate credentials and webhook URLs; and no
secret may appear in a workflow export, repository file, prompt, log, document or
execution response.

The n8n project identifier from the browser URL is deliberately **not recorded
here**. It is not required by the application contract.

---

## 2. The boundary

```
User / UI / approved external channel
        ↓
Trusted Green Hubs FastAPI gateway
   authentication · authorization · current-user · trusted organization
        ↓  signed, versioned envelope
n8n Cloud  — orchestration only, no independent authority
        ↓  forwards exactly what it received
Trusted Green Hubs FastAPI gateway  — verifies the signature
```

Trust flows **outward, never inward**. FastAPI establishes identity and
organization from a verified Supabase JWT and the stored profile, then hands n8n
an envelope describing that already-settled fact. Actor fields are *execution
context* for the orchestrator — never an authorization decision it makes.

A client may not supply `user_id`, `organization_id`, `role`, `permission`,
`permissions`, `reviewed_by`, `evidence_status`, `approval_state` or `is_admin`
at any depth of the payload. Sending one is **refused, never stripped**: a silent
strip teaches the caller that sending it was acceptable.

---

## 3. Why n8n Cloud changed the authentication design

The Gate 0 audit described "a dedicated header credential carrying an
HMAC-SHA256 signature". That conflated two unrelated mechanisms and is corrected
here.

**n8n's Webhook `Header Auth` credential is a static shared-secret equality check
on one header value. It is not a signature, it verifies nothing about the request
body, and it must never be described as HMAC verification.**

On n8n Cloud three constraints bind at once:

1. a Code node **cannot read a credential value**, so a credential cannot supply
   an HMAC key;
2. `$env` is unavailable, and Founder decision 12 forbids the secret in `$vars`
   or in exported workflow JSON;
3. the Code node sandbox has **no network access**, so it cannot call out.

The approved design therefore **inverts the direction of proof**:

```
FastAPI  signs the exact outbound body bytes
   ↓
n8n      captures the exact raw bytes + signing headers (Code node)
   ↓
n8n      POSTs them to the FastAPI verification endpoint (HTTP Request node)
   ↓
FastAPI  verifies HMAC, timestamp, key id, body digest and request id
   ↓
n8n      continues only when FastAPI answers valid
```

**The HMAC secret never enters n8n in any form.** That is strictly stronger than
any arrangement in which the orchestrator holds it.

### The verification endpoint is inert by construction

`POST /api/v1/internal/aios/verify-request` performs no product action, touches
no tenant data, writes no database row, dispatches no workflow and returns no
signing material. This is enforced structurally, not by policy: a CI test parses
the AST of every AIOS module and fails the build if any of them imports a
repository, a database session, storage, a model provider or an evidence
command. The service holds one dependency — a key ring — and a clock.

It is unauthenticated by end-user token **by design**: the orchestrator has no
end-user token to present, because it is verifying one of *our* requests rather
than acting for a person. It is protected by what it cannot do, plus a bounded
payload size and a rate limit.

Every verification failure — bad signature, expired timestamp, unknown key id,
unregistered workflow, malformed payload — is answered **identically**:
`{"valid": false, "request_id": null, "category": "signature_invalid"}`.
Distinguishing them would turn the endpoint into an oracle for which key ids
exist.

---

## 4. The signing protocol

```
canonical = key_id     \n
          ‖ timestamp  \n
          ‖ request_id \n
          ‖ workflow   \n
          ‖ sha256_hex(exact request body bytes)

signature = hex(HMAC-SHA256(secret_utf8, canonical_utf8))
```

- Separator is a **single LF byte (0x0A)**. Never CRLF. **No trailing newline.**
- Every component is **UTF-8**.
- Body digest is **lowercase hex SHA-256 of the exact transmitted bytes**.
- Timestamp is `YYYY-MM-DDTHH:MM:SSZ` — UTC, second precision, literal `Z`, no
  fractional seconds, no numeric offset. One accepted spelling only.
- Maximum clock skew **±300 seconds, two-sided**. A future-dated timestamp is
  rejected under the same bound: a one-sided window lets a signer with a fast
  clock mint long-lived signatures.
- Comparison is **constant-time** (`hmac.compare_digest`).
- `correlation_id` is deliberately **not signed** — it is diagnostic, the
  middleware may legitimately replace a malformed inbound value, and binding it
  would cause signature failures with no security benefit. Its transmitted value
  is covered anyway because it also appears inside the signed body.

### Headers

| Header | Format |
|---|---|
| `X-GH-AIOS-Key-Id` | `[a-z0-9-]{1,64}` |
| `X-GH-AIOS-Timestamp` | `YYYY-MM-DDTHH:MM:SSZ` |
| `X-GH-Request-Id` | canonical lowercase hyphenated UUID |
| `X-GH-AIOS-Signature` | `sha256=` + 64 lowercase hex |
| `Content-Type` | `application/json` |

HTTP header names are case-insensitive and **n8n normalises them to lowercase**.
Both sides look up the lowercase form. A verifier written against the mixed-case
spelling reads `undefined` and fails every request — a failure that looks like a
signing bug and is not.

### Never re-serialise

The digest is over the bytes actually transmitted, computed **once**.
`N8NAIOSClient` calls `httpx` with `content=body_bytes`, never `json=payload` —
`json=` re-serialises internally, so the signature would describe different bytes
than were sent.

This is not theoretical. Proved in `test_reserialising_a_parsed_body_changes_the_digest`:

| Serialiser | Bytes | SHA-256 prefix |
|---|---|---|
| Python `json.dumps` (default) | 95 | `ab3a3123…` |
| Python compact, `ensure_ascii=False` | 43 | `e55f015a…` |
| Node `JSON.stringify` | 43 | `e55f015a…` |

Python's default `ensure_ascii=True` escapes non-ASCII to `\uXXXX`. **Every
Arabic character in a payload would break the signature — and every ASCII test
would still pass.** Hence raw-body capture is mandatory on the n8n side
(`options.rawBody = true`) and the reviewed Code node **refuses to run** if it is
disabled rather than falling back to re-serialisation.

### Key ids and rotation

```
gh-aios-<direction>-<env>-<serial>
  direction : f2n (FastAPI→n8n) | n2f (n8n→FastAPI)
  env       : dev | prod
```

The key id encodes direction and environment, so a development key presented to a
production verifier is **absent from that verifier's ring entirely** and fails
structurally. That is what makes Founder decision 11 self-enforcing rather than
procedural.

Rotation is an overlap, never a cutover: add the new key (both verify) → switch
the active id → observe ≥24h → **remove the old key**. A retired key that still
verifies is not retired. Key ids are never reused. An unknown key id is rejected
identically to a bad signature.

---

## 5. Replay protection — recorded limitation

**Timestamp-only replay protection is acceptable *only* for the deterministic,
side-effect-free NORA Health Check.** The justification is narrow and does not
generalise: the workflow reads nothing, writes nothing and calls nothing but the
verification endpoint, so a replayed request produces a byte-identical response
and changes no state anywhere. The entire cost of a successful replay is one
duplicate execution record.

**The moment a workflow can change anything, this justification disappears.**

**Persistent request deduplication is mandatory before any workflow that writes
product state, moves a file, creates a task, sends a message or calls an approval
action.** "Persistent" means: survives workflow and instance restart; enforced by
a unique constraint on `request_id`, not a read-then-write check; claimed
*before* any side effect; retained ≥24 hours.

It is **not built in this foundation** — deliberately, because building a
deduplication store with no mutating workflow to protect would be speculative,
and its shape should be decided against the first real mutation at Gate 8. The
presumptive choice is a FastAPI-owned table, since PostgreSQL already provides
the unique constraint and the transaction, and it keeps the deduplication
authority on the side that already owns every other authority.

---

## 6. Timeouts and retries

Consistent with `OpenAILLMGateway`, so the codebase has one philosophy:

- connect timeout 5 s, total timeout 10 s, both bounded and configurable;
- **at most two attempts**, and only for transport failures and 5xx;
- **no retry on 4xx** — the orchestrator rejecting our request means our
  signature, contract or configuration is wrong, and repeating it cannot help;
- no retry on an invalid signature or invalid contract;
- no infinite loops.

Failures map onto the existing `AppError` envelope: `504` upstream timeout, `502`
upstream unavailable, `502` unexpected upstream response. A caller cannot act
differently on "unreachable" than on "answered incoherently", and distinguishing
them would describe the orchestrator's internal state to a product client.

---

## 7. Registries

| Registry | Content | Enforcement |
|---|---|---|
| Workflow | exactly one: `nora.health_check` | reserved names are **absent**, not present-and-disabled |
| Role | all nine named; **only NORA active** | HAFIDH is `DECLARED_INACTIVE` until Master Inbox is approved |
| Tool | **empty for every role** | no Drive, provider, messaging or database tool exists to grant |

All three are `MappingProxyType` of frozen values — immutable at runtime, so no
code path can widen them after import. Autonomy is capped at Level 2 and asserted
at import time.

Workflow identifiers are **not normalised** (they appear verbatim inside a
signature's canonical string, so a second accepted spelling would mean signing one
and registering another). Role names **are** normalised, exactly as
`resolve_trusted_role` normalises a stored `users.role`. The asymmetry is
deliberate and asserted.

---

## 8. Permission

`Permission.AIOS_INVOKE` (`aios.invoke`) is added to the existing catalogue and
granted to `editor`, `approver`, `admin`, `owner`; denied to `viewer` and to any
unrecognised role.

It is held as its own set, disjoint from `_EVIDENCE_REVIEW_PERMISSIONS`, for the
same reason that set exists: *who may invoke orchestration* is a question **M-4**
owns, and backlog risk **R-1** forbids engineering from answering it alone. Until
M-4 lands this grants exactly what the policy already grants every write-capable
role, and no more.

**Holding `aios.invoke` confers no authority over evidence.** A CI test asserts
that no AIOS module so much as mentions `EVIDENCE_REVIEW` or
`EvidenceReviewService`.

Tests derive allowed and denied roles **from `ROLE_PERMISSIONS` itself**, never
from hardcoded role names, so they follow the policy instead of quietly defining
a second one.

---

## 9. What was deliberately not built

- No Production Error Handler (Gate 6).
- No HAFIDH Master Inbox (Gate 8) — HAFIDH stays inactive.
- No Drive access, credential, folder or register (Gate 7).
- No OpenAI/OpenRouter call — the Health Check is deterministic and calls no
  provider by design.
- No RAG, retrieval, evidence review or answer approval reachable from AIOS.
- No persistent deduplication (§5).
- No database migration and no new runtime dependency: `hmac` and `hashlib` are
  standard library, `httpx` was already present.

---

## 10. Known limitations

**The rate limiter is per process and in memory.** This codebase has no
rate-limiting convention — no middleware, no dependency, no store — so the
smallest correct thing was built rather than pretending otherwise. Two instances
behind a load balancer each enforce the limit independently. It resets on
restart. It is an abuse brake, **not** a deduplication mechanism, and the two
must not be confused.

**The `GH-AIOS` team project does not exist.** The n8n MCP surface available
exposes no project-creation operation, so the workflow was created in the
account's personal project. Moving it is a manual, non-destructive UI step that
changes neither the webhook path nor the workflow id.

**The verification URL is an unset placeholder.** The AIOS deployment URL is a
Gate 10 configuration step; a committed URL would eventually be promoted by
accident.

**End-to-end n8n Cloud connectivity has not been exercised.** See the release
evidence record for exactly what was and was not verified.

**Trial-period continuity is unconfirmed.** Recorded as an operational risk, not
as a reason to purchase or upgrade anything.
