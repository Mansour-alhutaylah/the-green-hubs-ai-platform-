# Phase 1A Slice 2 Request Context Design

Evidence ID: **EV-ARC-CTX-01**

Branch: `feat/fnd-phase1a-correlation-request-context`

Starting commit: `3e54a87b0ba295adb5e0109faafc6b12c30a46b3`

## Architecture

The effective HTTP stack is:

1. Starlette `ServerErrorMiddleware`.
2. `RequestContextMiddleware` (pure ASGI).
3. `CORSMiddleware`.
4. `UnexpectedErrorMiddleware` (pure ASGI).
5. FastAPI exception middleware, routing, and dependencies.

The new outer user middleware creates one immutable, slotted `RequestContext`
for every HTTP scope. It stores the same logical object in a `ContextVar` and
the ASGI scope state exposed as `request.state.request_context`. Non-HTTP scopes
pass through unchanged.

The middleware accepts exactly one canonical UUID in `X-Correlation-ID` and
normalizes it to lowercase. Missing, duplicate, malformed, oversized,
non-ASCII, whitespace-containing, or control-character-containing values are
discarded without logging and replaced by UUID4. On response start, any
existing correlation header is removed and exactly one trusted value is added.

The `ContextVar` and scope-state tokens are reset in `finally`, after the safe
completion event is emitted. This preserves the enriched context through
awaited calls and logging while preventing reuse by a later request.

## Trusted enrichment

`get_current_user` is the sole enrichment point. It first receives a subject
UUID from the verified server-side token dependency, resolves the application
profile through `IUserRepository`, and only after a profile exists calls
`enrich_request_context(user_id=user.id,
organization_id=user.organization_id)`. The immutable object is replaced in
both the `ContextVar` and request state. The update API does not accept a
correlation ID.

No client header, query parameter, or body field participates in enrichment.
A profile without an organization remains `organization_id=None`. Context
values do not alter authentication, authorization, tenant isolation, or
service inputs.

## Logging and privacy

The standard-library log-record factory adds formatter-safe
`correlation_id`, `user_id`, and `organization_id` fields. Outside a request or
for absent identity fields, the value is `-`. The installation is idempotent
and preserves the prior record factory.

The completion event includes only method, safe path without query string,
status code, duration, and the context fields. It does not inspect or log
headers, cookies, query strings, request/response bodies, credentials, keys,
or document contents. Unexpected-error records are created while the same
context is active, so their correlation ID matches the response and completion
event.

## CORS and exception compatibility

`X-Correlation-ID` is the only addition to `expose_headers`; allowed origins,
credentials, methods, and request headers are unchanged. Registering the
correlation middleware after CORS makes it the outer user wrapper while
preserving Slice 1's `CORS -> UnexpectedErrorMiddleware` order. This allows
sanitized 500 responses to retain CORS and correlation headers. Controlled
`AppError`, FastAPI validation, authentication, authorization, and not-found
responses keep their existing status and payload contracts.

## Scope limitations

This is an observability and future audit foundation. It is not an
authorization decision, permanent audit record, distributed tracing system,
permission system, or audit-event implementation.
