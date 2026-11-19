import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page


class BrowserController:
    """Manages an authenticated, user-visible Playwright browser session for autonomous web tasks."""

    def __init__(self, user_data_dir: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.profile_dir = Path(user_data_dir) if user_data_dir else (base_dir / "data" / "browser_profile")
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._current_page: Optional[Page] = None
        self._thread_id: Optional[int] = None
        self.is_running: bool = False

    def start(self, channel: Optional[str] = None) -> bool:
        """Launch or attach to persistent Chrome session."""
        current_tid = threading.get_ident()
        if self.is_running and self._context:
            if self._thread_id == current_tid:
                return True
            else:
                self.close()

        self._thread_id = current_tid
        self._playwright = sync_playwright().start()

        # Prioritize Google Chrome, fallback to Edge, then bundled Chromium
        channels_to_try = [channel] if channel else ["chrome", "msedge", None]
        last_error = None

        for ch in channels_to_try:
            try:
                launch_kwargs: Dict[str, Any] = {
                    "user_data_dir": str(self.profile_dir),
                    "headless": False,
                    "viewport": {"width": 1280, "height": 850},
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized",
                    ],
                    "ignore_default_args": ["--enable-automation"],
                }
                if ch:
                    launch_kwargs["channel"] = ch

                self._context = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
                if self._context.pages:
                    self._current_page = self._context.pages[0]
                else:
                    self._current_page = self._context.new_page()

                self.is_running = True
                return True
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"Could not launch browser session: {last_error}")

    def get_current_page(self) -> Page:
        if not self._current_page or self._current_page.is_closed():
            if self._context and self._context.pages:
                self._current_page = self._context.pages[-1]
            elif self._context:
                self._current_page = self._context.new_page()
            else:
                self.start()
        return self._current_page

    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to destination URL."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        page = self.get_current_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1.0)
            return {"success": True, "url": page.url, "title": page.title()}
        except Exception as e:
            return {"success": False, "error": str(e), "url": page.url}

    def get_page_info(self) -> Dict[str, Any]:
        """Get current URL, title, and open tab list."""
        page = self.get_current_page()
        tabs = [p.title() or p.url for p in (self._context.pages if self._context else [page])]
        return {
            "url": page.url,
            "title": page.title(),
            "tab_count": len(tabs),
            "tabs": tabs,
        }

    def extract_interactive_elements(self) -> List[Dict[str, Any]]:
        """Query DOM for visible interactive elements: buttons, inputs, links, textareas, selects."""
        page = self.get_current_page()

        js_script = """
        () => {
            const results = [];
            const interactiveSelectors = 'button, a, input, textarea, select, [role="button"], [role="link"], [role="textbox"], [role="menuitem"], [contenteditable="true"]';
            const elements = document.querySelectorAll(interactiveSelectors);

            for (const el of elements) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const isVisible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                if (!isVisible) continue;

                let text = (el.innerText || el.textContent || '').trim();
                let val = el.value ? el.value.trim() : '';
                let aria = el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
                let role = el.getAttribute('role') || el.tagName.toLowerCase();

                // Unique selector generator
                let selector = '';
                if (el.id) {
                    selector = '#' + el.id;
                } else if (el.name) {
                    selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                } else if (el.getAttribute('data-control-name')) {
                    selector = `[data-control-name="${el.getAttribute('data-control-name')}"]`;
                } else if (aria) {
                    selector = `[aria-label="${aria}"]`;
                }

                results.push({
                    tag: el.tagName.toLowerCase(),
                    role: role,
                    text: text.slice(0, 80),
                    value: val.slice(0, 80),
                    aria_label: aria.slice(0, 80),
                    placeholder: el.getAttribute('placeholder') || '',
                    selector: selector,
                    is_visible: true,
                    box: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)}
                });
                if (results.length >= 100) break;
            }
            return results;
        }
        """
        try:
            return page.evaluate(js_script)
        except Exception:
            return []

    def click(self, target: str, by_text: bool = False) -> Dict[str, Any]:
        """Click element by selector, role, or text."""
        page = self.get_current_page()
        try:
            if by_text or not (target.startswith("#") or target.startswith(".") or target.startswith("[")):
                # Try locator by text or role
                loc = page.get_by_role("button", name=target).first
                if loc.count() > 0:
                    loc.click(timeout=5000)
                    return {"success": True, "target": target}
                
                loc_text = page.get_by_text(target, exact=False).first
                if loc_text.count() > 0:
                    loc_text.click(timeout=5000)
                    return {"success": True, "target": target}

            # Standard selector fallback
            page.locator(target).first.click(timeout=6000)
            return {"success": True, "target": target}
        except Exception as e:
            return {"success": False, "error": str(e), "target": target}

    def type_text(self, target: str, text: str, clear_first: bool = True) -> Dict[str, Any]:
        """Fill or type text into a designated field."""
        page = self.get_current_page()
        try:
            loc = page.locator(target).first
            if loc.count() == 0:
                loc = page.get_by_placeholder(target).first
            if loc.count() == 0:
                loc = page.get_by_label(target).first

            if clear_first:
                loc.fill(text, timeout=6000)
            else:
                loc.type(text, timeout=6000)
            return {"success": True, "target": target, "typed_length": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e), "target": target}

    def scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        """Scroll the current page."""
        page = self.get_current_page()
        delta = amount if direction.lower() == "down" else -amount
        try:
            page.evaluate(f"window.scrollBy(0, {delta});")
            time.sleep(0.4)
            return {"success": True, "direction": direction, "amount": amount}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def press_key(self, key: str) -> Dict[str, Any]:
        page = self.get_current_page()
        try:
            page.keyboard.press(key)
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_screenshot(self, output_path: str) -> bool:
        page = self.get_current_page()
        try:
            page.screenshot(path=output_path, full_page=False)
            return True
        except Exception:
            return False

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self.is_running = False
            self._context = None
            self._playwright = None
            self._current_page = None
            self._thread_id = None

