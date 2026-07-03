# Engineering Notes

## Main Reliability Design

- Pydantic contracts define Agent state, LLM outputs, API responses and GitHub tool IO before data enters the workflow state.
- JWT authentication binds sessions to `user_id`; session restore and filesystem fallback both enforce user ownership.
- LLM and GitHub calls use retry with exponential backoff before falling back to deterministic test data.
- Structured `ErrorEvent` logs include component, operation, retry count, fallback usage and severity for later Sentry or webhook integration.
- SSE events expose node progress, final state and completion status for long-running Agent workflows.

## Retry Policy

- Retry: timeout, network error, `429`, `500`, `502`, `503`, `504`.
- Do not retry as transient failures: malformed input, invalid token, permission denied and missing resource.
- Default attempts are controlled by `COACH_LLM_RETRY_ATTEMPTS` and `GITHUB_RETRY_ATTEMPTS`.

## Fallback Policy

- LLM fallback is used for local development, tests and demo continuity.
- GitHub fallback is used only after token mode, public mode or HTTP access cannot return usable data.
- Fallback data is schema-validated before entering Agent state.
