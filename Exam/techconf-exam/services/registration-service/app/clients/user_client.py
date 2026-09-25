"""User-service lookup port and requests adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote

import requests

from app.services.exceptions import DependencyUnavailableError, UpstreamNotFoundError


class UserClient(ABC):
    @abstractmethod
    def get_user(self, user_id: str) -> dict[str, Any]:
        raise NotImplementedError


class HttpUserClient(UserClient):
    def __init__(
        self,
        base_url: str,
        timeout: float = 2.0,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def get_user(self, user_id: str) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/users/{quote(user_id, safe='')}"
        try:
            response = self._session.get(url, timeout=self._timeout)
        except requests.RequestException as exc:
            raise DependencyUnavailableError("user-service") from exc
        if response.status_code == 404:
            raise UpstreamNotFoundError("user-service", user_id)
        if response.status_code != 200:
            raise DependencyUnavailableError(
                "user-service",
                f"user-service returned unexpected status {response.status_code}.",
            )
        try:
            user = response.json()
        except ValueError as exc:
            raise DependencyUnavailableError(
                "user-service", "user-service returned invalid JSON."
            ) from exc
        if not isinstance(user, dict) or not isinstance(user.get("id"), str):
            raise DependencyUnavailableError(
                "user-service", "user-service returned an unusable user response."
            )
        return user
