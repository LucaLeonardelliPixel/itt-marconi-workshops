"""Repository-layer unit tests (Task 13).

All tests are parameterised over all three storage adapters via the
``backend_repo`` fixture defined in ``conftest.py``.  Every test therefore
runs three times — once for ``MemoryRepository``, once for
``JsonRepository``, and once for ``Sqlite3Repository`` — verifying that
each adapter satisfies the ``UserRepository`` contract identically.

Requirements: REQ-USR-N02, REQ-USR-N03, REQ-USR-N05
"""

from __future__ import annotations

import uuid
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(**overrides) -> dict:
    """Return a fully-populated user dict suitable for passing to ``insert``."""
    now = datetime.utcnow().isoformat() + "Z"
    base = {
        "id": str(uuid.uuid4()),
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        "company": "Acme",
        "role": "attendee",
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------

class TestInsert:
    def test_returns_stored_user(self, backend_repo):
        """insert returns a dict equal to the one passed in."""
        user = _make_user()
        result = backend_repo.insert(user)
        assert result == user

    def test_stored_record_is_retrievable(self, backend_repo):
        """A record inserted can be found by its id."""
        user = _make_user()
        backend_repo.insert(user)
        found = backend_repo.find_by_id(user["id"])
        assert found == user

    def test_returns_copy_not_same_object(self, backend_repo):
        """Mutating the returned dict must not corrupt the store."""
        user = _make_user()
        result = backend_repo.insert(user)
        result["first_name"] = "Tampered"
        found = backend_repo.find_by_id(user["id"])
        assert found["first_name"] == user["first_name"]

    def test_multiple_inserts_are_independent(self, backend_repo):
        """Two users can be inserted and both are retrievable."""
        u1 = _make_user(id=str(uuid.uuid4()), email="u1@example.com")
        u2 = _make_user(id=str(uuid.uuid4()), email="u2@example.com")
        backend_repo.insert(u1)
        backend_repo.insert(u2)
        assert backend_repo.find_by_id(u1["id"]) == u1
        assert backend_repo.find_by_id(u2["id"]) == u2

    def test_nullable_company_stored_as_none(self, backend_repo):
        """``company`` may be ``None``; the adapter must preserve that."""
        user = _make_user(company=None)
        backend_repo.insert(user)
        found = backend_repo.find_by_id(user["id"])
        assert found["company"] is None


# ---------------------------------------------------------------------------
# find_by_id
# ---------------------------------------------------------------------------

class TestFindById:
    def test_returns_correct_user(self, backend_repo):
        """find_by_id returns the user matching the given id."""
        user = _make_user()
        backend_repo.insert(user)
        found = backend_repo.find_by_id(user["id"])
        assert found["id"] == user["id"]
        assert found["email"] == user["email"]

    def test_returns_none_for_unknown_id(self, backend_repo):
        """find_by_id returns None when no record matches."""
        result = backend_repo.find_by_id(str(uuid.uuid4()))
        assert result is None

    def test_does_not_return_wrong_user(self, backend_repo):
        """find_by_id with id A does not return user B."""
        u1 = _make_user(id=str(uuid.uuid4()), email="u1@example.com")
        u2 = _make_user(id=str(uuid.uuid4()), email="u2@example.com")
        backend_repo.insert(u1)
        backend_repo.insert(u2)
        assert backend_repo.find_by_id(u1["id"])["email"] == "u1@example.com"
        assert backend_repo.find_by_id(u2["id"])["email"] == "u2@example.com"

    def test_returns_copy_not_same_reference(self, backend_repo):
        """Mutating the returned dict must not corrupt the stored record."""
        user = _make_user()
        backend_repo.insert(user)
        found = backend_repo.find_by_id(user["id"])
        found["first_name"] = "Tampered"
        refound = backend_repo.find_by_id(user["id"])
        assert refound["first_name"] == user["first_name"]


# ---------------------------------------------------------------------------
# find_all
# ---------------------------------------------------------------------------

class TestFindAll:
    def test_empty_store_returns_empty_list(self, backend_repo):
        """find_all on an empty store returns []."""
        assert backend_repo.find_all() == []

    def test_returns_all_users(self, backend_repo):
        """find_all returns every inserted record when no filter is applied."""
        ids = set()
        for i in range(3):
            u = _make_user(id=str(uuid.uuid4()), email=f"user{i}@example.com")
            backend_repo.insert(u)
            ids.add(u["id"])
        results = backend_repo.find_all()
        assert {r["id"] for r in results} == ids

    def test_none_filter_returns_all(self, backend_repo):
        """Passing None as filters returns all records."""
        for i in range(2):
            backend_repo.insert(_make_user(id=str(uuid.uuid4()), email=f"u{i}@x.com"))
        assert len(backend_repo.find_all(None)) == 2

    def test_empty_dict_filter_returns_all(self, backend_repo):
        """Passing {} as filters returns all records."""
        for i in range(2):
            backend_repo.insert(_make_user(id=str(uuid.uuid4()), email=f"u{i}@y.com"))
        assert len(backend_repo.find_all({})) == 2

    def test_filter_by_role(self, backend_repo):
        """find_all with role filter returns only matching records."""
        attendee = _make_user(id=str(uuid.uuid4()), email="a@example.com", role="attendee")
        speaker = _make_user(id=str(uuid.uuid4()), email="s@example.com", role="speaker")
        organizer = _make_user(id=str(uuid.uuid4()), email="o@example.com", role="organizer")
        for u in (attendee, speaker, organizer):
            backend_repo.insert(u)

        attendees = backend_repo.find_all({"role": "attendee"})
        assert all(u["role"] == "attendee" for u in attendees)
        assert len(attendees) == 1

        speakers = backend_repo.find_all({"role": "speaker"})
        assert len(speakers) == 1
        assert speakers[0]["id"] == speaker["id"]

    def test_filter_by_email(self, backend_repo):
        """find_all with email filter returns only the matching record."""
        u1 = _make_user(id=str(uuid.uuid4()), email="target@example.com")
        u2 = _make_user(id=str(uuid.uuid4()), email="other@example.com")
        backend_repo.insert(u1)
        backend_repo.insert(u2)

        results = backend_repo.find_all({"email": "target@example.com"})
        assert len(results) == 1
        assert results[0]["id"] == u1["id"]

    def test_filter_by_role_and_email(self, backend_repo):
        """Combined role + email filter applies logical AND."""
        target = _make_user(id=str(uuid.uuid4()), email="t@example.com", role="speaker")
        same_email_diff_role = _make_user(id=str(uuid.uuid4()), email="t@example.com", role="attendee")
        # Normally email must be unique; we insert only target here and check
        # the combined filter doesn't widen the results.
        backend_repo.insert(target)
        results = backend_repo.find_all({"role": "speaker", "email": "t@example.com"})
        assert len(results) == 1
        assert results[0]["id"] == target["id"]

    def test_filter_by_role_no_match_returns_empty(self, backend_repo):
        """A role filter with no matching records returns []."""
        backend_repo.insert(_make_user(id=str(uuid.uuid4()), email="a@x.com", role="attendee"))
        assert backend_repo.find_all({"role": "organizer"}) == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_replaces_mutable_fields(self, backend_repo):
        """update overwrites the stored record with the supplied data."""
        user = _make_user()
        backend_repo.insert(user)
        now2 = datetime.utcnow().isoformat() + "Z"
        updated_data = {**user, "first_name": "Bob", "email": "bob@example.com", "updated_at": now2}
        result = backend_repo.update(user["id"], updated_data)
        assert result is not None
        assert result["first_name"] == "Bob"
        assert result["email"] == "bob@example.com"

    def test_preserves_id(self, backend_repo):
        """update must not change the id of the record."""
        user = _make_user()
        backend_repo.insert(user)
        updated_data = {**user, "first_name": "Charlie"}
        result = backend_repo.update(user["id"], updated_data)
        assert result["id"] == user["id"]

    def test_preserves_created_at(self, backend_repo):
        """update must not change created_at."""
        user = _make_user()
        backend_repo.insert(user)
        original_created_at = user["created_at"]
        now2 = datetime.utcnow().isoformat() + "Z"
        updated_data = {**user, "first_name": "Dave", "updated_at": now2}
        result = backend_repo.update(user["id"], updated_data)
        assert result["created_at"] == original_created_at

    def test_returns_updated_record(self, backend_repo):
        """update returns the new state of the record."""
        user = _make_user()
        backend_repo.insert(user)
        updated_data = {**user, "last_name": "Jones"}
        result = backend_repo.update(user["id"], updated_data)
        fetched = backend_repo.find_by_id(user["id"])
        assert result == fetched

    def test_returns_none_for_unknown_id(self, backend_repo):
        """update returns None when the id does not exist."""
        user = _make_user()
        result = backend_repo.update(str(uuid.uuid4()), user)
        assert result is None

    def test_persists_change_after_update(self, backend_repo):
        """A subsequent find_by_id after update reflects the new data."""
        user = _make_user()
        backend_repo.insert(user)
        updated_data = {**user, "company": "NewCo"}
        backend_repo.update(user["id"], updated_data)
        found = backend_repo.find_by_id(user["id"])
        assert found["company"] == "NewCo"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_removes_existing_record(self, backend_repo):
        """delete removes the record; find_by_id returns None afterwards."""
        user = _make_user()
        backend_repo.insert(user)
        result = backend_repo.delete(user["id"])
        assert result is True
        assert backend_repo.find_by_id(user["id"]) is None

    def test_returns_true_for_existing_id(self, backend_repo):
        """delete returns True when the record existed."""
        user = _make_user()
        backend_repo.insert(user)
        assert backend_repo.delete(user["id"]) is True

    def test_returns_false_for_unknown_id(self, backend_repo):
        """delete returns False when no record matches the id."""
        assert backend_repo.delete(str(uuid.uuid4())) is False

    def test_does_not_affect_other_records(self, backend_repo):
        """Deleting one user must not remove other users."""
        u1 = _make_user(id=str(uuid.uuid4()), email="del@example.com")
        u2 = _make_user(id=str(uuid.uuid4()), email="keep@example.com")
        backend_repo.insert(u1)
        backend_repo.insert(u2)
        backend_repo.delete(u1["id"])
        assert backend_repo.find_by_id(u2["id"]) is not None

    def test_double_delete_returns_false(self, backend_repo):
        """Deleting the same id twice returns False on the second call."""
        user = _make_user()
        backend_repo.insert(user)
        backend_repo.delete(user["id"])
        assert backend_repo.delete(user["id"]) is False

    def test_find_all_reflects_deletion(self, backend_repo):
        """find_all does not include a deleted record."""
        u1 = _make_user(id=str(uuid.uuid4()), email="gone@example.com")
        u2 = _make_user(id=str(uuid.uuid4()), email="here@example.com")
        backend_repo.insert(u1)
        backend_repo.insert(u2)
        backend_repo.delete(u1["id"])
        ids = {r["id"] for r in backend_repo.find_all()}
        assert u1["id"] not in ids
        assert u2["id"] in ids


# ---------------------------------------------------------------------------
# email_exists
# ---------------------------------------------------------------------------

class TestEmailExists:
    def test_returns_true_for_existing_email(self, backend_repo):
        """email_exists returns True when the email is present in the store."""
        user = _make_user(email="exists@example.com")
        backend_repo.insert(user)
        assert backend_repo.email_exists("exists@example.com") is True

    def test_returns_false_for_unknown_email(self, backend_repo):
        """email_exists returns False when no user has that email."""
        assert backend_repo.email_exists("ghost@example.com") is False

    def test_returns_false_on_empty_store(self, backend_repo):
        """email_exists returns False when the store is empty."""
        assert backend_repo.email_exists("any@example.com") is False

    def test_exclude_id_skips_own_record(self, backend_repo):
        """email_exists with exclude_id returns False for the owner's own email."""
        user = _make_user(email="owner@example.com")
        backend_repo.insert(user)
        result = backend_repo.email_exists("owner@example.com", exclude_id=user["id"])
        assert result is False

    def test_exclude_id_still_detects_other_user(self, backend_repo):
        """email_exists with exclude_id returns True when another user has that email."""
        u1 = _make_user(id=str(uuid.uuid4()), email="shared@example.com")
        u2 = _make_user(id=str(uuid.uuid4()), email="other@example.com")
        backend_repo.insert(u1)
        backend_repo.insert(u2)
        # Checking the email from u1's perspective with u2's id excluded: still True
        result = backend_repo.email_exists("shared@example.com", exclude_id=u2["id"])
        assert result is True

    def test_returns_false_after_deletion(self, backend_repo):
        """email_exists returns False once the owning record is deleted."""
        user = _make_user(email="todelete@example.com")
        backend_repo.insert(user)
        backend_repo.delete(user["id"])
        assert backend_repo.email_exists("todelete@example.com") is False

    def test_different_email_not_detected(self, backend_repo):
        """email_exists is exact-match; a different email returns False."""
        user = _make_user(email="exact@example.com")
        backend_repo.insert(user)
        assert backend_repo.email_exists("notexact@example.com") is False


# ---------------------------------------------------------------------------
# patch
# ---------------------------------------------------------------------------

class TestPatch:
    def test_merges_partial_fields(self, backend_repo):
        """patch updates only the supplied fields."""
        user = _make_user(first_name="Alice", last_name="Smith")
        backend_repo.insert(user)
        now2 = datetime.utcnow().isoformat() + "Z"
        result = backend_repo.patch(user["id"], {"first_name": "Alicia", "updated_at": now2})
        assert result is not None
        assert result["first_name"] == "Alicia"

    def test_preserves_unchanged_fields(self, backend_repo):
        """patch does not overwrite fields absent from the patch data."""
        user = _make_user(last_name="OriginalLast", company="OriginalCo")
        backend_repo.insert(user)
        now2 = datetime.utcnow().isoformat() + "Z"
        backend_repo.patch(user["id"], {"first_name": "NewFirst", "updated_at": now2})
        found = backend_repo.find_by_id(user["id"])
        assert found["last_name"] == "OriginalLast"
        assert found["company"] == "OriginalCo"

    def test_preserves_id(self, backend_repo):
        """patch must not change the record's id."""
        user = _make_user()
        backend_repo.insert(user)
        now2 = datetime.utcnow().isoformat() + "Z"
        result = backend_repo.patch(user["id"], {"last_name": "New", "updated_at": now2})
        assert result["id"] == user["id"]

    def test_preserves_created_at(self, backend_repo):
        """patch must not change created_at."""
        user = _make_user()
        backend_repo.insert(user)
        original_created_at = user["created_at"]
        now2 = datetime.utcnow().isoformat() + "Z"
        result = backend_repo.patch(user["id"], {"company": "PatchedCo", "updated_at": now2})
        assert result["created_at"] == original_created_at

    def test_returns_none_for_unknown_id(self, backend_repo):
        """patch returns None when the id does not exist in the store."""
        now2 = datetime.utcnow().isoformat() + "Z"
        result = backend_repo.patch(str(uuid.uuid4()), {"first_name": "X", "updated_at": now2})
        assert result is None

    def test_persists_patch_after_read(self, backend_repo):
        """A subsequent find_by_id after patch reflects the patched data."""
        user = _make_user(role="attendee")
        backend_repo.insert(user)
        now2 = datetime.utcnow().isoformat() + "Z"
        backend_repo.patch(user["id"], {"role": "speaker", "updated_at": now2})
        found = backend_repo.find_by_id(user["id"])
        assert found["role"] == "speaker"

    def test_returns_full_record_not_only_patched_keys(self, backend_repo):
        """patch returns the complete updated user dict, not just the patched fields."""
        user = _make_user()
        backend_repo.insert(user)
        now2 = datetime.utcnow().isoformat() + "Z"
        result = backend_repo.patch(user["id"], {"company": "PatchOnly", "updated_at": now2})
        # All fields expected in a full user record must be present
        for field in ("id", "first_name", "last_name", "email", "role", "created_at", "updated_at"):
            assert field in result
