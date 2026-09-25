"""UserService — stub (business logic implemented in Tasks 6–11).

This module will contain the full UserService class once the repository
interface (Task 2) and concrete adapters (Tasks 3–5) are in place.
"""

from __future__ import annotations

from app.repositories.base import UserRepository


class UserService:
    """Orchestrates all user-service business logic.

    Depends only on the UserRepository interface — never on a concrete adapter.
    """

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    # Methods implemented in Tasks 6–11:
    #   create(data)            -> dict
    #   list(filters, page, page_size) -> dict
    #   get(id)                 -> dict
    #   replace(id, data)       -> dict
    #   update(id, data)        -> dict
    #   delete(id)              -> None
