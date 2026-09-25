"""Registration persistence adapters."""

from app.repositories.json_repo import JsonRegistrationRepository
from app.repositories.memory import MemoryRegistrationRepository
from app.repositories.registration_repository import InsertOutcome, RegistrationRepository
from app.repositories.sqlite_repo import SqliteRegistrationRepository

__all__ = [
    "RegistrationRepository",
    "InsertOutcome",
    "MemoryRegistrationRepository",
    "JsonRegistrationRepository",
    "SqliteRegistrationRepository",
]
