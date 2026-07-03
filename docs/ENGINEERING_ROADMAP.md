# Engineering Roadmap

This document tracks the path from engineering prototype to production-grade project.

## Phase 1: Repository Hygiene

Status: started

- Keep local secrets, databases, caches, build outputs, and logs out of the repository.
- Use `.env.example` as the only committed environment template.
- Keep README and user-facing text encoded as UTF-8.
- Keep Docker build contexts small with `.dockerignore`.

## Phase 2: Reproducible Development

Status: started

- Use `pyproject.toml` for Python version, test, lint, and formatting configuration.
- Use `requirements-dev.txt` for local development dependencies.
- Use `check.ps1` as the local quality gate.
- Add CI to run backend tests, ruff, and frontend build on every pull request.

## Phase 3: Security Baseline

Status: started

- Require non-default `SECRET_KEY` and `REFRESH_SECRET_KEY` in production.
- Require a non-SQLite `DATABASE_URL` in production.
- Avoid exposing long-lived access tokens in URLs.
- Add login and register rate limiting.
- Return generic production errors to users and keep detailed errors in logs only.

## Phase 4: Database Operations

Status: started

- Alembic has been introduced.
- An initial migration has been generated from the current SQLAlchemy models.
- Schema upgrades have been moved out of application startup.
- Add rollback and migration verification instructions.

## Phase 5: Production Deployment

Status: started

- Build the frontend into a static nginx image.
- Avoid runtime dependency installation in production containers.
- Add health checks for backend, frontend, Redis, and database dependencies.
- Run containers as non-root users where possible.

## Phase 6: Observability

Status: pending

- Add request IDs.
- Add structured access logs.
- Export traces and metrics with OpenTelemetry or an equivalent stack.
- Send critical exceptions to Sentry or an equivalent alerting service.

## Phase 7: Product Hardening

Status: pending

- Add API integration tests for auth, session ownership, SSE, quiz submission, and interview submission.
- Add frontend component or e2e tests for the main learning flow.
- Add cost and latency tracking for LLM and GitHub calls.
- Define data retention and user data deletion policies.
