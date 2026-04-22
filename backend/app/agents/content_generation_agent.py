import json
import re
from typing import Any, Dict

# ── Content-type detection ─────────────────────────────────────────────────────

_TYPE_KEYWORDS: dict[str, list[str]] = {
    "email":    ["email", "newsletter", "outreach", "cold email", "follow-up", "follow up", "drip", "inbox"],
    "post":     ["post", "linkedin", "twitter", "instagram", "thread", "social", "facebook", "tiktok", "caption", "short-form", "short form"],
    "slogan":   ["slogan", "tagline", "catchphrase", "motto", "brand line", "one-liner", "taglines", "slogans"],
    "strategy": ["strategy", "plan", "brief", "positioning", "roadmap", "go-to-market", "gtm", "playbook", "marketing plan"],
    "blog":     ["blog", "article", "long-form", "long form", "content piece", "write up", "writeup"],
    "flyer":    ["flyer", "banner", "poster", "visual", "infographic", "graphic", "ad", "advertisement"],
}

_JSON_SCHEMAS: dict[str, str] = {
    "flyer": """{
  "headlines": ["", "", ""],
  "body": "",
  "cta": "",
  "variations": {"emotional": "", "professional": "", "minimal": ""},
  "platform_output": ""
}""",
    "email": """{
  "subject_lines": ["", "", ""],
  "preview_text": "",
  "body": {
    "opening": "",
    "value_proposition": "",
    "social_proof": "",
    "closing": ""
  },
  "cta": "",
  "ps_line": "",
  "variations": {"direct": "", "story_led": "", "question_led": ""}
}""",
    "post": """{
  "platform": "",
  "posts": [
    {"angle": "hook",    "copy": "", "hashtags": []},
    {"angle": "insight", "copy": "", "hashtags": []},
    {"angle": "cta",     "copy": "", "hashtags": []}
  ],
  "best_post": "",
  "thread_version": ""
}""",
    "slogan": """{
  "slogans": ["", "", "", "", ""],
  "rationale": ["", "", "", "", ""],
  "best_slogan": "",
  "why": ""
}""",
    "strategy": """{
  "target_audience": {"primary": "", "secondary": "", "psychographic": ""},
  "positioning": "",
  "key_messages": ["", "", ""],
  "channel_mix": [{"channel": "", "rationale": "", "priority": ""}],
  "90_day_plan": [{"phase": "", "actions": [], "success_metric": ""}],
  "risks": [""],
  "quick_wins": [""]
}""",
    "blog": """{
  "title": "",
  "meta_description": "",
  "outline": [{"section": "", "key_points": []}],
  "intro": "",
  "conclusion": "",
  "cta": ""
}""",
}

_TASKS: dict[str, str] = {
    "flyer":    "Create 3 distinct headlines, body copy of 35–50 words, a specific CTA, 3 short variations (emotional / professional / minimal), and a formatted platform_output.",
    "email":    "Write an outreach email with 3 subject lines, preview text, structured body (opening, value_proposition, social_proof, closing), a CTA, a P.S. line, and 3 opening variations (direct / story_led / question_led).",
    "post":     "Write 3 social-media posts, each a different angle (hook / insight / cta), with relevant hashtags. Identify the best post and write a multi-part thread version.",
    "slogan":   "Generate 5 distinct slogans/taglines, give the rationale for each, and identify the best one with a one-sentence reason.",
    "strategy": "Produce a go-to-market strategy: audience breakdown, positioning statement, 3 key messages, channel mix with priorities, a 90-day phased action plan, risks, and quick wins.",
    "blog":     "Produce a complete blog article: title, meta description, section-by-section outline with key points, full intro paragraph, conclusion, and CTA.",
}


def _detect_content_type(input_data: Dict[str, Any]) -> str:
    text = " ".join([
        str(input_data.get("prompt", "")),
        str(input_data.get("platform", "")),
        str(input_data.get("goal", "")),
    ]).lower()
    for content_type, keywords in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return content_type
    return "flyer"


# ── Agent pool ─────────────────────────────────────────────────────────────────

class ContentAgentPool:
    def __init__(self, llm):
        self.llm = llm

    # ── Core agents ────────────────────────────────────────────────────────────

    def content_agent(self, input_data: Dict[str, Any], content_type: str) -> Dict:
        brief = (
            input_data.get("prompt")
            or input_data.get("brief")
            or input_data.get("goal")
            or ""
        )
        prompt = f"""You are an elite marketing strategist and conversion copywriter.

Create output that is tightly tied to the primary brief. Do not invent a different offer, audience, or angle.

INPUT:
{json.dumps(input_data, indent=2)}

PRIMARY BRIEF:
{brief}

RULES:
- Stay tightly focused on the primary brief.
- Keep responses concise and directly relevant.
- No generic filler, no unrelated marketing advice.
- Do not repeat the same idea in different words.
- If the brief is short, infer only the minimum context needed.

CONTENT TYPE: {content_type.upper()}

TASK:
{_TASKS[content_type]}

OUTPUT STRICTLY IN JSON (no markdown, no explanation):
{_JSON_SCHEMAS[content_type]}
"""
        return self._call_llm(prompt)

    def design_agent(self, content: Dict, content_type: str) -> Dict:
        """Only runs for visual/print types (flyer, post)."""
        if content_type not in ("flyer",):
            return {}
        prompt = f"""You are a world-class graphic designer.

Transform the following content into a visually compelling {content_type}.

CONTENT:
{json.dumps(content, indent=2)}

RULES:
- Use specific HEX codes for colours.
- Name exact fonts with sizes and weights.
- Describe layout with grid / spacing details.
- Match the visual mood to the target audience.

OUTPUT STRICTLY IN JSON:
{{
  "color_palette": "",
  "typography": "",
  "layout": "",
  "visual_elements": ""
}}
"""
        return self._call_llm(prompt)

    def critique_agent(self, content: Dict, content_type: str) -> Dict:
        has_variations = content_type in ("flyer", "email", "post")

        if has_variations:
            prompt = f"""You are a senior growth marketer and conversion analyst.

CONTENT ({content_type.upper()}):
{json.dumps(content, indent=2)}

TASK:
1. Evaluate the variations present in the content.
2. Score each from 1–10 (clarity, engagement, conversion potential).
3. Select the best version and explain why in one sentence.
4. Rewrite it as a final, polished, high-converting version.

OUTPUT STRICTLY IN JSON:
{{
  "scores": {{}},
  "best_version": "",
  "reason": "",
  "final_output": ""
}}
"""
        else:
            prompt = f"""You are a senior growth marketer and conversion analyst.

CONTENT ({content_type.upper()}):
{json.dumps(content, indent=2)}

Review this output. Score it 1–10, list what works, what is weak, and rewrite the most important section as a final improved version.

OUTPUT STRICTLY IN JSON:
{{
  "score": 0,
  "strengths": [""],
  "weaknesses": [""],
  "final_output": ""
}}
"""
        return self._call_llm(prompt)

    # ── Orchestrator ───────────────────────────────────────────────────────────

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        content_type = _detect_content_type(input_data)
        print(f"Running content generation agent... type={content_type}")

        content = self.content_agent(input_data, content_type)
        design = self.design_agent(content, content_type)
        critique = self.critique_agent(content, content_type)

        result: Dict[str, Any] = {
            "content_type": content_type,
            "content": content,
            "critique": critique,
        }
        if design:
            result["design"] = design
        return result

    # ── LLM wrapper ────────────────────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> Dict:
        text = ""
        try:
            response = self.llm.generate_content(prompt)
            text = (response.text or "").strip()
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)

            return json.loads(text)
        except Exception:
            return {
                "error": "Parsing failed",
                "raw_output": text if text else "No response",
            }