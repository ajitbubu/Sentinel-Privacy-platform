"""Email normalisation. Over-merging is the dangerous failure: two people
collapsed into one subject leaks data across a DSAR boundary."""
import pytest

from src.services.identity_service import IdentityError, normalize


def test_case_and_whitespace():
    assert normalize("  John.Doe@Example.COM ") == "john.doe@example.com"


def test_gmail_dots_and_plus_are_aliases():
    assert normalize("john.doe+news@gmail.com") == "johndoe@gmail.com"
    assert normalize("johndoe@googlemail.com") == "johndoe@googlemail.com"


def test_plus_stripped_only_for_known_providers():
    # Outlook aliases +tags...
    assert normalize("a+tag@outlook.com") == "a@outlook.com"
    # ...but an arbitrary corporate domain may treat +tag as a distinct mailbox,
    # so we must NOT merge those.
    assert normalize("a+tag@acme-corp.com") == "a+tag@acme-corp.com"


def test_dots_preserved_outside_gmail():
    """Merging first.last@ with firstlast@ on a corporate domain could union
    two different employees."""
    assert normalize("first.last@acme-corp.com") == "first.last@acme-corp.com"


def test_invalid_emails_rejected():
    for bad in ("", "no-at-sign", "@example.com", "a@b", "a b@example.com"):
        with pytest.raises(IdentityError):
            normalize(bad)


def test_plus_only_local_part_rejected():
    with pytest.raises(IdentityError):
        normalize("+tag@gmail.com")
