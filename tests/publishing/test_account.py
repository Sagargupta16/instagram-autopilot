"""The end card's handle comes from a read-only lookup that never fails the slot."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.adapters.composio import ComposioActionError, ComposioRequestError
from src.publishing import account


def test_handle_reads_the_connected_accounts_username(monkeypatch) -> None:
    lookup = Mock(return_value={"successful": True, "data": {"id": "1", "username": "facts.daily"}})
    monkeypatch.setattr(account, "execute_action", lookup)
    assert account.handle() == "@facts.daily"
    lookup.assert_called_once_with(
        "INSTAGRAM_GET_USER_INFO", {"ig_user_id": "me", "fields": "username"}
    )


@pytest.mark.parametrize(
    "error", [ComposioRequestError("timeout"), ComposioActionError("token expired")]
)
def test_a_failed_lookup_gives_no_handle(monkeypatch, error) -> None:
    monkeypatch.setattr(account, "execute_action", Mock(side_effect=error))
    assert account.handle() is None


@pytest.mark.parametrize("username", [None, "", "has space", "x" * 31, 42])
def test_an_unusable_username_gives_no_handle(monkeypatch, username) -> None:
    result = {"successful": True, "data": {"username": username}}
    monkeypatch.setattr(account, "execute_action", Mock(return_value=result))
    assert account.handle() is None
