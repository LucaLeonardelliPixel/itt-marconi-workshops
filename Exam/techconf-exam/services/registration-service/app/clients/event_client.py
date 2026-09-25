"""Event-service lookup port and requests adapter."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote

import requests

from app.services.exceptions import DependencyUnavailableError, UpstreamNotFoundError


class EventClient(ABC):
    @abstractmethod
    def get_event(self, event_id: str) -> dict[str, Any]:
        raise NotImplementedError


class HttpEventClient(EventClient):
    def __init__(
        self,
        base_url: str,
        timeout: float = 2.0,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def get_event(self, event_id: str) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/events/{quote(event_id, safe='')}"
        try:
            response = self._session.get(url, timeout=self._timeout)
        except requests.RequestException as exc:
            raise DependencyUnavailableError("event-service") from exc
        if response.status_code == 404:
            raise UpstreamNotFoundError("event-service", event_id)
        if response.status_code != 200:
            raise DependencyUnavailableError(
                "event-service",
                f"event-service returned unexpected status {response.status_code}.",
            )
        try:
            event = response.json()
        except ValueError as exc:
            raise DependencyUnavailableError(
                "event-service", "event-service returned invalid JSON."
            ) from exc
        if not self._usable_event(event):
            raise DependencyUnavailableError(
                "event-service", "event-service returned an unusable event response."
            )
        return event

    @staticmethod
    def _usable_event(event: Any) -> bool:
        if not isinstance(event, dict):
            return False
        capacity = event.get("capacity")
        price = event.get("price")
        return (
            isinstance(event.get("id"), str)
            and isinstance(event.get("status"), str)
            and isinstance(capacity, int)
            and not isinstance(capacity, bool)
            and capacity >= 1
            and isinstance(price, (int, float))
            and not isinstance(price, bool)
            and math.isfinite(price)
            and price >= 0
        )
