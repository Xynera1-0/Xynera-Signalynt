import json
from typing import Dict, Any


class ContentAgentPool:
    def __init__(self, llm):
        self.llm = llm

    # ---------------- CONTENT AGENT ----------------
    def content_agent(self, input_data: Dict[str, Any]) -> Dict:
        prompt = f"""
You are an elite marketing strategist and conversion copywriter.

Your goal is to create HIGH-CONVERTING, NON-GENERIC marketing content.

INPUT:
{json.dumps(input_data, indent=2)}

RULES:
- Do NOT use generic phrases like "join now" without context
- Be specific to the audience
- Use emotional + logical appeal
- Keep it concise but impactful
- Make it feel real and modern

TASK:
1. Create 3 DISTINCT headlines (different angles: emotional, benefit-driven, curiosity)
2. Write a short persuasive body (max 60 words)
3. Create a strong, specific CTA
4. Generate 3 variations:
   - emotional (exciting, energetic)
   - professional (clear, value-focused)
   - minimal (short + punchy)
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

    # ---------------- DESIGN AGENT ----------------
    def design_agent(self, content: Dict) -> Dict:
        prompt = f"""
You are a world-class graphic designer.

Your job is to transform content into a visually compelling flyer/banner.

CONTENT:
{json.dumps(content, indent=2)}

RULES:
- Be specific (no vague terms like "nice colors")
- Ensure modern, trendy design
- Match visuals with target audience psychology

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

    # ---------------- CRITIQUE AGENT ----------------
    def critique_agent(self, content: Dict) -> Dict:
        prompt = f"""
You are a senior growth marketer and conversion analyst.

CONTENT:
{json.dumps(content, indent=2)}

TASK:
1. Evaluate each variation (emotional, professional, minimal)
2. Score each (1-10) based on:
   - clarity
   - engagement
   - conversion potential
3. Select the BEST version
4. Explain WHY it is best (short)
5. Improve it further into a FINAL HIGH-CONVERTING version

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

    # ---------------- MAIN PIPELINE ----------------
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        print("🚀 Running Competition-Level Content Agent System...")

        content = self.content_agent(input_data)
        design = self.design_agent(content)
        critique = self.critique_agent(content)

        return {
            "content": content,
            "design": design,
            "critique": critique
        }

    # ---------------- LLM CALL ----------------
    def _call_llm(self, prompt: str) -> Dict:
        try:
            response = self.llm.generate_content(prompt)
            text = response.text.strip()

            # Try parsing JSON safely
            return json.loads(text)
        except Exception:
            return {
                "error": "Parsing failed",
                "raw_output": text if 'text' in locals() else "No response"
            }