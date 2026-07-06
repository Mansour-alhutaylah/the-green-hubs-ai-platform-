"""Authentication/security infrastructure.

Placeholder for Sprint 1 -- no auth logic is implemented yet.

Planned migration from Hemaya's ``backend/auth.py``: bcrypt password
hashing, JWT creation/verification (python-jose), and crypto-secure OTP
generation/hashing -- these algorithms are sound and reviewed as reusable.

NOT carried over: Hemaya's hardcoded fallback ``SECRET_KEY`` literal used
when the environment variable was missing. In this project, a missing
secret must fail fast (via ``app.core.config.Settings``) rather than
silently default to a known value.
"""
