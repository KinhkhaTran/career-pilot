"""Adapter factory shared by the discovery task and the scheduler.

Keeps the source -> adapter mapping in one place so the manual CLI task and
the scheduled cron cannot drift on which sources are supported.
"""
from __future__ import annotations

from collections.abc import Callable

from .ashby import AshbyAdapter
from .base import ATSAdapter
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter

_ADAPTERS: dict[str, Callable[[str], ATSAdapter]] = {
    "greenhouse": lambda company_id: GreenhouseAdapter(board_token=company_id),
    "lever": lambda company_id: LeverAdapter(company_slug=company_id),
    "ashby": lambda company_id: AshbyAdapter(organization_id=company_id),
}

SUPPORTED_SOURCES = tuple(_ADAPTERS)


def build_adapter(source: str, company_id: str) -> ATSAdapter:
    """Return the read-only ATS adapter for ``source``.

    Raises ValueError for an unknown source so both the task and the scheduler
    fail loudly rather than silently skipping a misconfigured entry.
    """
    factory = _ADAPTERS.get(source)
    if factory is None:
        raise ValueError(f"Unknown ATS source: {source!r}. Valid: {list(_ADAPTERS)}")
    return factory(company_id)
