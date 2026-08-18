"""Self-registration helper for a Vibe-Trading install.

Vibe-Trading loaders self-register via a ``@register`` class decorator that
writes into ``backtest.loaders.registry.LOADER_REGISTRY``, and every accepted
source name also lives in ``backtest.loaders.registry.VALID_SOURCES``. Because
this loader lives in a *separate* package (it is not bundled into the host
repo — see the maintainer's guidance on HKUDS/Vibe-Trading#1133), the host does
not import it automatically. Call :func:`register` once at startup — before the
first ``backtest`` / ``get_market_data`` call — to wire it in.

The import of the host modules is deferred to call time so this package installs
and its own tests run without Vibe-Trading present.
"""

from __future__ import annotations

from typing import Any

from .loader import DataLoader

__all__ = ["register"]


def register() -> type[Any]:
    """Register the loader with the host's registry and accepted-source set.

    Returns:
        The registered :class:`DataLoader` class.

    Raises:
        ImportError: Vibe-Trading is not importable in the current environment
            (install ``vibe-trading-ai`` and run inside its ``agent/`` package
            path).
    """
    from backtest.loaders.registry import (  # type: ignore[import-not-found]
        LOADER_REGISTRY,
        VALID_SOURCES,
    )
    from backtest.loaders.registry import (
        register as host_register,
    )

    host_register(DataLoader)
    # host_register already writes LOADER_REGISTRY[name]; add the source name to
    # VALID_SOURCES so the config schema and backtest tool accept it too.
    LOADER_REGISTRY[DataLoader.name] = DataLoader
    VALID_SOURCES.add(DataLoader.name)
    return DataLoader
