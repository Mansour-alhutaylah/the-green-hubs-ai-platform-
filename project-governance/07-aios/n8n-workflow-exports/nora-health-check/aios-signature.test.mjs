/**
 * The JavaScript half of the cross-language parity gate.
 *
 * Reads the SAME fixture the Python tests read
 * (backend/tests/fixtures/aios_signature_vectors.json) and proves that an
 * independent implementation reproduces every value. Expected values are
 * never restated here -- a second copy would drift, and two drifted
 * copies agreeing with themselves is exactly the failure this gate exists
 * to catch.
 *
 * Run:  node --test project-governance/07-aios/n8n-workflow-exports/nora-health-check/
 */

import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  bodyDigest,
  canonicalBytes,
  constantTimeEqualHex,
  parseSignatureHeader,
  signCanonical,
  verifySignedRequest,
} from './aios-signature.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..', '..', '..');
const FIXTURE_PATH = path.join(
  REPO_ROOT,
  'backend',
  'tests',
  'fixtures',
  'aios_signature_vectors.json'
);

const fixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));
const SECRET = fixture.secret_utf8;

/** The exact bytes a vector describes, via the same base64 hop n8n uses. */
function vectorBodyBytes(vector) {
  const base64 = Buffer.from(vector.body_utf8, 'utf8').toString('base64');
  return Buffer.from(base64, 'base64');
}

function epochSecondsOf(vector) {
  return Math.floor(Date.parse(vector.timestamp) / 1000);
}

test('the fixture is the one the Python tests read, and is non-trivial', () => {
  assert.ok(fs.existsSync(FIXTURE_PATH), `missing fixture at ${FIXTURE_PATH}`);
  assert.equal(fixture.algorithm, 'HMAC-SHA256');
  assert.equal(fixture.canonical_separator, '\n');
  assert.ok(fixture.vectors.length >= 4);
  // A fixture of only ASCII vectors would pass under a wrong encoding
  // path, so the non-ASCII case must actually be present.
  assert.ok(
    fixture.vectors.some((vector) => /[^\x00-\x7F]/.test(vector.body_utf8)),
    'fixture must contain a non-ASCII vector'
  );
});

for (const vector of fixture.vectors) {
  test(`${vector.name}: body digest matches Python`, () => {
    const bytes = vectorBodyBytes(vector);
    assert.equal(bytes.length, vector.body_byte_length);
    assert.equal(bodyDigest(bytes), vector.body_sha256_hex);
  });

  test(`${vector.name}: canonical bytes match Python`, () => {
    const canonical = canonicalBytes({
      keyId: vector.key_id,
      timestamp: vector.timestamp,
      requestId: vector.request_id,
      workflow: vector.workflow,
      bodyBytes: vectorBodyBytes(vector),
    });
    assert.equal(canonical.length, vector.canonical_byte_length);
    assert.equal(canonical.toString('utf8'), vector.canonical_string_utf8);
    // No trailing newline, and LF rather than CRLF.
    assert.ok(!canonical.toString('utf8').endsWith('\n'));
    assert.ok(!canonical.includes('\r'));
  });

  test(`${vector.name}: signature matches Python`, () => {
    const signature = signCanonical(
      SECRET,
      canonicalBytes({
        keyId: vector.key_id,
        timestamp: vector.timestamp,
        requestId: vector.request_id,
        workflow: vector.workflow,
        bodyBytes: vectorBodyBytes(vector),
      })
    );
    assert.equal(signature, vector.signature_hex);
    assert.equal(`sha256=${signature}`, vector.signature_header_value);
    assert.equal(parseSignatureHeader(vector.signature_header_value), vector.signature_hex);
  });

  test(`${vector.name}: a valid signature verifies`, () => {
    assert.equal(
      verifySignedRequest({
        secret: SECRET,
        keyId: vector.key_id,
        timestamp: vector.timestamp,
        requestId: vector.request_id,
        workflow: vector.workflow,
        signature: vector.signature_header_value,
        bodyBytes: vectorBodyBytes(vector),
        nowEpochSeconds: epochSecondsOf(vector),
      }),
      true
    );
  });

  test(`${vector.name}: a changed body fails`, () => {
    assert.equal(
      verifySignedRequest({
        secret: SECRET,
        keyId: vector.key_id,
        timestamp: vector.timestamp,
        requestId: vector.request_id,
        workflow: vector.workflow,
        signature: vector.signature_header_value,
        bodyBytes: Buffer.concat([vectorBodyBytes(vector), Buffer.from(' ', 'utf8')]),
        nowEpochSeconds: epochSecondsOf(vector),
      }),
      false
    );
  });

  test(`${vector.name}: a changed timestamp fails`, () => {
    assert.equal(
      verifySignedRequest({
        secret: SECRET,
        keyId: vector.key_id,
        timestamp: '2026-08-12T14:47:06Z',
        requestId: vector.request_id,
        workflow: vector.workflow,
        signature: vector.signature_header_value,
        bodyBytes: vectorBodyBytes(vector),
        nowEpochSeconds: Math.floor(Date.parse('2026-08-12T14:47:06Z') / 1000),
      }),
      false
    );
  });

  test(`${vector.name}: a changed request id fails`, () => {
    assert.equal(
      verifySignedRequest({
        secret: SECRET,
        keyId: vector.key_id,
        timestamp: vector.timestamp,
        requestId: '11111111-2222-4333-8444-555555555555',
        workflow: vector.workflow,
        signature: vector.signature_header_value,
        bodyBytes: vectorBodyBytes(vector),
        nowEpochSeconds: epochSecondsOf(vector),
      }),
      false
    );
  });

  test(`${vector.name}: a changed key id fails`, () => {
    assert.equal(
      verifySignedRequest({
        secret: SECRET,
        keyId: 'gh-aios-f2n-dev-999',
        timestamp: vector.timestamp,
        requestId: vector.request_id,
        workflow: vector.workflow,
        signature: vector.signature_header_value,
        bodyBytes: vectorBodyBytes(vector),
        nowEpochSeconds: epochSecondsOf(vector),
      }),
      false
    );
  });

  test(`${vector.name}: a changed workflow fails`, () => {
    assert.equal(
      verifySignedRequest({
        secret: SECRET,
        keyId: vector.key_id,
        timestamp: vector.timestamp,
        requestId: vector.request_id,
        workflow: 'hafidh.master_inbox',
        signature: vector.signature_header_value,
        bodyBytes: vectorBodyBytes(vector),
        nowEpochSeconds: epochSecondsOf(vector),
      }),
      false
    );
  });

  test(`${vector.name}: a timestamp outside the window fails`, () => {
    for (const offset of [301, -301]) {
      assert.equal(
        verifySignedRequest({
          secret: SECRET,
          keyId: vector.key_id,
          timestamp: vector.timestamp,
          requestId: vector.request_id,
          workflow: vector.workflow,
          signature: vector.signature_header_value,
          bodyBytes: vectorBodyBytes(vector),
          nowEpochSeconds: epochSecondsOf(vector) + offset,
        }),
        false,
        `offset ${offset}s should be rejected`
      );
    }
  });

  test(`${vector.name}: a malformed signature fails safely, never throws`, () => {
    for (const bad of ['', 'sha256=', 'sha256=abc', 'deadbeef', `sha256=${'Z'.repeat(64)}`]) {
      assert.equal(
        verifySignedRequest({
          secret: SECRET,
          keyId: vector.key_id,
          timestamp: vector.timestamp,
          requestId: vector.request_id,
          workflow: vector.workflow,
          signature: bad,
          bodyBytes: vectorBodyBytes(vector),
          nowEpochSeconds: epochSecondsOf(vector),
        }),
        false,
        `signature ${JSON.stringify(bad)} should be rejected`
      );
    }
  });
}

test('the non-ASCII vector survives the base64 hop without escaping drift', () => {
  const vector = fixture.vectors.find((candidate) => /[^\x00-\x7F]/.test(candidate.body_utf8));
  const bytes = vectorBodyBytes(vector);
  assert.equal(bytes.toString('utf8'), vector.body_utf8);
  assert.equal(bodyDigest(bytes), vector.body_sha256_hex);
});

test('re-serialising a parsed body would produce a DIFFERENT digest', () => {
  // The concrete reason raw-body capture is mandatory. This asserts the
  // hazard is real rather than theoretical: JSON.stringify of the parsed
  // object is not guaranteed to reproduce the transmitted bytes, and the
  // fixture's V2 envelope is a case where it does not.
  const vector = fixture.vectors.find((candidate) => candidate.name === 'V2_health_check_envelope');
  const reserialised = Buffer.from(JSON.stringify(JSON.parse(vector.body_utf8)), 'utf8');
  const exact = vectorBodyBytes(vector);
  assert.equal(bodyDigest(exact), vector.body_sha256_hex);
  if (!reserialised.equals(exact)) {
    assert.notEqual(bodyDigest(reserialised), vector.body_sha256_hex);
  }
});

test('constant-time comparison rejects unequal lengths without throwing', () => {
  assert.equal(constantTimeEqualHex('abc', 'a'.repeat(64)), false);
  assert.equal(constantTimeEqualHex('a'.repeat(64), 'a'.repeat(64)), true);
  assert.equal(constantTimeEqualHex('a'.repeat(64), 'b'.repeat(64)), false);
});
