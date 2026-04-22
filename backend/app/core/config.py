from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Application
    app_name: str = Field(default="Xynera", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")
    fallback_to_sqlite: bool = Field(default=False, alias="FALLBACK_TO_SQLITE")

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # Auth
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # LLM Providers
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    # Tool APIs — Search
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")
    firecrawl_api_key: str = Field(default="", alias="FIRECRAWL_API_KEY")
    serpapi_key: str = Field(default="", alias="SERPAPI_KEY")

    # Tool APIs — Social & Community
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="Xynera/1.0", alias="REDDIT_USER_AGENT")
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")

    # Tool APIs — News & Trends
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")

    # Tool APIs — Advertising Intelligence
    meta_access_token: str = Field(default="", alias="META_ACCESS_TOKEN")
    linkedin_access_token: str = Field(default="", alias="LINKEDIN_ACCESS_TOKEN")
    semrush_api_key: str = Field(default="", alias="SEMRUSH_API_KEY")

    # Tool APIs — SEO / Link Intelligence
    moz_access_id: str = Field(default="", alias="MOZ_ACCESS_ID")
    moz_secret_key: str = Field(default="", alias="MOZ_SECRET_KEY")

    # Tool APIs — Market Intelligence
    crunchbase_api_key: str = Field(default="", alias="CRUNCHBASE_API_KEY")
    calendarific_api_key: str = Field(default="", alias="CALENDARIFIC_API_KEY")

    # MCP
    mcp_mode: str = Field(default="mock", alias="MCP_MODE")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Orchestrator
    num_orchestrators: int = Field(default=2, alias="NUM_ORCHESTRATORS")
    orchestrator_timeout: int = Field(default=30, alias="ORCHESTRATOR_TIMEOUT")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")

    # Agent
    agent_temperature: float = Field(default=0.7, alias="AGENT_TEMPERATURE")
    agent_timeout_seconds: int = Field(default=30, alias="AGENT_TIMEOUT_SECONDS")
    confidence_threshold: float = Field(default=0.6, alias="CONFIDENCE_THRESHOLD")

    # Auth — OAuth
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")

    # BigQuery
    google_application_credentials: str = Field(default="", alias="GOOGLE_APPLICATION_CREDENTIALS")
    bigquery_project_id: str = Field(default="", alias="BIGQUERY_PROJECT_ID")
    bigquery_table_id: str = Field(default="", alias="BIGQUERY_TABLE_ID")
    porter_table_id: str = Field(default="", alias="PORTER_TABLE_ID")

    # Publishing: Zapier Webhooks
    zapier_fb_webhook: str = Field(default="", alias="ZAPIER_FB_WEBHOOK")
    zapier_li_webhook: str = Field(default="", alias="ZAPIER_LI_WEBHOOK")

    # Neo4j (knowledge base)
    neo4j_uri: str = Field(default="", alias="NEO4J_URI")
    neo4j_username: str = Field(default="", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")

    # Temporal Poller
    temporal_poller_interval_seconds: int = Field(default=900, alias="TEMPORAL_POLLER_INTERVAL_SECONDS")

    model_config = {"env_file": str(_ENV_FILE), "populate_by_name": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
