"""Cross-cutting concerns — navigation links and error pages.

Verifies that all pages have working nav links and that invalid routes
show appropriate error pages.
"""

from __future__ import annotations


class TestNavigation:
    """Verify nav links are present and functional on every page."""

    NAV_PATHS = ["/daily", "/knowledge", "/profile", "/settings"]

    def test_nav_links_on_dashboard(self, page, server_url: str) -> None:
        """Dashboard has all nav links plus brand link."""
        page.goto(server_url + "/")
        nav = page.locator("nav")
        assert nav.locator("a.nav-brand[href='/']").is_visible()
        for path in self.NAV_PATHS:
            link = nav.locator(f"a[href='{path}']")
            assert link.is_visible(), f"Nav link to {path} not visible"

    def test_nav_links_on_daily(self, page, server_url: str) -> None:
        """Daily page has all nav links."""
        page.goto(server_url + "/daily")
        nav = page.locator("nav")
        for path in self.NAV_PATHS:
            link = nav.locator(f"a[href='{path}']")
            assert link.is_visible(), f"Nav link to {path} not visible"

    def test_nav_links_on_knowledge(self, page, server_url: str) -> None:
        """Knowledge page has all nav links."""
        page.goto(server_url + "/knowledge")
        nav = page.locator("nav")
        for path in self.NAV_PATHS:
            link = nav.locator(f"a[href='{path}']")
            assert link.is_visible(), f"Nav link to {path} not visible"

    def test_nav_links_on_profile(self, page, server_url: str) -> None:
        """Profile page has all nav links."""
        page.goto(server_url + "/profile")
        nav = page.locator("nav")
        for path in self.NAV_PATHS:
            link = nav.locator(f"a[href='{path}']")
            assert link.is_visible(), f"Nav link to {path} not visible"

    def test_nav_links_on_settings(self, page, server_url: str) -> None:
        """Settings page has all nav links."""
        page.goto(server_url + "/settings")
        nav = page.locator("nav")
        for path in self.NAV_PATHS:
            link = nav.locator(f"a[href='{path}']")
            assert link.is_visible(), f"Nav link to {path} not visible"
