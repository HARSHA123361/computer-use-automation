from __future__ import annotations

import base64
import os
from typing import Optional, Tuple

from playwright.sync_api import Page, sync_playwright, Browser, BrowserContext, Playwright

from .schema import Locator, LocatorStrategy


class BrowserSession:
    def __init__(self, headless: bool = True, screenshots_dir: str = "evidence/screenshots"):
        self.headless = headless
        self.screenshots_dir = screenshots_dir
        os.makedirs(screenshots_dir, exist_ok=True)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._screenshot_counter = 0

    def start(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (compatible; AutomationAgent/1.0)",
        )
        self.page = self._context.new_page()

    def stop(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def navigate(self, url: str, timeout_ms: int = 10000) -> None:
        self.page.goto(url, timeout=timeout_ms)
        self.page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)

    def resolve_locator(self, locator: Locator, timeout_ms: int = 5000):
        strategies = [locator] + locator.fallbacks
        last_error = None
        for loc in strategies:
            try:
                element = self._build_locator(loc)
                element.wait_for(state="visible", timeout=timeout_ms)
                return element
            except Exception as e:
                last_error = e
                continue
        raise RuntimeError(
            f"Could not resolve locator '{locator.description}' "
            f"with any strategy. Last error: {last_error}"
        )

    def _build_locator(self, locator: Locator):
        strategy = locator.strategy
        value = locator.value

        if strategy == LocatorStrategy.css:
            return self.page.locator(value)
        elif strategy == LocatorStrategy.xpath:
            return self.page.locator(f"xpath={value}")
        elif strategy == LocatorStrategy.text:
            return self.page.get_by_text(value, exact=False)
        elif strategy == LocatorStrategy.label:
            return self.page.get_by_label(value)
        elif strategy == LocatorStrategy.role:
            parts = value.split(":", 1)
            role = parts[0]
            name = parts[1] if len(parts) > 1 else None
            if name:
                return self.page.get_by_role(role, name=name)
            return self.page.get_by_role(role)
        elif strategy == LocatorStrategy.accessibility:
            return self.page.locator(f"[aria-label='{value}']")
        else:
            raise ValueError(f"Unknown locator strategy: {strategy}")

    def click(self, locator: Locator, timeout_ms: int = 5000) -> None:
        element = self.resolve_locator(locator, timeout_ms)
        element.click(timeout=timeout_ms)

    def type_text(self, locator: Locator, text: str, timeout_ms: int = 5000) -> None:
        element = self.resolve_locator(locator, timeout_ms)
        element.fill(text, timeout=timeout_ms)

    def select_option(self, locator: Locator, value: str, timeout_ms: int = 5000) -> None:
        element = self.resolve_locator(locator, timeout_ms)
        element.select_option(value, timeout=timeout_ms)

    def wait_for(self, locator: Locator, timeout_ms: int = 10000) -> None:
        self.resolve_locator(locator, timeout_ms)

    def extract_text(self, locator: Locator, timeout_ms: int = 5000) -> str:
        element = self.resolve_locator(locator, timeout_ms)
        return (element.inner_text(timeout=timeout_ms) or "").strip()

    def check_text_present(self, locator: Locator, expected_text: Optional[str], timeout_ms: int = 5000) -> Tuple[bool, str]:
        try:
            element = self.resolve_locator(locator, timeout_ms)
            actual = (element.inner_text(timeout=timeout_ms) or "").strip()
            if expected_text is None:
                return True, actual
            if expected_text.lower() in actual.lower():
                return True, actual
            return False, actual
        except Exception as e:
            return False, str(e)

    def check_url_contains(self, fragment: str) -> bool:
        return fragment in self.page.url

    def current_url(self) -> str:
        return self.page.url

    def get_page_text(self) -> str:
        try:
            return self.page.inner_text("body") or ""
        except Exception:
            return ""

    def get_accessibility_snapshot(self) -> dict:
        try:
            return self.page.accessibility.snapshot() or {}
        except Exception:
            return {}

    def take_screenshot(self, label: str = "") -> str:
        self._screenshot_counter += 1
        filename = f"{self._screenshot_counter:03d}_{label}.png" if label else f"{self._screenshot_counter:03d}.png"
        path = os.path.join(self.screenshots_dir, filename)
        self.page.screenshot(path=path, full_page=True)
        return path

    def screenshot_as_base64(self) -> str:
        data = self.page.screenshot(full_page=True)
        return base64.b64encode(data).decode("utf-8")

    def get_dom_snapshot(self) -> str:
        try:
            return self.page.content()
        except Exception:
            return ""
