/**
 * Typed error hierarchy for the API client. Every class carries only the
 * backend's own `detail` message (or a client-generated safe message) —
 * never a raw response body, provider error, or token.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor(message: string) {
    super(401, message);
    this.name = 'UnauthorizedError';
  }
}

export class ForbiddenError extends ApiError {
  constructor(message: string) {
    super(403, message);
    this.name = 'ForbiddenError';
  }
}

export class NotFoundApiError extends ApiError {
  constructor(message: string) {
    super(404, message);
    this.name = 'NotFoundApiError';
  }
}

export class ConflictError extends ApiError {
  constructor(message: string) {
    super(409, message);
    this.name = 'ConflictError';
  }
}

export class ValidationApiError extends ApiError {
  constructor(message: string) {
    super(422, message);
    this.name = 'ValidationApiError';
  }
}

/** Any transport-level failure (offline, DNS, CORS, timeout) — distinct
 * from a well-formed backend error response. */
export class NetworkError extends Error {
  constructor(message = 'Unable to reach the server. Check your connection and try again.') {
    super(message);
    this.name = 'NetworkError';
  }
}

/** The caller aborted the request (unmount/route change/logout) — never
 * surfaced as a user-facing failure. */
export class RequestAbortedError extends Error {
  constructor() {
    super('Request was cancelled.');
    this.name = 'RequestAbortedError';
  }
}

const GENERIC_MESSAGES: Record<number, string> = {
  400: 'The request could not be processed.',
  401: 'Your session is no longer valid. Sign in again.',
  403: "You don't have permission to do this.",
  404: 'The requested item could not be found.',
  409: 'This action conflicts with the current state.',
  422: 'Some of the submitted information is not valid.',
  500: 'Something went wrong on our end. Try again.',
};

/** Backend's `AppError` envelope is always `{"detail": "<message>"}`
 * (see backend/app/core/exceptions.py), but FastAPI's own built-in request
 * validation (triggered before any of our code runs, e.g. a malformed
 * multipart field) uses `{"detail": [{"msg": "...", ...}, ...]}` instead —
 * this normalizes both into one safe, human-readable string, never
 * exposing raw internals. */
function extractDetailMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) => (entry && typeof entry === 'object' && 'msg' in entry ? String((entry as { msg: unknown }).msg) : null))
        .filter((msg): msg is string => Boolean(msg));
      if (messages.length > 0) return messages.join(' ');
    }
  }
  return GENERIC_MESSAGES[status] ?? `Request failed with status ${status}.`;
}

export function buildApiErrorFromResponse(status: number, body: unknown): ApiError {
  const message = extractDetailMessage(body, status);
  switch (status) {
    case 401:
      return new UnauthorizedError(message);
    case 403:
      return new ForbiddenError(message);
    case 404:
      return new NotFoundApiError(message);
    case 409:
      return new ConflictError(message);
    case 422:
      return new ValidationApiError(message);
    default:
      return new ApiError(status, message);
  }
}
