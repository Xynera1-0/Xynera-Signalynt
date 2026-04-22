"""
Playwright driver — JS-heavy fallback scraper.
Used for: BigSpy, Google Ads Transparency, LinkedIn Ad Library (non-API), dynamic SPAs.
Requires: playwright install chromium (run once on deployment).
"""
from app.tools.base import ToolResult


async def playwright_scrape(url: str, wait_selector: str | None = None, timeout_ms: int = 15000) -> ToolResult:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return ToolResult(tool_name="playwright", source_url=url, content="", error="playwright not installed")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
        page = await context.new_page()
        try:
            await page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=timeout_ms)
            content = await page.inner_text("body")
            title = await page.title()
        except Exception as e:
            return ToolResult(tool_name="playwright", source_url=url, content="", error=str(e))
        finally:
            await browser.close()

    return ToolResult(
        tool_name="playwright",
        source_url=url,
        source_name=title or _domain(url),
        content=content[:4000],
        quote=content[:300] if content else None,
        recency="24h",
        metadata={"url": url},
    )


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return url
