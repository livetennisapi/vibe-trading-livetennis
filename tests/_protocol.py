"""A local copy of Vibe-Trading's ``DataLoaderProtocol`` structural shape.

Kept here verbatim (methods + attributes only) so the conformance test can
``isinstance``-check our loader against the host's interface without importing
the host package. Mirrors ``agent/backtest/loaders/base.py`` in
HKUDS/Vibe-Trading: a ``runtime_checkable`` Protocol with ``name`` / ``markets``
/ ``requires_auth`` and ``is_available`` / ``fetch``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DataLoaderProtocol(Protocol):
    """Structural interface every Vibe-Trading loader must satisfy."""

    name: str
    markets: set[str]
    requires_auth: bool

    def is_available(self) -> bool:
        ...

    def fetch(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        ...
