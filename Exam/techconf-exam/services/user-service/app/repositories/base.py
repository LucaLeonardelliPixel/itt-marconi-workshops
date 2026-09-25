"""Abstract repository interface for user-service."""

from __future__ import annotations

from abc import ABC, abstractmethod


class UserRepository(ABC):
    """Abstract base class defining the storage contract for user records.

    All methods receive and return plain ``dict`` objects whose shape matches
    the ``User`` schema defined in the OpenAPI contract.  Concrete adapters
    (``MemoryRepository``, ``JsonRepository``, ``Sqlite3Repository``) must
    implement every method without exposing their internal representation to
    callers.
    """

    @abstractmethod
    def insert(self, user: dict) -> dict:
        """Persist a new user record and return the stored dict.

        Parameters
        ----------
        user:
            A fully-populated ``User`` dict (id, timestamps, etc. already set
            by the service layer before calling this method).

        Returns
        -------
        dict
            The stored user dict, identical to the input.
        """

    @abstractmethod
    def find_by_id(self, id: str) -> dict | None:
        """Return the user dict for the given ``id``, or ``None`` if absent.

        Parameters
        ----------
        id:
            UUID v4 string identifying the user.
        """

    @abstractmethod
    def find_all(self, filters: dict | None = None) -> list[dict]:
        """Return all user dicts, optionally filtered.

        Parameters
        ----------
        filters:
            Optional mapping of field names to expected values.  Supported
            keys are ``role`` and ``email``; both are applied as equality
            checks (logical AND when both are present).  Pass ``None`` or an
            empty dict to return every record.

        Returns
        -------
        list[dict]
            Possibly-empty list of matching user dicts.
        """

    @abstractmethod
    def update(self, id: str, data: dict) -> dict | None:
        """Replace the mutable fields of an existing user record.

        Parameters
        ----------
        id:
            UUID v4 string identifying the user to update.
        data:
            Dict of fields to write.  ``id`` and ``created_at`` are already
            preserved by the service layer; the adapter writes whatever it
            receives.

        Returns
        -------
        dict | None
            The updated user dict, or ``None`` if ``id`` was not found.
        """

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Remove the user with the given ``id`` from storage.

        Parameters
        ----------
        id:
            UUID v4 string identifying the user to remove.

        Returns
        -------
        bool
            ``True`` if the record existed and was removed, ``False`` if no
            record with that ``id`` was found.
        """

    @abstractmethod
    def patch(self, id: str, data: dict) -> dict | None:
        """Merge *data* onto the existing record for *id*.

        Unlike ``update``, which overwrites the whole record, ``patch``
        applies only the keys present in *data*, leaving all other fields
        unchanged.  The service layer guarantees that ``id`` and
        ``created_at`` are never included in *data*.

        Parameters
        ----------
        id:
            UUID v4 string identifying the user to patch.
        data:
            Dict of fields to merge onto the existing record.

        Returns
        -------
        dict | None
            The updated user dict after the merge, or ``None`` if *id* was
            not found.
        """

    @abstractmethod
    def email_exists(self, email: str, exclude_id: str | None = None) -> bool:
        """Check whether a normalised email address is already in use.

        Parameters
        ----------
        email:
            Lowercase-normalised email address to look up.
        exclude_id:
            When performing a uniqueness check for an *update* operation,
            pass the ``id`` of the user being updated so that their own email
            is not treated as a conflict.

        Returns
        -------
        bool
            ``True`` if another user (not ``exclude_id``) owns this email,
            ``False`` otherwise.
        """
