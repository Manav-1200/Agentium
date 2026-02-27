"""
NodriverTool — Undetected Browser Automation
============================================
Wraps the `nodriver` library (successor to undetected-chromedriver) to give agents
a stealth Chromium session that bypasses most WAF / anti-bot protections.

All public methods return a consistent Dict[str, Any] with at minimum:
    {"status": "success"|"error", ...}

Because nodriver is fully async this class is async-native.
The tool_registry handles bridging to sync callers via execute_tool_async /
run_in_executor — no changes needed there.

Docker note
-----------
nodriver requires a Chromium binary. In your Docker image add:

    RUN apt-get update && apt-get install -y chromium chromium-driver xvfb \
        && pip install nodriver

Then launch with headless=True (default) or point DISPLAY at a virtual framebuffer.
If your container already has Playwright / Chromium installed you can point
`browser_executable_path` at that binary instead.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import — nodriver is optional; fail gracefully if not installed
# ---------------------------------------------------------------------------
try:
    import nodriver as uc
    _NODRIVER_AVAILABLE = True
except ImportError:
    _NODRIVER_AVAILABLE = False
    logger.warning(
        "nodriver package not installed. "
        "Run `pip install nodriver` and ensure Chromium is available."
    )


class NodriverTool:
    """
    Stealth browser automation tool backed by nodriver.

    Lifecycle
    ---------
    The browser is started lazily on the first call that needs it and is
    kept alive across calls so agents can carry session state (cookies, login,
    etc.).  Call `close()` explicitly when done, or use the registry's
    shutdown hook if you add one.

    A single active tab is tracked (`self._tab`).  Most operations act on
    that tab; use `navigate()` to open a new URL in it or `new_tab()` to
    open a parallel tab.
    """

    def __init__(
        self,
        headless: bool = True,
        browser_executable_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        browser_args: Optional[List[str]] = None,
        lang: str = "en-US",
    ):
        self._headless = headless
        self._browser_executable_path = browser_executable_path
        self._user_data_dir = user_data_dir
        self._browser_args = browser_args or []
        self._lang = lang

        self._browser: Optional[Any] = None   # nodriver.Browser
        self._tab: Optional[Any] = None       # nodriver.Tab
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _unavailable(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error": (
                "nodriver is not installed. "
                "Add `pip install nodriver` to your Docker image and ensure Chromium is present."
            ),
        }

    async def _ensure_browser(self) -> None:
        """Start the browser if it isn't running yet."""
        if self._browser is not None:
            return

        start_kwargs: Dict[str, Any] = {
            "headless": self._headless,
            "lang": self._lang,
        }
        if self._browser_executable_path:
            start_kwargs["browser_executable_path"] = self._browser_executable_path
        if self._user_data_dir:
            start_kwargs["user_data_dir"] = self._user_data_dir
        if self._browser_args:
            start_kwargs["browser_args"] = self._browser_args

        self._browser = await uc.start(**start_kwargs)
        logger.info("nodriver browser started (headless=%s)", self._headless)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API — each method is a tool endpoint
    # ──────────────────────────────────────────────────────────────────────────

    async def navigate(
        self,
        url: str,
        new_tab: bool = False,
        new_window: bool = False,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Navigate to *url*.

        Parameters
        ----------
        url        : Destination URL (must include scheme, e.g. https://)
        new_tab    : Open in a new tab instead of the current one
        new_window : Open in a new browser window
        timeout    : Seconds to wait for page load (default 30)
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        try:
            await self._ensure_browser()
            tab = await self._browser.get(url, new_tab=new_tab, new_window=new_window)
            self._tab = tab
            title = await tab.evaluate("document.title")
            current_url = await tab.evaluate("location.href")
            return {
                "status": "success",
                "url": current_url,
                "title": title,
                "new_tab": new_tab,
                "new_window": new_window,
            }
        except Exception as exc:
            logger.exception("navigate failed")
            return {"status": "error", "error": str(exc)}

    async def get_content(
        self,
        max_chars: int = 8000,
    ) -> Dict[str, Any]:
        """
        Return the current page's HTML content (truncated to *max_chars*).
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            content = await self._tab.get_content()
            return {
                "status": "success",
                "content": content[:max_chars],
                "truncated": len(content) > max_chars,
                "total_chars": len(content),
            }
        except Exception as exc:
            logger.exception("get_content failed")
            return {"status": "error", "error": str(exc)}

    async def find_element(
        self,
        text: str,
        best_match: bool = True,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Find a DOM element by visible text.

        Uses nodriver's smart shortest-text-match algorithm so
        ``find_element("accept all")`` returns the cookie button,
        not a script block that happens to contain the phrase.

        Parameters
        ----------
        text       : Visible text to search for
        best_match : When True, returns the element whose text length is
                     closest to *text* (most precise match)
        timeout    : How long to retry before giving up (seconds)
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            elem = await self._tab.find(text, best_match=best_match, timeout=timeout)
            if elem is None:
                return {"status": "not_found", "text": text}
            return {
                "status": "success",
                "text": text,
                "element_html": repr(elem),
                "tag": elem.tag_name if hasattr(elem, "tag_name") else None,
            }
        except Exception as exc:
            logger.exception("find_element failed")
            return {"status": "error", "error": str(exc)}

    async def find_all_elements(
        self,
        text: str,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Find *all* elements whose visible text contains *text*.
        Returns a list of element reprs.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            elems = await self._tab.find_all(text, timeout=timeout)
            return {
                "status": "success",
                "text": text,
                "count": len(elems),
                "elements": [repr(e) for e in elems],
            }
        except Exception as exc:
            logger.exception("find_all_elements failed")
            return {"status": "error", "error": str(exc)}

    async def select_element(
        self,
        css_selector: str,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Select a single element by CSS selector (waits until it appears).

        Example selectors
        -----------------
        - ``"input[type=email]"``
        - ``"a[href] > div > img"``
        - ``"[role=button]"``
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            elem = await self._tab.select(css_selector, timeout=timeout)
            if elem is None:
                return {"status": "not_found", "selector": css_selector}
            return {
                "status": "success",
                "selector": css_selector,
                "element_html": repr(elem),
            }
        except Exception as exc:
            logger.exception("select_element failed")
            return {"status": "error", "error": str(exc)}

    async def select_all_elements(
        self,
        css_selector: str,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Select *all* elements matching a CSS selector.
        Also works on content inside iframes.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            elems = await self._tab.select_all(css_selector, timeout=timeout)
            return {
                "status": "success",
                "selector": css_selector,
                "count": len(elems),
                "elements": [repr(e) for e in elems],
            }
        except Exception as exc:
            logger.exception("select_all_elements failed")
            return {"status": "error", "error": str(exc)}

    async def xpath(
        self,
        xpath_selector: str,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Find a node using an XPath selector.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            elem = await self._tab.xpath(xpath_selector, timeout=timeout)
            if elem is None:
                return {"status": "not_found", "xpath": xpath_selector}
            return {
                "status": "success",
                "xpath": xpath_selector,
                "element_html": repr(elem),
            }
        except Exception as exc:
            logger.exception("xpath failed")
            return {"status": "error", "error": str(exc)}

    async def click_element(
        self,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        best_match: bool = True,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Click an element located by CSS *selector* **or** visible *text*.
        Exactly one of the two must be supplied.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        if not selector and not text:
            return {"status": "error", "error": "Provide 'selector' or 'text'."}
        try:
            if selector:
                elem = await self._tab.select(selector, timeout=timeout)
            else:
                elem = await self._tab.find(text, best_match=best_match, timeout=timeout)

            if elem is None:
                return {"status": "not_found", "selector": selector, "text": text}

            await elem.click()
            return {"status": "success", "clicked": selector or text}
        except Exception as exc:
            logger.exception("click_element failed")
            return {"status": "error", "error": str(exc)}

    async def send_keys(
        self,
        selector: str,
        keys: str,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Send keystrokes to the element matched by *selector*.
        Use for filling text inputs, dropdowns (send the visible option text), etc.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            elem = await self._tab.select(selector, timeout=timeout)
            if elem is None:
                return {"status": "not_found", "selector": selector}
            await elem.send_keys(keys)
            return {"status": "success", "selector": selector, "keys_sent": keys}
        except Exception as exc:
            logger.exception("send_keys failed")
            return {"status": "error", "error": str(exc)}

    async def evaluate(
        self,
        expression: str,
    ) -> Dict[str, Any]:
        """
        Evaluate arbitrary JavaScript in the page context and return the result.

        Example
        -------
        ``{"expression": "document.querySelectorAll('a').length"}``
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            result = await self._tab.evaluate(expression)
            return {"status": "success", "expression": expression, "result": result}
        except Exception as exc:
            logger.exception("evaluate failed")
            return {"status": "error", "error": str(exc)}

    async def scroll(
        self,
        amount: int = 200,
        direction: str = "down",
    ) -> Dict[str, Any]:
        """
        Scroll the page.

        Parameters
        ----------
        amount    : Pixels to scroll (default 200)
        direction : ``"down"`` | ``"up"`` (default ``"down"``)
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            if direction == "down":
                await self._tab.scroll_down(amount)
            else:
                await self._tab.scroll_up(amount)
            return {"status": "success", "scrolled": direction, "amount": amount}
        except Exception as exc:
            logger.exception("scroll failed")
            return {"status": "error", "error": str(exc)}

    async def screenshot(
        self,
        save_path: str = "/tmp/nodriver_screenshot.png",
    ) -> Dict[str, Any]:
        """
        Save a screenshot of the current page to *save_path*.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            await self._tab.save_screenshot(save_path)
            size = Path(save_path).stat().st_size if Path(save_path).exists() else 0
            return {
                "status": "success",
                "save_path": save_path,
                "size_bytes": size,
            }
        except Exception as exc:
            logger.exception("screenshot failed")
            return {"status": "error", "error": str(exc)}

    async def save_cookies(
        self,
        filepath: str,
    ) -> Dict[str, Any]:
        """Save session cookies to *filepath* (JSON) for reuse across runs."""
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            await self._tab.save_cookies(filepath)
            return {"status": "success", "filepath": filepath}
        except Exception as exc:
            logger.exception("save_cookies failed")
            return {"status": "error", "error": str(exc)}

    async def load_cookies(
        self,
        filepath: str,
    ) -> Dict[str, Any]:
        """Restore cookies from *filepath* (previously saved by save_cookies)."""
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            await self._tab.load_cookies(filepath)
            return {"status": "success", "filepath": filepath}
        except Exception as exc:
            logger.exception("load_cookies failed")
            return {"status": "error", "error": str(exc)}

    async def get_local_storage(self) -> Dict[str, Any]:
        """Return the page's localStorage as a dict."""
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            data = await self._tab.get_local_storage()
            return {"status": "success", "local_storage": data}
        except Exception as exc:
            logger.exception("get_local_storage failed")
            return {"status": "error", "error": str(exc)}

    async def set_local_storage(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Set localStorage key-value pairs on the current page."""
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            await self._tab.set_local_storage(data)
            return {"status": "success", "keys_set": list(data.keys())}
        except Exception as exc:
            logger.exception("set_local_storage failed")
            return {"status": "error", "error": str(exc)}

    async def cf_verify(self) -> Dict[str, Any]:
        """
        Automatically solve a Cloudflare 'I am human' checkbox.
        Requires ``opencv-python`` to be installed.
        Only works when *not* in expert mode.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            await self._tab.cf_verify()
            return {"status": "success", "action": "cf_verify"}
        except Exception as exc:
            logger.exception("cf_verify failed")
            return {"status": "error", "error": str(exc)}

    async def bypass_insecure_warning(self) -> Dict[str, Any]:
        """
        Click through the browser's 'your connection is not private' warning page.
        Useful when testing against self-signed certificates.
        """
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            await self._tab.bypass_insecure_connection_warning()
            return {"status": "success", "action": "bypass_insecure_warning"}
        except Exception as exc:
            logger.exception("bypass_insecure_warning failed")
            return {"status": "error", "error": str(exc)}

    async def reload(self) -> Dict[str, Any]:
        """Reload the current page."""
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab. Call navigate() first."}
        try:
            await self._tab.reload()
            title = await self._tab.evaluate("document.title")
            return {"status": "success", "action": "reload", "title": title}
        except Exception as exc:
            logger.exception("reload failed")
            return {"status": "error", "error": str(exc)}

    async def close_tab(self) -> Dict[str, Any]:
        """Close the currently active tab."""
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        if not self._tab:
            return {"status": "error", "error": "No active tab."}
        try:
            await self._tab.close()
            self._tab = None
            return {"status": "success", "action": "close_tab"}
        except Exception as exc:
            logger.exception("close_tab failed")
            return {"status": "error", "error": str(exc)}

    async def close(self) -> Dict[str, Any]:
        """Shut down the browser entirely and clean up."""
        if not _NODRIVER_AVAILABLE:
            return self._unavailable()
        try:
            if self._browser:
                self._browser.stop()
                self._browser = None
                self._tab = None
                logger.info("nodriver browser stopped")
            return {"status": "success", "action": "browser_closed"}
        except Exception as exc:
            logger.exception("close failed")
            return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton used by tool_registry
# ---------------------------------------------------------------------------
nodriver_tool = NodriverTool()