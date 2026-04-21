import json
import re
from typing import Any, Dict


class ContentAgentPool:
    def __init__(self, llm):
        self.llm = llm

    def content_agent(self, input_data: Dict[str, Any]) -> Dict:
        brief = input_data.get("prompt") or input_data.get("brief") or input_data.get("goal") or ""
        prompt = f"""
You are an elite marketing strategist and conversion copywriter.

Create output that is tightly tied to the primary brief. Do not invent a different offer, audience, or angle.

INPUT:
{json.dumps(input_data, indent=2)}

PRIMARY BRIEF:
{brief}

RULES:
- Stay tightly focused on the primary brief.
- Keep the response concise and directly relevant.
- Do not use generic filler, long paragraphs, or unrelated marketing advice.
- Avoid repeating the same idea in different words.
- If the brief is short, infer only the minimum context needed.

TASK:
1. Create 3 distinct headlines tied to the brief.
2. Write a body of 35 to 50 words max.
3. Create a specific CTA.
4. Generate 3 short variations: emotional, professional, minimal.
5. Format content for platform: {input_data.get("platform", "flyer")}

OUTPUT STRICTLY IN JSON:
{{
  "headlines": ["", "", ""],
  "body": "",
  "cta": "",
  "variations": {{
    "emotional": "",
    "professional": "",
    "minimal": ""
  }},
  "platform_output": ""
}}
"""
        return self._call_llm(prompt)

    def design_agent(self, content: Dict) -> Dict:
        prompt = f"""
You are a world-class graphic designer.

Your job is to transform content into a visually compelling flyer/banner.

CONTENT:
{json.dumps(content, indent=2)}

RULES:
- Be specific.
- Ensure modern, trendy design.
- Match visuals with target audience psychology.

TASK:
Provide:
1. Color palette (with HEX or style description)
2. Typography (font style + hierarchy)
3. Layout (sections arrangement)
4. Visual elements (images, icons, style)

OUTPUT STRICTLY IN JSON:
{{
  "color_palette": "",
  "typography": "",
  "layout": "",
  "visual_elements": ""
}}
"""
        return self._call_llm(prompt)

    def critique_agent(self, content: Dict) -> Dict:
        prompt = f"""
You are a senior growth marketer and conversion analyst.

CONTENT:
{json.dumps(content, indent=2)}

TASK:
1. Evaluate each variation (emotional, professional, minimal).
2. Score each from 1 to 10 based on clarity, engagement, and conversion potential.
3. Select the best version.
4. Explain why it is best in one short sentence.
5. Improve it further into a final high-converting version.

OUTPUT STRICTLY IN JSON:
{{
  "scores": {{
    "emotional": 0,
    "professional": 0,
    "minimal": 0
  }},
  "best_version": "",
  "reason": "",
  "final_output": ""
}}
"""
        return self._call_llm(prompt)

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print("Running content generation agent...")

        content = self.content_agent(input_data)
        design = self.design_agent(content)
        critique = self.critique_agent(content)

        return {
            "content": content,
            "design": design,
            "critique": critique,
        }

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