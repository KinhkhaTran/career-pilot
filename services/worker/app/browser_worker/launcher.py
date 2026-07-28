"""Headful Chromium launch with a persistent local profile.

Playwright is an *optional* runtime dependency: it is imported lazily so the
test suite (which drives a deterministic in-memory page) and the rest of the
worker never require a browser binary.

Safety properties enforced here:

* Headless is refused — assisted runs must be visible so a human can supervise.
* No stealth/automation-concealment flags, no proxy configuration, no
  credential injection. The persistent profile lets the human log in *once*,
  by hand; the runner never handles passwords, MFA codes, or CAPTCHAs.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any


class LaunchRejected(RuntimeError):
    pass


class PlaywrightPageAdapter:
    """Adapt a real Playwright ``Page`` to the :class:`BrowserPage` protocol."""

    def __init__(self, page: Any) -> None:
        self._page = page

    async def goto(self, url: str) -> None:
        await self._page.goto(url, wait_until="domcontentloaded")

    async def current_url(self) -> str:
        return str(self._page.url)

    async def content(self) -> str:
        return str(await self._page.content())

    async def is_visible(self, selector: str) -> bool:
        try:
            return bool(await self._page.is_visible(selector))
        except Exception:  # noqa: BLE001 - a missing selector is simply "not visible"
            return False

    async def text_content(self, selector: str) -> str | None:
        loc = self._page.locator(selector).first
        if not await loc.count():
            return None
        text: str | None = await loc.text_content()
        return text

    async def fill(self, selector: str, value: str) -> None:
        await self._page.fill(selector, value)

    async def click(self, selector: str) -> None:
        await self._page.click(selector)

    async def check(self, selector: str) -> None:
        await self._page.check(selector)

    async def select_option(self, selector: str, value: str) -> None:
        await self._page.select_option(selector, value)

    async def set_input_files(self, selector: str, path: str) -> None:
        await self._page.set_input_files(selector, path)

    async def screenshot(self, *, path: str) -> bytes:
        return bytes(await self._page.screenshot(path=path))


@asynccontextmanager
async def launch_persistent_headful(
    profile_dir: str, *, headless: bool = False
) -> AsyncIterator[PlaywrightPageAdapter]:
    """Open a visible Chromium bound to a persistent local profile directory."""
    if headless:
        raise LaunchRejected("assisted runs must be visible; headless is forbidden")
    try:
        from playwright.async_api import async_playwright  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - only in real-browser use
        raise LaunchRejected(
            "playwright is not installed; install it to run against a live browser"
        ) from exc

    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,  # never headless for a supervised run
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            yield PlaywrightPageAdapter(page)
        finally:
            await context.close()
