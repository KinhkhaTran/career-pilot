"""Clean-room ATS form boundary. Implementations never submit."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class BrowserPage(Protocol):
    async def goto(self, url: str) -> None: ...
    async def fill(self, selector: str, value: str) -> None: ...
    async def screenshot(self, *, path: str) -> bytes: ...


class ATSFormAdapter(Protocol):
    @property
    def name(self) -> str: ...

    async def open_application(self, page: BrowserPage, url: str) -> None: ...
    def selectors(self) -> dict[str, str]: ...


@dataclass(frozen=True)
class GreenhouseLikeAdapter:
    """Deterministic public-form adapter; selectors are deliberately explicit."""

    name: str = "greenhouse-like"
    _selectors: dict[str, str] = field(default_factory=lambda: {
        "full_name": "input[name='name']",
        "email": "input[name='email']",
        "phone": "input[name='phone']",
        "linkedin": "input[name='urls[LinkedIn]']",
        "cover_letter": "textarea[name='cover_letter']",
    })

    async def open_application(self, page: BrowserPage, url: str) -> None:
        await page.goto(url)

    def selectors(self) -> dict[str, str]:
        return dict(self._selectors)


GenericMockATSAdapter = GreenhouseLikeAdapter
