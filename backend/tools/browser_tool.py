"""
Browser Tool — Simple synchronous Playwright browser control.

Provides basic web navigation and screenshots via the sync Playwright API.
For full-featured async browser automation (forms, JS execution, downloads,
multi-tab, etc.) use the DesktopTool's BrowserAutomationTool, registered
in the ToolRegistry as desktop_browser_* tools.

This file is the original lightweight browser tool registered as:
  - browser_control    (navigate)
  - browser_screenshot (screenshot)
"""

from typing import Any, Dict, List, Optional

# Playwright is an optional dependency — fail gracefully if not installed.
try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


class BrowserTool:
    """
    Simple synchronous browser for basic navigation and screenshots.

    Tool contract
    -------------
    TOOL_NAME         : str  — registry key used by ToolFactory
    TOOL_DESCRIPTION  : str  — sent to LLM as the tool description
    AUTHORIZED_TIERS  : list — which agent tiers may call this tool
    execute(**kwargs) : async entry-point used when loaded dynamically
    tool_instance     : module-level singleton for dynamic loader
    """

    TOOL_NAME: str = "browser_control"
    TOOL_DESCRIPTION: str = """
    Simple browser control for web navigation and screenshots.
    Handles single-page visits and content capture.

    For forms, JavaScript execution, cookies, downloads, or multi-tab
    sessions use the desktop_browser_* tools instead.

    Actions:
      navigate   — Load a URL; returns title and content snippet
      screenshot — Save a PNG of the current page to disk
      close      — Close the browser and release all resources
    """
    AUTHORIZED_TIERS: List[str] = ["0xxxx", "1xxxx"]

    def __init__(self) -> None:
        self.playwright = None
        self.browser    = None
        self._page      = None   # tracks the most-recently-opened page

    # ── Tool contract: async dispatch entry-point ──────────────────────────────

    async def execute(
        self,
        action: str,
        url:      Optional[str] = None,
        path:     str = "/tmp/browser_screenshot.png",
        headless: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Dispatch to the requested browser action.

        Parameters
        ----------
        action   : "navigate" | "screenshot" | "close"
        url      : destination URL (required for navigate)
        path     : file path for screenshot PNG
        headless : run Chromium headless (default True)
        """
        handlers = {
            "navigate":   self._action_navigate,
            "screenshot": self._action_screenshot,
            "close":      self._action_close,
        }
        handler = handlers.get(action)
        if not handler:
            return {
                "success": False,
                "action":  action,
                "error":   (
                    f"Unknown action '{action}'. "
                    f"Valid actions: {sorted(handlers.keys())}"
                ),
            }
        try:
            return await handler(url=url, path=path, headless=headless, **kwargs)
        except Exception as exc:
            return {"success": False, "action": action, "error": str(exc)}

    # ── Async action handlers (called from execute) ────────────────────────────

    async def _action_navigate(
        self,
        url:      Optional[str],
        headless: bool = True,
        **_: Any,
    ) -> Dict[str, Any]:
        if not _PLAYWRIGHT_AVAILABLE:
            return {"success": False, "action": "navigate",
                    "error": "playwright not installed — run: pip install playwright && playwright install chromium"}
        if not url:
            return {"success": False, "action": "navigate",
                    "error": "'url' is required for navigate"}
        result = self.navigate(url, headless=headless)
        # Normalise key names to match tool contract
        return {
            "success": result.get("status") == "success",
            "action":  "navigate",
            **{k: v for k, v in result.items() if k != "status"},
        }

    async def _action_screenshot(
        self,
        path: str = "/tmp/browser_screenshot.png",
        **_: Any,
    ) -> Dict[str, Any]:
        if not _PLAYWRIGHT_AVAILABLE:
            return {"success": False, "action": "screenshot",
                    "error": "playwright not installed"}
        result = self.screenshot(path=path)
        return {
            "success": result.get("status") == "success",
            "action":  "screenshot",
            **{k: v for k, v in result.items() if k != "status"},
        }

    async def _action_close(self, **_: Any) -> Dict[str, Any]:
        self.close()
        return {"success": True, "action": "close"}

    # ── Public sync methods — used directly by ToolRegistry registrations ──────
    # These signatures are UNCHANGED from the original so existing registry
    # calls (browser.navigate, browser.screenshot) keep working.

    def launch(self, headless: bool = True) -> Dict[str, Any]:
        """Launch browser instance."""
        if not _PLAYWRIGHT_AVAILABLE:
            return {"status": "error",
                    "error": "playwright not installed"}
        self._ensure_browser(headless)
        return {"status": "success", "browser": "chromium"}

    def navigate(self, url: str, headless: bool = True) -> Dict[str, Any]:
        """Navigate to URL and return title + content snippet."""
        if not _PLAYWRIGHT_AVAILABLE:
            return {"status": "error",
                    "error": "playwright not installed"}
        self._ensure_browser(headless)
        page = self.browser.new_page()
        try:
            page.goto(url, timeout=30_000)
            title   = page.title()
            content = page.content()
            # Keep the page open so screenshot() can use it
            if self._page and self._page != page:
                try:
                    self._page.close()
                except Exception:
                    pass
            self._page = page
            return {
                "status":  "success",
                "url":     url,
                "title":   title,
                "content": content[:2000],
            }
        except Exception as exc:
            page.close()
            return {"status": "error", "error": str(exc)}

    def click(self, selector: str) -> Dict[str, Any]:
        """Click element by CSS selector."""
        if not self._page:
            return {"status": "error",
                    "error": "No page open — call navigate first"}
        try:
            self._page.click(selector)
            return {"status": "success", "selector": selector}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def fill_form(self, selector: str, text: str) -> Dict[str, Any]:
        """Fill a form field."""
        if not self._page:
            return {"status": "error",
                    "error": "No page open — call navigate first"}
        try:
            self._page.fill(selector, text)
            return {"status": "success", "selector": selector}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def screenshot(self, path: str = "/tmp/screenshot.png") -> Dict[str, Any]:
        """Take screenshot of the current page and save to path."""
        if not _PLAYWRIGHT_AVAILABLE:
            return {"status": "error", "error": "playwright not installed"}
        if not self._page:
            return {"status": "error",
                    "error": "No page open — call navigate first"}
        try:
            self._page.screenshot(path=path)
            return {"status": "success", "path": path}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def close(self) -> None:
        """Close browser and release all resources."""
        try:
            if self._page:
                self._page.close()
                self._page = None
        except Exception:
            pass
        try:
            if self.browser:
                self.browser.close()
                self.browser = None
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception:
            pass

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _ensure_browser(self, headless: bool = True) -> None:
        """Start Playwright + Chromium if not already running."""
        if self.browser is not None:
            return
        self.playwright = sync_playwright().start()
        self.browser    = self.playwright.chromium.launch(headless=headless)


# ── Module-level singleton ─────────────────────────────────────────────────────
# ToolRegistry imports BrowserTool and instantiates it directly:
#   browser = BrowserTool()
# This module singleton is used when the file is loaded dynamically via
# ToolFactory.load_tool(), which expects a module-level `tool_instance`.

tool_instance = BrowserTool()