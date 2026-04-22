# Xynera-Signalynt — System Architecture

## Full Flow

```
User message (HTTP POST /chat/conversations/{id}/send)
    │
    ▼
routes/chat.py  ──  saves user message to Postgres messages table
    │               resolves tool_hint (research / generate_content / full_workflow)
    │
    ▼
supervisor_graph.py  ──  SupervisorState (TypedDict)
    │
    ├── planner_node
    │     • Fast-path: greetings/short messages → route = "chat" (LLM reply, no pipeline)
    │     • Parallel: reads Neo4j KB + fetches last 10 campaigns from Postgres
    │     • LLM (Groq llama-3.3-70b) classifies intent → route + plan JSON
    │     • Routes: chat | research_only | content_only | research_content |
    │               post_existing | full_campaign
    │
    ├── [route = "chat"] ──────────────────────────────────────────────────────┐
    │     chat_node: LLM with system prompt → chat_reply returned to user      │
    │                                                                           │
    ├── [route includes research] ──────────────────────────────────────────── │
    │     run_research_team ──► RESEARCH GRAPH (LangGraph subgraph)            │
    │                                                                           │
    ├── [route includes content] ──────────────────────────────────────────── │
    │     run_content_team  ──► CONTENT GRAPH (LangGraph subgraph)             │
    │                                                                           │
    └── result assembled → saved to Postgres → HTTP response to frontend       │
                                                                                │
◄───────────────────────────────────────────────────────────────────────────── ┘
```

---

## Research Graph (subgraph)

```
ResearchState flows through:

  kb_reader_node
      │  Reads Neo4j for past growth signals on this topic
      │  → state: kb_context
      ▼
  orchestrator_node  (LLM: Groq)
      │  Plans which agents to dispatch and with what scoped focus question
      │  → state: orchestrator_plan { reasoning, intent_labels, dispatches[], temporal_needed }
      ▼
  dispatch_to_agents()  ◄── conditional edge (returns list[Send] for parallel fan-out)
      │
      ├──► trend_scout          ─┐
      ├──► spy_scout            ─┤  parallel (Send)
      ├──► anthropologist       ─┤  each appends to agent_findings (operator.add)
      ├──► contextual_scout     ─┤
      └──► temporal_agent_node  ─┘
                │
                ▼ (all converge)
  synthesis_node  (LLM: Groq)
      │  3-phase: relevance audit → gap check → merge & route decision
      │  → state: synthesis_result, routing ("to_user" | "to_content_agent")
      │
      ├── [routing = "to_user"] ──► summarizer_node (LLM: Groq, JSON mode)
      │                                → state: user_report { summary, key_insights,
      │                                           gaps, confidence, sources }
      │                                → END
      │
      └── [routing = "to_content_agent"] ──► END
              (content_brief in state passed back to supervisor)
```

---

## Agent → Tool Mapping

### trend_scout
Answers: *WHY is the market moving? (PESTEL)*

| Tool | Purpose |
|------|---------|
| `tavily_search` | Live web search — news, market data, regulatory signals |
| `exa_search` | Semantic search — long-form contextually relevant articles |
| `newsapi_headlines` | Recent news by keyword — PESTEL signal detection |
| `pytrends_interest` | Google Trends — rising/falling interest cycles |
| `firecrawl_scrape` | Scrape specific URLs to clean markdown |
| `serpapi_search` | Google SERP + People Also Ask — search intent signals |

---

### spy_scout
Answers: *WHAT are competitors doing?*

| Tool | Purpose |
|------|---------|
| `meta_ad_search` | Meta Ad Library — competitor ad creatives, spend ranges |
| `linkedin_ad_search` | LinkedIn Ad Library — B2B competitor ads (falls back to Firecrawl scrape) |
| `exa_search` | Semantic search — competitor strategy articles |
| `tavily_search` | Live web search — competitor campaigns |
| `firecrawl_scrape` | Scrape competitor landing pages to clean markdown |
| `firecrawl_crawl` | Bulk-crawl competitor sites (up to N pages) |
| `playwright_scrape` | JS-rendered pages — BigSpy, Google Ads Transparency, SPAs |
| `moz_domain_metrics` | Domain Authority, Page Authority, backlink count, spam score |
| `moz_bulk_domain_metrics` | Same as above for up to 50 domains in one request |
| `serpapi_search` | Google SERP for competitor visibility |

---

### anthropologist
Answers: *WHO is the audience and what do they feel?*

| Tool | Purpose |
|------|---------|
| `reddit_search` | Community posts + top comments — raw emotional language |
| `hn_search` | Hacker News — tech practitioner sentiment |
| `youtube_search` | YouTube videos — niche creator narratives |
| `youtube_comments` | YouTube comment threads — raw audience sentiment |
| `exa_search` | Semantic search — audience research articles |
| `tavily_search` | Live web search |
| `firecrawl_scrape` | Scrape forum/community pages |
| `playwright_scrape` | JS-rendered community sites |

---

### contextual_scout
Answers: *WHAT is coming from adjacent sectors? (VC, patents, tech shifts)*

| Tool | Purpose |
|------|---------|
| `exa_search` | Semantic search — cross-sector disruption signals |
| `tavily_search` | Live web search |
| `firecrawl_scrape` | Scrape reports and white papers |
| `firecrawl_crawl` | Bulk-crawl related industry sites |
| `playwright_scrape` | JS-rendered pages |
| `serpapi_search` | Google SERP |
| `hn_search` | HN — technical early signals (6-12 months ahead of mainstream) |
| `patent_search` | USPTO patent filings — 12-18 month product direction signals |
| `crunchbase_search` | VC funding flows into adjacent categories |

---

### temporal_agent
Answers: *WHEN is the right moment? (trends, seasonality, news cycle)*

| Tool | Purpose |
|------|---------|
| `tavily_search` | Live web search |
| `exa_search` | Trending news this week |
| `pytrends_interest` | Google Trends — topic rising/falling, timeframe "now 7-d" |
| `newsapi_headlines` | News headlines — dominant news cycle detection |
| `calendarific_events` | Public holidays and cultural events by country/month |
| `serpapi_search` | SERP timing signals |
| `platform_timing_heuristics` | Best posting times per platform (LinkedIn, Instagram, etc.) |

---

## How Research Data Reaches the Content Generation Agent

The handoff from research → content is entirely through LangGraph state and Python dict passing. No database is used as the bridge.

### Step 1 — Synthesis decides routing

`synthesis_node` sets `routing = "to_content_agent"` when `ready_for_content = True` in its JSON output. This is the gate.

### Step 2 — Research graph returns `content_brief`

When `routing = "to_content_agent"`, the research graph exits at `END` **without** calling the summarizer. The `ResearchState` at that point contains:

```python
state["content_brief"]   # ContentBrief pydantic model (populated by synthesis or summarizer)
state["synthesis_result"] # full SynthesisResult with key_findings, coverage, gaps
state["agent_findings"]  # list[AgentFinding] from all parallel agents
state["orchestrator_plan"] # reasoning + intent_labels
```

### Step 3 — Supervisor extracts the brief

`run_research_team()` in `supervisor_graph.py` calls `research_graph.ainvoke()` and gets back the full final state. It stores it as:

```python
return {"research_result": result, "status": "creating_content"}
```

So `supervisor_state["research_result"]` is the entire `ResearchState` dict.

### Step 4 — Content team receives it

`run_content_team()` extracts the brief from research_result:

```python
content_brief = state.get("research_result", {}).get("content_brief") or {}
```

It then invokes the content graph with:

```python
content_input = {
    "content_brief": content_brief,   # ← from research
    "kb_context": state.get("kb_context", {}),
    "platforms": state.get("plan", {}).get("platforms", ["linkedin"]),
    "hypothesis": state.get("plan", {}).get("hypothesis", ""),
}
```

### Step 5 — Content graph uses the brief

Inside the content graph, `content_strategist_node` reads `content_brief` and formats it as JSON into its LLM prompt. The brief contains the synthesised research findings, gaps, intent labels, and confidence scores from all parallel agents.

### Current gap ⚠️ — FIXED ✅

`synthesis_node` now writes a `ContentBrief` to state when `routing = "to_content_agent"`.
`run_content_team` also has a fallback: if `content_brief` is empty it constructs one from `synthesis_result` directly.

---

## Content Graph (subgraph)

```
ContentState:

  content_strategist_node  (LLM: Groq)
      │  Reads content_brief + KB signals → defines angles, hooks, test design
      │  → state: strategy { primary_angle, test_hypothesis, hooks[], cta }
      ▼
  content_generator_node  (ContentAgentPool via GrokGenerativeModel)
      │  One LLM call per platform → base content per platform
      │  → state: base_contents { linkedin: {...}, instagram: {...} }
      ▼
  variant_builder_node  (no LLM — structural composition)
      │  Builds A/B variants from base content + strategy tones/headlines
      │  → state: variants [ { id, platform, headline, body, cta, tone, ... } ]
      ▼
  [optional] generate_flyer_image()
      │  Pollinations.ai image generation → base64 + Cloudinary upload
      ▼
  END → content_result returned to supervisor
```

---

## LLM Stack

| Priority | Provider | Model | Used via |
|---------|---------|-------|---------|
| 1 (primary) | Groq | `llama-3.3-70b-versatile` | `langchain_groq.ChatGroq` |
| 2 (fallback) | Gemini | `gemini-3-flash-preview` | `google.genai` |
| 3 (if key present) | Anthropic | Claude | `langchain_anthropic` |

`get_llm()` in `base.py` checks API keys in order: Anthropic → Groq → Gemini.
`content_generation_service.py` uses `GrokGenerativeModel` (direct HTTP to `api.groq.com/openai/v1`) with `GeminiGenerativeModel` as fallback.
