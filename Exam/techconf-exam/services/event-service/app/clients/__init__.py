"""Outbound service ports and adapters."""

from app.clients.http_user_repository import HttpUserRepository
from app.clients.user_repository import UserRepository

__all__ = ["UserRepository", "HttpUserRepository"]
