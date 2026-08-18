"""The loader satisfies Vibe-Trading's DataLoaderProtocol, structurally."""

from __future__ import annotations

import inspect

from vibe_trading_livetennis.loader import DataLoader

from ._protocol import DataLoaderProtocol


def test_instance_is_a_data_loader():
    assert isinstance(DataLoader(), DataLoaderProtocol)


def test_declares_required_class_attributes():
    assert DataLoader.name == "polymarket_tennis"
    assert isinstance(DataLoader.markets, set) and DataLoader.markets
    assert DataLoader.requires_auth is False


def test_is_available_true_without_any_key():
    # Public keyless endpoints, so availability never depends on a credential.
    assert DataLoader().is_available() is True


def test_fetch_signature_matches_protocol():
    sig = inspect.signature(DataLoader.fetch)
    params = sig.parameters
    assert list(params)[:4] == ["self", "codes", "start_date", "end_date"]
    assert params["interval"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["fields"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["interval"].default == "1D"
    assert params["fields"].default is None
