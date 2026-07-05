"""GitHub tool client with public/token modes, retry and structured logging."""
from __future__ import annotations

import hashlib
import json
from typing import Protocol

import httpx

from app.config import GITHUB_CACHE_TTL_SECONDS, GITHUB_RETRY_ATTEMPTS, GITHUB_TOKEN
from app.redis_client import get_redis
from app.schemas.contracts import GitHubRepository, GitHubSearchInput, dump_model
from app.services.observability import ErrorEvent, get_logger, record_error_event, retry_with_backoff
from app.mcp.tool_registry import assert_tool_allowed

PUBLIC_GITHUB_HEADERS = {"Accept": "application/vnd.github+json"}
RAW_GITHUB_HEADERS = {"Accept": "application/vnd.github.raw+json"}
logger = get_logger(__name__)


class GitHubTools(Protocol):
    def search_repositories(self, query: str, limit: int = 3) -> list[dict]: ...
    def read_readme(self, repo: str) -> str: ...


class GitHubMCPClient:
    """Stable GitHub tool adapter used by OpenSource Mentor."""

    def __init__(self, token: str | None = None, agent_name: str = "opensource_mentor"):
        self.token = (token if token is not None else GITHUB_TOKEN).strip()
        self.agent_name = agent_name

    @staticmethod
    def _cache_key(namespace: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"coach:github:{namespace}:{digest}"

    @staticmethod
    def _cache_get_json(key: str):
        client = get_redis()
        if client is None:
            return None
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    @staticmethod
    def _cache_set_json(key: str, value) -> None:
        client = get_redis()
        if client is None:
            return
        try:
            client.setex(key, GITHUB_CACHE_TTL_SECONDS, json.dumps(value, ensure_ascii=False))
        except Exception:
            return

    @property
    def auth_mode(self) -> str:
        return "token" if self.token else "public"

    @property
    def _headers(self) -> dict[str, str]:
        headers = dict(PUBLIC_GITHUB_HEADERS)
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @property
    def _raw_headers(self) -> dict[str, str]:
        headers = dict(RAW_GITHUB_HEADERS)
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _public_headers(raw: bool = False) -> dict[str, str]:
        return dict(RAW_GITHUB_HEADERS if raw else PUBLIC_GITHUB_HEADERS)

    @staticmethod
    def _is_retryable_http_error(exc: Exception) -> bool:
        if isinstance(exc, httpx.RequestError):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {429, 500, 502, 503, 504}
        return False

    @staticmethod
    def _raise_for_retryable_status(response: httpx.Response) -> httpx.Response:
        if response.status_code in {429, 500, 502, 503, 504}:
            response.raise_for_status()
        return response

    def _record_failure(
        self,
        *,
        operation: str,
        exc: Exception | None = None,
        status_code: int | None = None,
        message: str = "",
        metadata: dict | None = None,
    ) -> None:
        record_error_event(ErrorEvent(
            component="github",
            operation=operation,
            error_type=type(exc).__name__ if exc else f"HTTP{status_code}",
            error_message=str(exc) if exc else message,
            retry_count=max(0, GITHUB_RETRY_ATTEMPTS - 1),
            fallback_used=True,
            severity="warning",
            tool=operation,
            metadata={"auth_mode": self.auth_mode, **(metadata or {})},
        ))

    def _get(self, url: str, *, headers: dict[str, str], params: dict | None, operation: str, metadata: dict) -> httpx.Response:
        return retry_with_backoff(
            lambda: self._raise_for_retryable_status(httpx.get(url, headers=headers, params=params, timeout=15)),
            component="github",
            operation_name=operation,
            attempts=GITHUB_RETRY_ATTEMPTS,
            retryable=self._is_retryable_http_error,
            metadata={"auth_mode": self.auth_mode, **metadata},
        )

    def search_repositories(self, query: str, limit: int = 3) -> list[dict]:
        assert_tool_allowed(self.agent_name, "github.search_repositories")
        search_input = GitHubSearchInput.model_validate({"query": query, "limit": limit})
        params = {"q": search_input.query, "sort": "stars", "per_page": search_input.limit}
        cache_key = self._cache_key("search", f"{self.auth_mode}:{search_input.query}:{search_input.limit}")
        cached = self._cache_get_json(cache_key)
        if isinstance(cached, list):
            return cached
        try:
            headers = self._headers
            response = self._get(
                "https://api.github.com/search/repositories",
                headers=headers,
                params=params,
                operation="search_repositories",
                metadata={"query": search_input.query},
            )
            if response.status_code in {401, 403} and "Authorization" in headers:
                record_error_event(ErrorEvent(
                    component="github",
                    operation="search_repositories",
                    error_type=f"HTTP{response.status_code}",
                    error_message="Token access failed, retrying with public GitHub API",
                    fallback_used=True,
                    severity="warning",
                    tool="search_repositories",
                    metadata={"auth_mode": "token", "query": search_input.query},
                ))
                logger.warning("GitHub token search failed, retrying public API")
                response = self._get(
                    "https://api.github.com/search/repositories",
                    headers=self._public_headers(),
                    params=params,
                    operation="search_repositories_public",
                    metadata={"query": search_input.query},
                )
            response.raise_for_status()
            repositories: list[dict] = []
            for item in response.json().get("items", [])[: search_input.limit]:
                repositories.append(dump_model(GitHubRepository.model_validate({
                    "full_name": item.get("full_name") or item.get("name") or "unknown",
                    "html_url": item.get("html_url") or "",
                    "description": item.get("description") or "",
                    "stargazers_count": item.get("stargazers_count") or 0,
                    "language": item.get("language"),
                    "topics": item.get("topics") or [],
                    "updated_at": item.get("updated_at"),
                    "source": "github",
                })))
            self._cache_set_json(cache_key, repositories)
            return repositories
        except httpx.HTTPStatusError as exc:
            self._record_failure(
                operation="search_repositories",
                exc=exc,
                metadata={"query": search_input.query, "status_code": exc.response.status_code},
            )
            logger.warning("GitHub search failed with HTTP status")
        except httpx.RequestError as exc:
            self._record_failure(operation="search_repositories", exc=exc, metadata={"query": search_input.query})
            logger.warning("GitHub search request failed")
        except Exception as exc:
            self._record_failure(operation="search_repositories", exc=exc, metadata={"query": search_input.query})
            logger.warning("GitHub search failed")
        return []

    def read_readme(self, repo: str) -> str:
        assert_tool_allowed(self.agent_name, "github.read_readme")
        cache_key = self._cache_key("readme", f"{self.auth_mode}:{repo}")
        cached = self._cache_get_json(cache_key)
        if isinstance(cached, str):
            return cached
        try:
            headers = self._raw_headers
            response = self._get(
                f"https://api.github.com/repos/{repo}/readme",
                headers=headers,
                params=None,
                operation="read_readme",
                metadata={"repo": repo},
            )
            if response.status_code in {401, 403} and "Authorization" in headers:
                record_error_event(ErrorEvent(
                    component="github",
                    operation="read_readme",
                    error_type=f"HTTP{response.status_code}",
                    error_message="Token README access failed, retrying public API",
                    fallback_used=True,
                    severity="warning",
                    tool="read_readme",
                    metadata={"auth_mode": "token", "repo": repo},
                ))
                logger.warning("GitHub token README access failed, retrying public API")
                response = self._get(
                    f"https://api.github.com/repos/{repo}/readme",
                    headers=self._public_headers(raw=True),
                    params=None,
                    operation="read_readme_public",
                    metadata={"repo": repo},
                )
            response.raise_for_status()
            text = response.text[:12000]
            self._cache_set_json(cache_key, text)
            return text
        except httpx.HTTPStatusError as exc:
            self._record_failure(
                operation="read_readme",
                exc=exc,
                metadata={"repo": repo, "status_code": exc.response.status_code},
            )
            logger.warning("GitHub README read failed with HTTP status")
        except httpx.RequestError as exc:
            self._record_failure(operation="read_readme", exc=exc, metadata={"repo": repo})
            logger.warning("GitHub README read request failed")
        except Exception as exc:
            self._record_failure(operation="read_readme", exc=exc, metadata={"repo": repo})
            logger.warning("GitHub README read failed")
        return ""


__all__ = ["GitHubMCPClient", "GitHubTools"]
