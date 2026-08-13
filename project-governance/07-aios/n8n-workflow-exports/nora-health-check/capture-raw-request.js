/**
 * GH-AIOS / NORA / Health Check -- "Capture Raw Request" Code node.
 *
 * This file is the SINGLE SOURCE for the JavaScript pasted into the n8n
 * Code node. It lives in the repository rather than only inside the
 * workflow export for one reason: code that exists only as a string in
 * exported JSON cannot be tested by anything. Keeping it here is what
 * makes the cross-language parity gate possible at all.
 *
 * WHAT IT DOES
 * Takes the Webhook node's raw body (delivered as base64 binary because
 * the node is configured with `options.rawBody = true`) and the received
 * headers, and emits the flat payload that the next node -- an HTTP
 * Request node -- posts to the application's verification endpoint.
 *
 * WHAT IT DOES NOT DO
 * It does not compute an HMAC, and it holds no secret. On n8n Cloud a
 * Code node cannot read a credential value and `$env` is unavailable,
 * and Founder decision (Gate 1) forbids putting the signing secret into
 * n8n in any form -- `$vars` and workflow JSON included. So the proof is
 * inverted: this node forwards what arrived, and FastAPI, which already
 * holds the secret, performs the comparison. The secret never enters n8n.
 *
 * It also makes no HTTP request. The n8n Code node sandbox has no network
 * access -- fetch/axios/http are unavailable and fail at runtime -- which
 * is why the verification call is a separate HTTP Request node.
 *
 * WHY THE BODY IS NEVER RE-SERIALISED
 * The signature covers a SHA-256 digest of the exact bytes FastAPI
 * transmitted. Parsing the JSON here and stringifying it again would not
 * reliably reproduce those bytes: Python's `json.dumps` escapes non-ASCII
 * to \uXXXX by default, so an Arabic payload produces a completely
 * different digest from JavaScript's `JSON.stringify` -- while every
 * ASCII test still passes. That failure ships silently. The base64 string
 * is therefore passed through untouched, and parsing happens only after
 * the signature has been verified.
 *
 * HEADER CASE
 * n8n normalises header names to lowercase. Looking them up in their
 * mixed-case spelling reads `undefined` and fails every request -- a
 * failure that looks like a signing bug and is not.
 */

const HEADER_KEY_ID = 'x-gh-aios-key-id';
const HEADER_TIMESTAMP = 'x-gh-aios-timestamp';
const HEADER_REQUEST_ID = 'x-gh-request-id';
const HEADER_SIGNATURE = 'x-gh-aios-signature';

const WORKFLOW_IDENTIFIER = 'nora.health_check';

/**
 * Normalise an incoming header map to lowercase keys.
 * @param {Record<string, unknown>} headers
 * @returns {Record<string, string>}
 */
function lowercaseHeaders(headers) {
  const normalised = {};
  for (const [name, value] of Object.entries(headers || {})) {
    normalised[String(name).toLowerCase()] = value === undefined || value === null ? '' : String(value);
  }
  return normalised;
}

/**
 * Extract the exact received body as base64, without re-serialising it.
 *
 * With `rawBody` enabled the Webhook node delivers the body as binary,
 * already base64-encoded, so it is passed straight through. The JSON
 * fallback exists only to fail LOUDLY: if raw-body capture is ever turned
 * off, silently falling back to re-serialising the parsed object would
 * produce a wrong digest and look like a key problem. Refusing is the
 * only safe behaviour.
 *
 * @param {{ binary?: Record<string, { data?: string }>, json?: Record<string, unknown> }} item
 * @returns {string} base64 of the exact received bytes
 */
function rawBodyBase64(item) {
  const binary = item.binary || {};
  const property = binary.data || binary.body;
  if (property && typeof property.data === 'string') {
    return property.data;
  }
  throw new Error(
    'Raw body capture is not enabled on the Webhook node. Enable options.rawBody. ' +
      'Re-serialising the parsed body would produce a different digest and break ' +
      'signature verification.'
  );
}

const item = $input.first();
const headers = lowercaseHeaders(item.json && item.json.headers);

return [
  {
    json: {
      workflow: WORKFLOW_IDENTIFIER,
      key_id: headers[HEADER_KEY_ID] || '',
      timestamp: headers[HEADER_TIMESTAMP] || '',
      request_id: headers[HEADER_REQUEST_ID] || '',
      signature: headers[HEADER_SIGNATURE] || '',
      body_base64: rawBodyBase64(item),
    },
  },
];
