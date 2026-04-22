from pydantic import BaseModel
from typing import Any, Literal

RecencyLiteral = Literal["24h", "7d", "30d", "90d", "older"]


class ToolResult(BaseModel):
    tool_name: str
    source_url: str | None = None
    source_name: str | None = None        # Human-readable label, e.g. "Reddit r/marketing"
    content: str                          # Extracted text / structured data as string
    metadata: dict[str, Any] = {}         # timestamps, query used, page title, etc.
    error: str | None = None
    recency: RecencyLiteral = "30d"       # 24h | 7d | 30d | 90d | older
    quote: str | None = None             # Verbatim excerpt if available

    def as_markdown_link(self) -> str:
        """Returns [source_name](url) or bare source_name if no URL."""
        if self.source_url and self.source_name:
            return f"[{self.source_name}]({self.source_url})"
        return self.source_name or self.source_url or self.tool_name
