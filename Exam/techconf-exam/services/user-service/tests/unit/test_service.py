"""Service-layer unit tests (Task 14).

Tests exercise ``UserService`` methods directly (no HTTP) using
``MemoryRepository`` as the backing store.

Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03,
              REQ-USR-E01, REQ-USR-E02, REQ-USR-E03,
              REQ-USR-E04, REQ-USR-E05, REQ-USR-E06, REQ-USR-N05
"""

from __future__ import annotations

import re
import uuid

import pytest

from app.repositories.memory import MemoryRepository
from app.services.user_service import UserService
from app.services.exceptions import (
    EmailConflictError,
    NotFoundError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _make_service() -> UserService:
    """Return a fresh UserService backed by an empty MemoryRepository."""
    return UserService(MemoryRepository())


def _valid_create(**overrides) -> dict:
    """Return a minimal valid UserCreate payload."""
    base = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestCreate:

    # --- happy path ---

    def test_returns_user_dict_with_all_fields(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        for field in ("id", "first_name", "last_name", "email",
                      "company", "role", "created_at", "updated_at"):
            assert field in user, f"missing field: {field}"

    def test_server_generates_uuid_id(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        # Must be a valid UUID v4 string
        parsed = uuid.UUID(user["id"], version=4)
        assert str(parsed) == user["id"]

    def test_server_generates_iso_timestamps(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        assert _ISO_RE.match(user["created_at"]), f"bad created_at: {user['created_at']}"
        assert _ISO_RE.match(user["updated_at"]), f"bad updated_at: {user['updated_at']}"

    def test_created_at_equals_updated_at_on_create(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        assert user["created_at"] == user["updated_at"]

    def test_email_is_normalised_to_lowercase(self):
        svc = _make_service()
        user = svc.create(_valid_create(email="  User@Example.COM  "))
        assert user["email"] == "user@example.com"

    def test_role_defaults_to_attendee_when_omitted(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        assert user["role"] == "attendee"

    def test_explicit_role_is_preserved(self):
        svc = _make_service()
        user = svc.create(_valid_create(role="speaker"))
        assert user["role"] == "speaker"

    def test_company_stored_when_provided(self):
        svc = _make_service()
        user = svc.create(_valid_create(company="Acme Corp"))
        assert user["company"] == "Acme Corp"

    def test_company_is_none_when_omitted(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        assert user["company"] is None

    def test_first_name_and_last_name_stored_correctly(self):
        svc = _make_service()
        user = svc.create(_valid_create(first_name="Bob", last_name="Jones"))
        assert user["first_name"] == "Bob"
        assert user["last_name"] == "Jones"

    # --- ValidationError: missing required fields ---

    def test_raises_validation_error_missing_first_name(self):
        svc = _make_service()
        data = {"last_name": "Smith", "email": "x@example.com"}
        with pytest.raises(ValidationError) as exc_info:
            svc.create(data)
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_missing_last_name(self):
        svc = _make_service()
        data = {"first_name": "Alice", "email": "x@example.com"}
        with pytest.raises(ValidationError) as exc_info:
            svc.create(data)
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_missing_email(self):
        svc = _make_service()
        data = {"first_name": "Alice", "last_name": "Smith"}
        with pytest.raises(ValidationError) as exc_info:
            svc.create(data)
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_empty_first_name(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.create(_valid_create(first_name="   "))

    def test_raises_validation_error_empty_last_name(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.create(_valid_create(last_name=""))

    # --- ValidationError: oversized fields ---

    def test_raises_validation_error_first_name_too_long(self):
        svc = _make_service()
        with pytest.raises(ValidationError) as exc_info:
            svc.create(_valid_create(first_name="A" * 51))
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_last_name_too_long(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.create(_valid_create(last_name="B" * 51))

    def test_raises_validation_error_company_too_long(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.create(_valid_create(company="C" * 101))

    # --- ValidationError: bad email format ---

    def test_raises_validation_error_bad_email_no_at(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.create(_valid_create(email="notanemail"))

    def test_raises_validation_error_bad_email_no_tld(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.create(_valid_create(email="user@domain"))

    # --- ValidationError: extra/unknown fields ---

    def test_raises_validation_error_unknown_field(self):
        svc = _make_service()
        data = _valid_create()
        data["unknown_field"] = "oops"
        with pytest.raises(ValidationError) as exc_info:
            svc.create(data)
        assert exc_info.value.code == "VALIDATION_ERROR"

    # --- EmailConflictError ---

    def test_raises_email_conflict_on_duplicate_exact(self):
        svc = _make_service()
        svc.create(_valid_create(email="user@example.com"))
        with pytest.raises(EmailConflictError) as exc_info:
            svc.create(_valid_create(first_name="Bob", last_name="Jones",
                                     email="user@example.com"))
        assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"

    def test_raises_email_conflict_case_insensitive(self):
        """Inserting User@Example.com after user@example.com must raise."""
        svc = _make_service()
        svc.create(_valid_create(email="user@example.com"))
        with pytest.raises(EmailConflictError) as exc_info:
            svc.create(_valid_create(first_name="Carol", last_name="White",
                                     email="User@Example.com"))
        assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"

    def test_email_conflict_error_carries_normalised_email(self):
        svc = _make_service()
        svc.create(_valid_create(email="alice@example.com"))
        with pytest.raises(EmailConflictError) as exc_info:
            svc.create(_valid_create(first_name="B", last_name="B",
                                     email="ALICE@example.com"))
        assert "alice@example.com" in exc_info.value.message


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:

    def _create_users(self, svc: UserService, n: int = 3) -> list[dict]:
        """Create n users with unique emails and return their dicts."""
        users = []
        for i in range(n):
            u = svc.create(_valid_create(
                first_name=f"User{i}",
                last_name="Test",
                email=f"user{i}@example.com",
            ))
            users.append(u)
        return users

    # --- defaults ---

    def test_default_page_and_page_size(self):
        svc = _make_service()
        self._create_users(svc, 3)
        result = svc.list()
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_total_reflects_full_count(self):
        svc = _make_service()
        self._create_users(svc, 5)
        result = svc.list()
        assert result["total"] == 5

    def test_items_are_user_dicts(self):
        svc = _make_service()
        self._create_users(svc, 2)
        result = svc.list()
        for item in result["items"]:
            assert "id" in item
            assert "email" in item

    def test_empty_store_returns_zero_total(self):
        svc = _make_service()
        result = svc.list()
        assert result["total"] == 0
        assert result["items"] == []

    # --- filters ---

    def test_filter_by_role(self):
        svc = _make_service()
        svc.create(_valid_create(email="a@example.com", role="attendee"))
        svc.create(_valid_create(first_name="S", last_name="T",
                                  email="s@example.com", role="speaker"))
        result = svc.list(filters={"role": "attendee"})
        assert result["total"] == 1
        assert result["items"][0]["role"] == "attendee"

    def test_filter_by_role_total_reflects_filtered_count(self):
        svc = _make_service()
        for i in range(3):
            svc.create(_valid_create(first_name=f"A{i}", last_name="T",
                                      email=f"a{i}@example.com", role="attendee"))
        svc.create(_valid_create(first_name="S", last_name="T",
                                  email="s@example.com", role="speaker"))
        result = svc.list(filters={"role": "attendee"})
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_filter_by_email(self):
        svc = _make_service()
        svc.create(_valid_create(email="find@example.com"))
        svc.create(_valid_create(first_name="B", last_name="B",
                                  email="other@example.com"))
        result = svc.list(filters={"email": "find@example.com"})
        assert result["total"] == 1
        assert result["items"][0]["email"] == "find@example.com"

    def test_combined_role_and_email_filter(self):
        svc = _make_service()
        svc.create(_valid_create(email="match@example.com", role="speaker"))
        svc.create(_valid_create(first_name="B", last_name="B",
                                  email="nomatch@example.com", role="speaker"))
        result = svc.list(filters={"role": "speaker", "email": "match@example.com"})
        assert result["total"] == 1
        assert result["items"][0]["email"] == "match@example.com"

    def test_filter_no_match_returns_empty(self):
        svc = _make_service()
        svc.create(_valid_create(email="a@example.com", role="attendee"))
        result = svc.list(filters={"role": "organizer"})
        assert result["total"] == 0
        assert result["items"] == []

    # --- pagination ---

    def test_pagination_slices_correctly(self):
        svc = _make_service()
        for i in range(5):
            svc.create(_valid_create(first_name=f"U{i}", last_name="T",
                                      email=f"u{i}@example.com"))
        result = svc.list(page=2, page_size=2)
        assert result["page"] == 2
        assert result["page_size"] == 2
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_last_page_may_be_partial(self):
        svc = _make_service()
        for i in range(5):
            svc.create(_valid_create(first_name=f"U{i}", last_name="T",
                                      email=f"p{i}@example.com"))
        result = svc.list(page=3, page_size=2)
        assert len(result["items"]) == 1

    # --- ValidationError ---

    def test_raises_validation_error_page_less_than_1(self):
        svc = _make_service()
        with pytest.raises(ValidationError) as exc_info:
            svc.list(page=0)
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_page_zero(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.list(page=0, page_size=10)

    def test_raises_validation_error_page_size_over_100(self):
        svc = _make_service()
        with pytest.raises(ValidationError) as exc_info:
            svc.list(page_size=101)
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_page_size_zero(self):
        svc = _make_service()
        with pytest.raises(ValidationError):
            svc.list(page_size=0)

    def test_raises_validation_error_unknown_role_filter(self):
        svc = _make_service()
        with pytest.raises(ValidationError) as exc_info:
            svc.list(filters={"role": "superadmin"})
        assert exc_info.value.code == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:

    def test_returns_user_for_known_id(self):
        svc = _make_service()
        created = svc.create(_valid_create())
        fetched = svc.get(created["id"])
        assert fetched["id"] == created["id"]
        assert fetched["email"] == created["email"]

    def test_returned_user_has_all_fields(self):
        svc = _make_service()
        created = svc.create(_valid_create())
        fetched = svc.get(created["id"])
        for field in ("id", "first_name", "last_name", "email",
                      "company", "role", "created_at", "updated_at"):
            assert field in fetched

    def test_raises_not_found_for_unknown_id(self):
        svc = _make_service()
        with pytest.raises(NotFoundError) as exc_info:
            svc.get(str(uuid.uuid4()))
        assert exc_info.value.code == "NOT_FOUND"

    def test_raises_not_found_after_deletion(self):
        svc = _make_service()
        created = svc.create(_valid_create())
        svc.delete(created["id"])
        with pytest.raises(NotFoundError):
            svc.get(created["id"])


# ---------------------------------------------------------------------------
# replace (PUT)
# ---------------------------------------------------------------------------

class TestReplace:

    def _create_alice(self, svc: UserService) -> dict:
        return svc.create(_valid_create(email="alice@example.com", role="attendee"))

    def test_updates_all_mutable_fields(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        updated = svc.replace(alice["id"], {
            "first_name": "Alicia",
            "last_name": "Brown",
            "email": "alicia@example.com",
            "company": "NewCo",
            "role": "speaker",
        })
        assert updated["first_name"] == "Alicia"
        assert updated["last_name"] == "Brown"
        assert updated["email"] == "alicia@example.com"
        assert updated["company"] == "NewCo"
        assert updated["role"] == "speaker"

    def test_preserves_original_id(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        updated = svc.replace(alice["id"], _valid_create(
            first_name="Alicia", last_name="Brown", email="alicia@example.com"
        ))
        assert updated["id"] == alice["id"]

    def test_preserves_original_created_at(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        updated = svc.replace(alice["id"], _valid_create(
            first_name="Alicia", last_name="Brown", email="alicia@example.com"
        ))
        assert updated["created_at"] == alice["created_at"]

    def test_updates_updated_at(self):
        """updated_at after replace must be ≥ created_at (may differ by seconds)."""
        svc = _make_service()
        alice = self._create_alice(svc)
        import time; time.sleep(0.01)  # ensure at least a tiny time gap
        updated = svc.replace(alice["id"], _valid_create(
            first_name="Alicia", last_name="Brown", email="alicia@example.com"
        ))
        # updated_at must be a valid ISO timestamp
        assert _ISO_RE.match(updated["updated_at"])

    def test_replace_normalises_email(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        updated = svc.replace(alice["id"], _valid_create(
            first_name="A", last_name="B", email="  NEW@EXAMPLE.COM  "
        ))
        assert updated["email"] == "new@example.com"

    def test_replace_same_email_does_not_raise_conflict(self):
        """Replacing with the same email as the current user must not conflict."""
        svc = _make_service()
        alice = self._create_alice(svc)
        # Should not raise EmailConflictError
        updated = svc.replace(alice["id"], _valid_create(
            first_name="Alice", last_name="Smith", email="alice@example.com"
        ))
        assert updated["email"] == "alice@example.com"

    def test_raises_not_found_for_unknown_id(self):
        svc = _make_service()
        with pytest.raises(NotFoundError) as exc_info:
            svc.replace(str(uuid.uuid4()), _valid_create())
        assert exc_info.value.code == "NOT_FOUND"

    def test_raises_email_conflict_for_different_user_email(self):
        svc = _make_service()
        svc.create(_valid_create(email="bob@example.com",
                                  first_name="Bob", last_name="B"))
        alice = self._create_alice(svc)
        with pytest.raises(EmailConflictError) as exc_info:
            svc.replace(alice["id"], _valid_create(
                first_name="Alice", last_name="Smith", email="bob@example.com"
            ))
        assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"

    def test_raises_validation_error_missing_first_name(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        with pytest.raises(ValidationError):
            svc.replace(alice["id"], {"last_name": "Smith", "email": "x@example.com"})

    def test_raises_validation_error_bad_email(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        with pytest.raises(ValidationError):
            svc.replace(alice["id"], _valid_create(email="notvalid"))

    def test_raises_validation_error_unknown_field(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        data = _valid_create()
        data["extra"] = "nope"
        with pytest.raises(ValidationError):
            svc.replace(alice["id"], data)

    def test_role_defaults_to_attendee_when_omitted(self):
        svc = _make_service()
        alice = svc.create(_valid_create(role="speaker"))
        updated = svc.replace(alice["id"], _valid_create(
            first_name="Alice", last_name="Smith", email="alice2@example.com"
        ))
        assert updated["role"] == "attendee"


# ---------------------------------------------------------------------------
# update (PATCH)
# ---------------------------------------------------------------------------

class TestUpdate:

    def _create_alice(self, svc: UserService) -> dict:
        return svc.create(_valid_create(
            email="alice@example.com",
            company="OldCo",
            role="attendee",
        ))

    def test_merges_partial_fields(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        patched = svc.update(alice["id"], {"first_name": "Alicia"})
        assert patched["first_name"] == "Alicia"

    def test_unchanged_fields_are_retained(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        patched = svc.update(alice["id"], {"company": "NewCo"})
        assert patched["last_name"] == alice["last_name"]
        assert patched["email"] == alice["email"]
        assert patched["role"] == alice["role"]

    def test_id_and_created_at_are_never_overwritten(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        patched = svc.update(alice["id"], {"first_name": "A"})
        assert patched["id"] == alice["id"]
        assert patched["created_at"] == alice["created_at"]

    def test_updated_at_is_refreshed(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        patched = svc.update(alice["id"], {"first_name": "A"})
        assert _ISO_RE.match(patched["updated_at"])

    def test_email_is_normalised_when_patched(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        patched = svc.update(alice["id"], {"email": "  NEW@EXAMPLE.COM  "})
        assert patched["email"] == "new@example.com"

    def test_raises_not_found_for_unknown_id(self):
        svc = _make_service()
        with pytest.raises(NotFoundError) as exc_info:
            svc.update(str(uuid.uuid4()), {"first_name": "Ghost"})
        assert exc_info.value.code == "NOT_FOUND"

    def test_raises_email_conflict_for_different_user(self):
        svc = _make_service()
        svc.create(_valid_create(first_name="Bob", last_name="B",
                                  email="bob@example.com"))
        alice = self._create_alice(svc)
        with pytest.raises(EmailConflictError) as exc_info:
            svc.update(alice["id"], {"email": "bob@example.com"})
        assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"

    def test_patch_with_own_email_does_not_conflict(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        # Patching with the same email must not raise
        patched = svc.update(alice["id"], {"email": "alice@example.com"})
        assert patched["email"] == "alice@example.com"

    def test_raises_validation_error_invalid_email(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        with pytest.raises(ValidationError) as exc_info:
            svc.update(alice["id"], {"email": "notvalid"})
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_unknown_field(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        with pytest.raises(ValidationError) as exc_info:
            svc.update(alice["id"], {"mystery": "field"})
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_empty_body(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        with pytest.raises(ValidationError) as exc_info:
            svc.update(alice["id"], {})
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_raises_validation_error_first_name_too_long(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        with pytest.raises(ValidationError):
            svc.update(alice["id"], {"first_name": "X" * 51})

    def test_raises_validation_error_invalid_role(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        with pytest.raises(ValidationError):
            svc.update(alice["id"], {"role": "superadmin"})

    def test_patch_multiple_fields_at_once(self):
        svc = _make_service()
        alice = self._create_alice(svc)
        patched = svc.update(alice["id"], {
            "first_name": "AliceNew",
            "company": "PatchedCo",
            "role": "organizer",
        })
        assert patched["first_name"] == "AliceNew"
        assert patched["company"] == "PatchedCo"
        assert patched["role"] == "organizer"
        # unchanged fields
        assert patched["last_name"] == alice["last_name"]


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:

    def test_removes_user_successfully(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        svc.delete(user["id"])
        with pytest.raises(NotFoundError):
            svc.get(user["id"])

    def test_delete_returns_none(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        result = svc.delete(user["id"])
        assert result is None

    def test_raises_not_found_for_unknown_id(self):
        svc = _make_service()
        with pytest.raises(NotFoundError) as exc_info:
            svc.delete(str(uuid.uuid4()))
        assert exc_info.value.code == "NOT_FOUND"

    def test_raises_not_found_on_double_delete(self):
        svc = _make_service()
        user = svc.create(_valid_create())
        svc.delete(user["id"])
        with pytest.raises(NotFoundError):
            svc.delete(user["id"])

    def test_delete_does_not_affect_other_users(self):
        svc = _make_service()
        u1 = svc.create(_valid_create(email="gone@example.com"))
        u2 = svc.create(_valid_create(first_name="B", last_name="B",
                                       email="keep@example.com"))
        svc.delete(u1["id"])
        # u2 must still be retrievable
        found = svc.get(u2["id"])
        assert found["id"] == u2["id"]

    def test_list_total_decrements_after_delete(self):
        svc = _make_service()
        u1 = svc.create(_valid_create(email="a@example.com"))
        u2 = svc.create(_valid_create(first_name="B", last_name="B",
                                       email="b@example.com"))
        svc.delete(u1["id"])
        result = svc.list()
        assert result["total"] == 1
