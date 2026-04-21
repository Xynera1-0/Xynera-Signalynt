"""Reddit via PRAW — community language, pain points, raw sentiment."""
from app.tools.base import ToolResult
from app.core.config import get_settings

settings = get_settings()


async def reddit_search(query: str, subreddits: list[str] | None = None, limit: int = 20, sort: str = "relevance") -> list[ToolResult]:
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        return [ToolResult(tool_name="reddit_praw", content="", error="Reddit credentials not configured")]

    import asyncio
    import praw

    def _fetch() -> list[dict]:
        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        sub_string = "+".join(subreddits) if subreddits else "all"
        posts = []
        for submission in reddit.subreddit(sub_string).search(query, sort=sort, limit=limit):
            top_comments = []
            submission.comments.replace_more(limit=0)
            for c in submission.comments[:5]:
                if hasattr(c, "body"):
                    top_comments.append(c.body[:200])
            posts.append({
                "title": submission.title,
                "url": f"https://reddit.com{submission.permalink}",
                "subreddit": str(submission.subreddit),
                "score": submission.score,
                "selftext": (submission.selftext or "")[:500],
                "top_comments": top_comments,
                "created_utc": submission.created_utc,
            })
        return posts

    try:
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(None, _fetch)
    except Exception as e:
        return [ToolResult(tool_name="reddit_praw", content="", error=str(e))]

    results = []
    for p in posts:
        from app.tools.implementations.tavily import _estimate_recency
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(p["created_utc"], tz=timezone.utc).isoformat()
        recency = _estimate_recency(dt)
        body = p["selftext"]
        comments_text = "\n".join(f"Comment: {c}" for c in p["top_comments"])
        content = f"{p['title']}\n{body}\n{comments_text}".strip()
        results.append(ToolResult(
            tool_name="reddit_praw",
            source_url=p["url"],
            source_name=f"r/{p['subreddit']} — {p['title'][:60]}",
            content=content,
            quote=body[:300] if body else p["title"],
            recency=recency,
            metadata={"subreddit": p["subreddit"], "score": p["score"], "query": query},
        ))
    return results
