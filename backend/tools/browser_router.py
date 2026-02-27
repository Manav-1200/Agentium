"""
browser_router.py
=================
Stateless routing helper that decides whether a URL warrants the stealth
nodriver browser or the standard Playwright browser.

Usage (agent or orchestrator code)
-----------------------------------
    from backend.tools.browser_router import should_use_stealth_browser, BrowserChoice

    choice = should_use_stealth_browser(url, hint=agent_hint)

    if choice.use_stealth:
        result = await tool_registry.execute_tool_async("nodriver_navigate", url=url)
    else:
        result = await tool_registry.execute_tool_async("desktop_browse_to", url=url)

    # The `reason` field is useful for audit logs / agent explanations:
    # choice.reason -> "domain is in stealth list (cloudflare-protected)"

Design notes
------------
- No imports from nodriver_tool or desktop_tool — zero coupling.
- All logic is pure / synchronous — trivial to unit test.
- Agents can override with an explicit `hint` ("stealth" | "playwright" | "auto").
- The STEALTH_DOMAINS list is the single place to maintain WAF-protected sites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Domains / patterns known to need stealth browsing
# ---------------------------------------------------------------------------

# Exact registered domains (subdomain-agnostic match applied below)
STEALTH_DOMAINS: frozenset[str] = frozenset({
    # Cloudflare-heavy / bot-detection
    "cloudflare.com",
    "nowsecure.nl",
    # Social / auth-gated
    "twitter.com",
    "x.com",
    "instagram.com",
    "linkedin.com",
    "facebook.com",
    "tiktok.com",
    # E-commerce with heavy bot protection
    "amazon.com",
    "nike.com",
    "ticketmaster.com",
    "stubhub.com",
    # Misc known WAF sites
    "datadome.co",
    "imperva.com",
    "akamai.com",
    "distilnetworks.com",
})

# URL path / query patterns that suggest bot-detection is active
STEALTH_PATH_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"/captcha", re.I),
    re.compile(r"/challenge", re.I),
    re.compile(r"__cf_chl", re.I),      # Cloudflare challenge param
    re.compile(r"recaptcha", re.I),
    re.compile(r"distil_r_captcha", re.I),
)

# Hint type accepted by the public API
Hint = Literal["auto", "stealth", "playwright"]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BrowserChoice:
    use_stealth: bool
    tool_name: str          # registry key to call
    reason: str
    url: str
    hint_applied: bool = False

    # Convenience: the opposite tool name, for logging
    @property
    def alternative_tool(self) -> str:
        return "nodriver_navigate" if not self.use_stealth else "desktop_browse_to"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def should_use_stealth_browser(
    url: str,
    hint: Hint = "auto",
    extra_stealth_domains: Optional[list[str]] = None,
) -> BrowserChoice:
    """
    Decide whether *url* should be opened with the stealth nodriver browser
    or the standard Playwright browser.

    Parameters
    ----------
    url
        The destination URL.  Must include a scheme (https:// / http://).
    hint
        Agent-supplied override.
        - ``"stealth"``    → always use nodriver regardless of URL
        - ``"playwright"`` → always use Playwright regardless of URL
        - ``"auto"``       → apply heuristic (default)
    extra_stealth_domains
        Caller-supplied list of additional domains to treat as stealth-required.
        Useful when an agent has discovered at runtime that a site blocks bots.

    Returns
    -------
    BrowserChoice
        ``use_stealth``  bool — True → call nodriver_navigate
        ``tool_name``    str  — registry key ready to pass to execute_tool_async
        ``reason``       str  — human-readable explanation for audit logs
        ``hint_applied`` bool — True when the hint overrode the heuristic
    """
    # ── Explicit hint overrides everything ────────────────────────────────────
    if hint == "stealth":
        return BrowserChoice(
            use_stealth=True,
            tool_name="nodriver_navigate",
            reason="caller hint: stealth",
            url=url,
            hint_applied=True,
        )
    if hint == "playwright":
        return BrowserChoice(
            use_stealth=False,
            tool_name="desktop_browse_to",
            reason="caller hint: playwright",
            url=url,
            hint_applied=True,
        )

    # ── Parse URL ─────────────────────────────────────────────────────────────
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        path_and_query = (parsed.path or "") + ("?" + parsed.query if parsed.query else "")
    except Exception:
        # Unparseable URL — default to stealth (safer)
        return BrowserChoice(
            use_stealth=True,
            tool_name="nodriver_navigate",
            reason="url parse failed — defaulting to stealth",
            url=url,
        )

    # ── Build effective stealth domain set ────────────────────────────────────
    effective_stealth = STEALTH_DOMAINS
    if extra_stealth_domains:
        effective_stealth = effective_stealth | frozenset(
            d.lower().lstrip("*.") for d in extra_stealth_domains
        )

    # ── Domain check (subdomain-aware) ────────────────────────────────────────
    hostname_lower = hostname.lower()
    for domain in effective_stealth:
        if hostname_lower == domain or hostname_lower.endswith("." + domain):
            return BrowserChoice(
                use_stealth=True,
                tool_name="nodriver_navigate",
                reason=f"domain matches stealth list ({domain})",
                url=url,
            )

    # ── Path / query pattern check ────────────────────────────────────────────
    for pattern in STEALTH_PATH_PATTERNS:
        if pattern.search(path_and_query):
            return BrowserChoice(
                use_stealth=True,
                tool_name="nodriver_navigate",
                reason=f"url contains stealth pattern ({pattern.pattern})",
                url=url,
            )

    # ── Default: standard Playwright is fine ─────────────────────────────────
    return BrowserChoice(
        use_stealth=False,
        tool_name="desktop_browse_to",
        reason="no stealth indicators detected",
        url=url,
    )


# ---------------------------------------------------------------------------
# Convenience: register a domain as stealth at runtime
# (agents can call this after receiving a 403 / bot-detection response)
# ---------------------------------------------------------------------------

_runtime_stealth_domains: set[str] = set()


def register_stealth_domain(domain: str) -> None:
    """
    Mark a domain as requiring stealth browsing for the lifetime of this process.
    Useful when an agent discovers at runtime that a site is bot-protected.

    Example
    -------
        register_stealth_domain("newsite.example.com")
        choice = should_use_stealth_browser("https://newsite.example.com/products")
        # choice.use_stealth == True
    """
    _runtime_stealth_domains.add(domain.lower().lstrip("*."))


def should_use_stealth_browser_with_runtime(
    url: str,
    hint: Hint = "auto",
) -> BrowserChoice:
    """
    Like `should_use_stealth_browser` but also consults domains registered
    via `register_stealth_domain()` at runtime.
    """
    return should_use_stealth_browser(
        url,
        hint=hint,
        extra_stealth_domains=list(_runtime_stealth_domains),
    )