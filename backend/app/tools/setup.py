"""
Tool setup — called once at FastAPI startup.
All registrations live here. Change agents list here to re-scope a tool.
"""
from app.tools.registry import register

# Search & Web
from app.tools.implementations.tavily import tavily_search
from app.tools.implementations.exa import exa_search
from app.tools.implementations.firecrawl import firecrawl_scrape, firecrawl_crawl
from app.tools.implementations.playwright_driver import playwright_scrape
from app.tools.implementations.serpapi import serpapi_search

# Trends & News
from app.tools.implementations.pytrends import pytrends_interest
from app.tools.implementations.newsapi import newsapi_headlines

# Social & Community
from app.tools.implementations.reddit import reddit_search
from app.tools.implementations.hn_algolia import hn_search, hn_search_recent
from app.tools.implementations.youtube import youtube_search, youtube_comments

# Advertising Intelligence
from app.tools.implementations.meta_ads import meta_ad_search
from app.tools.implementations.linkedin_ads import linkedin_ad_search
from app.tools.implementations.moz import moz_domain_metrics, moz_bulk_domain_metrics

# Market Intelligence
from app.tools.implementations.patents import patent_search
from app.tools.implementations.crunchbase import crunchbase_search

# Temporal
from app.tools.implementations.temporal_utils import calendarific_events, get_platform_timing_heuristics


def setup_tool_registry() -> None:
    # ── Search ──────────────────────────────────────────────────────────────
    register("tavily_search", tavily_search,
             ["trend_scout", "spy_scout", "anthropologist", "contextual_scout", "temporal_agent", "temporal_poller"],
             "Live web search via Tavily. Returns ranked snippets with source URLs.")

    register("exa_search", exa_search,
             ["trend_scout", "spy_scout", "anthropologist", "contextual_scout", "temporal_agent"],
             "Semantic search via Exa. Best for long-form, contextually relevant results.")

    register("firecrawl_scrape", firecrawl_scrape,
             ["trend_scout", "spy_scout", "anthropologist", "contextual_scout"],
             "Scrape a URL to clean markdown. Use when you have a specific page to read.")

    register("firecrawl_crawl", firecrawl_crawl,
             ["spy_scout", "contextual_scout"],
             "Crawl a site (up to N pages). Use for competitor site analysis.")

    register("playwright_scrape", playwright_scrape,
             ["spy_scout", "anthropologist", "contextual_scout"],
             "JS-rendered page scraper. Fallback for BigSpy, Google Ads Transparency, dynamic SPAs.")

    register("serpapi_search", serpapi_search,
             ["trend_scout", "spy_scout", "contextual_scout", "temporal_agent"],
             "Google SERP data including People Also Ask. Reveals search intent signals.")

    # ── Trends & News ────────────────────────────────────────────────────────
    register("pytrends_interest", pytrends_interest,
             ["trend_scout", "contextual_scout", "temporal_agent", "temporal_poller"],
             "Google Trends interest over time and related queries.")

    register("newsapi_headlines", newsapi_headlines,
             ["trend_scout", "temporal_agent", "temporal_poller"],
             "Recent news headlines filtered by keyword. Good for PESTEL signals.")

    # ── Social & Community ───────────────────────────────────────────────────
    register("reddit_search", reddit_search,
             ["anthropologist", "temporal_poller"],
             "Reddit posts + top comments. Raw community language and pain points.")

    register("hn_search", hn_search,
             ["anthropologist", "contextual_scout", "temporal_poller"],
             "Hacker News full-text search via Algolia. Sorted by relevance → points → comments.")

    register("hn_search_recent", hn_search_recent,
             ["trend_scout", "temporal_poller"],
             "Hacker News search sorted by date, most recent first. Use for trending/emerging topics.")

    register("youtube_search", youtube_search,
             ["anthropologist"],
             "YouTube video search. Surface niche content and creator narratives.")

    register("youtube_comments", youtube_comments,
             ["anthropologist"],
             "YouTube comment threads for a video. Raw audience sentiment.")

    # ── Advertising Intelligence ─────────────────────────────────────────────
    register("meta_ad_search", meta_ad_search,
             ["spy_scout"],
             "Meta Ad Library API. Competitor ad creatives, spend ranges, demographics.")

    register("linkedin_ad_search", linkedin_ad_search,
             ["spy_scout"],
             "LinkedIn Ad Library. B2B competitor ad creative and targeting signals.")

    register("moz_domain_metrics", moz_domain_metrics,
             ["spy_scout"],
             "Moz Link Explorer: Domain Authority, Page Authority, backlink counts, spam score for a competitor domain.")

    register("moz_bulk_domain_metrics", moz_bulk_domain_metrics,
             ["spy_scout"],
             "Moz bulk domain metrics for up to 50 competitor domains in a single API call.")

    # ── Market Intelligence ───────────────────────────────────────────────────
    register("patent_search", patent_search,
             ["contextual_scout"],
             "USPTO patent search. IP filings as 12-18 month leading indicator of product direction.")

    register("crunchbase_search", crunchbase_search,
             ["contextual_scout"],
             "Crunchbase funding and company data. VC flows into adjacent categories.")

    # ── Temporal ─────────────────────────────────────────────────────────────
    register("calendarific_events", calendarific_events,
             ["temporal_agent"],
             "Cultural and public holiday calendar by country. Context for seasonal timing.")

    register("platform_timing_heuristics", get_platform_timing_heuristics,
             ["temporal_agent"],
             "Best days/times to post per social platform. Based on industry benchmarks.")
