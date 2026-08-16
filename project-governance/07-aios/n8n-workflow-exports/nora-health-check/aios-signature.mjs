/**
 * Reviewed JavaScript reference implementation of the AIOS signing protocol.
 *
 * WHAT THIS IS FOR
 * The deployed NORA Health Check workflow does NOT sign or verify in
 * JavaScript -- on n8n Cloud the secret never enters n8n, and FastAPI
 * performs the comparison (see capture-raw-request.js). So why does this
 * file exist?
 *
 * Because a protocol implemented in exactly one language is a protocol
 * whose rules cannot be distinguished from one implementation's quirks.
 * Running the same fixture through an independent implementation is what
 * proves the canonical form is genuinely language-neutral -- that the LF
 * separator, the UTF-8 encoding, the lowercase hex digest and the
 * no-trailing-newline rule are the specification, not accidents of
 * Python's `hashlib` and `json` defaults.
 *
 * It is also the implementation a self-hosted deployment would use if the
 * hosting model ever changed and in-node verification became possible.
 * Proving it now costs one test run; discovering a mismatch later, from a
 * production signature failure, costs considerably more.
 *
 * NORMATIVE SPEC
 *   project-governance/07-aios/AIOS_Internal_Signing_Protocol.md
 * SHARED FIXTURE (the only source of expected values)
 *   backend/tests/fixtures/aios_signature_vectors.json
 */

import crypto from 'node:crypto';

export const CANONICAL_SEPARATOR = '\n';
export const SIGNATURE_PREFIX = 'sha256=';
export const DIGEST_HEX_LENGTH = 64;
export const DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300;

export const HEADER_KEY_ID = 'x-gh-aios-key-id';
export const HEADER_TIMESTAMP = 'x-gh-aios-timestamp';
export const HEADER_REQUEST_ID = 'x-gh-request-id';
export const HEADER_SIGNATURE = 'x-gh-aios-signature';

const TIMESTAMP_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HEX_PATTERN = /^[0-9a-f]+$/;

/**
 * Lowercase hex SHA-256 of the exact body bytes.
 *
 * Takes a Buffer, never a parsed object. An empty body is not a special
 * case -- it digests to the SHA-256 of zero bytes like anything else.
 *
 * @param {Buffer} bodyBytes
 * @returns {string}
 */
export function bodyDigest(bodyBytes) {
  if (!Buffer.isBuffer(bodyBytes)) {
    throw new TypeError('bodyDigest requires a Buffer of the exact received bytes');
  }
  return crypto.createHash('sha256').update(bodyBytes).digest('hex');
}

/**
 * Build the exact bytes that are signed: five LF-separated UTF-8 fields,
 * no trailing newline.
 *
 * @param {{ keyId: string, timestamp: string, requestId: string, workflow: string, bodyBytes: Buffer }} parts
 * @returns {Buffer}
 */
export function canonicalBytes({ keyId, timestamp, requestId, workflow, bodyBytes }) {
  const canonical = [keyId, timestamp, requestId, workflow, bodyDigest(bodyBytes)].join(
    CANONICAL_SEPARATOR
  );
  return Buffer.from(canonical, 'utf8');
}

/**
 * Lowercase hex HMAC-SHA256 over the canonical bytes.
 *
 * @param {string} secret
 * @param {Buffer} canonical
 * @returns {string}
 */
export function signCanonical(secret, canonical) {
  return crypto
    .createHmac('sha256', Buffer.from(secret, 'utf8'))
    .update(canonical)
    .digest('hex');
}

/**
 * Constant-time comparison of two hex digests.
 *
 * `crypto.timingSafeEqual` THROWS on a length mismatch rather than
 * returning false, so the length is checked first. Since both operands
 * are fixed 64-character hex, that check leaks nothing. A plain `===`
 * would short-circuit on the first differing character and leak the
 * expected signature byte by byte.
 *
 * @param {string} a
 * @param {string} b
 * @returns {boolean}
 */
export function constantTimeEqualHex(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const bufferA = Buffer.from(a, 'utf8');
  const bufferB = Buffer.from(b, 'utf8');
  if (bufferA.length !== bufferB.length) return false;
  return crypto.timingSafeEqual(bufferA, bufferB);
}

/**
 * Strip and validate the `sha256=<hex>` signature header value.
 *
 * @param {string} headerValue
 * @returns {string} the bare hex digest
 */
export function parseSignatureHeader(headerValue) {
  if (typeof headerValue !== 'string' || !headerValue.startsWith(SIGNATURE_PREFIX)) {
    throw new Error('signature header is malformed');
  }
  const candidate = headerValue.slice(SIGNATURE_PREFIX.length);
  if (candidate.length !== DIGEST_HEX_LENGTH) {
    throw new Error('signature has the wrong length');
  }
  if (!HEX_PATTERN.test(candidate)) {
    throw new Error('signature is not lowercase hex');
  }
  return candidate;
}

/**
 * Verify a signed request. Returns false for every failure rather than
 * distinguishing them -- an external caller learns only valid/invalid.
 *
 * @param {{ secret: string, keyId: string, timestamp: string, requestId: string, workflow: string, signature: string, bodyBytes: Buffer, nowEpochSeconds: number, maxClockSkewSeconds?: number }} input
 * @returns {boolean}
 */
export function verifySignedRequest({
  secret,
  keyId,
  timestamp,
  requestId,
  workflow,
  signature,
  bodyBytes,
  nowEpochSeconds,
  maxClockSkewSeconds = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
}) {
  let provided;
  try {
    provided = parseSignatureHeader(signature);
  } catch {
    return false;
  }

  if (!TIMESTAMP_PATTERN.test(timestamp)) return false;
  if (!UUID_PATTERN.test(requestId)) return false;

  const signedAt = Math.floor(Date.parse(timestamp) / 1000);
  if (!Number.isFinite(signedAt)) return false;
  // Two-sided: a future-dated timestamp is rejected under the same bound,
  // so a signer with a fast clock cannot mint long-lived signatures.
  if (Math.abs(nowEpochSeconds - signedAt) > maxClockSkewSeconds) return false;

  const expected = signCanonical(
    secret,
    canonicalBytes({ keyId, timestamp, requestId, workflow, bodyBytes })
  );
  return constantTimeEqualHex(expected, provided);
}
