import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import error, parse, request


@dataclass
class HttpResult:
	status_code: int
	data: Dict[str, Any]


class HttpJsonClient:
	def __init__(self, timeout_seconds: int = 30):
		self.timeout_seconds = timeout_seconds

	def post_json(
		self,
		url: str,
		payload: Dict[str, Any],
		headers: Optional[Dict[str, str]] = None,
	) -> HttpResult:
		req = request.Request(
			url=url,
			data=json.dumps(payload).encode("utf-8"),
			headers=headers or {"Content-Type": "application/json"},
			method="POST",
		)

		try:
			with request.urlopen(req, timeout=self.timeout_seconds) as response:
				body = response.read().decode("utf-8")
				return HttpResult(status_code=response.getcode(), data=self._decode_json(body))
		except error.HTTPError as exc:
			body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
			return HttpResult(status_code=exc.code, data={"error": body or str(exc)})
		except error.URLError as exc:
			return HttpResult(status_code=0, data={"error": f"Connection failed: {exc.reason}"})

	def get_json(
		self,
		url: str,
		query: Optional[Dict[str, Any]] = None,
		headers: Optional[Dict[str, str]] = None,
	) -> HttpResult:
		if query:
			encoded_query = parse.urlencode({k: str(v) for k, v in query.items()})
			separator = "&" if "?" in url else "?"
			url = f"{url}{separator}{encoded_query}"

		req = request.Request(
			url=url,
			headers=headers or {"Content-Type": "application/json"},
			method="GET",
		)

		try:
			with request.urlopen(req, timeout=self.timeout_seconds) as response:
				body = response.read().decode("utf-8")
				return HttpResult(status_code=response.getcode(), data=self._decode_json(body))
		except error.HTTPError as exc:
			body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
			return HttpResult(status_code=exc.code, data={"error": body or str(exc)})
		except error.URLError as exc:
			return HttpResult(status_code=0, data={"error": f"Connection failed: {exc.reason}"})

	@staticmethod
	def _decode_json(raw: str) -> Dict[str, Any]:
		text = (raw or "").strip()
		if not text:
			return {}
		try:
			parsed = json.loads(text)
			if isinstance(parsed, dict):
				return parsed
			return {"value": parsed}
		except json.JSONDecodeError:
			return {"raw": text}


class CampaignExecutionAgent:
	def __init__(
		self,
		llm: Any,
		social_post_api_url: Optional[str] = None,
		email_post_api_url: Optional[str] = None,
		feedback_api_url: Optional[str] = None,
		api_bearer_token: Optional[str] = None,
		timeout_seconds: int = 30,
	):
		self.llm = llm
		self.http = HttpJsonClient(timeout_seconds=timeout_seconds)

		self.social_post_api_url = social_post_api_url or os.getenv("SOCIAL_POST_API_URL", "").strip()
		self.email_post_api_url = email_post_api_url or os.getenv("EMAIL_POST_API_URL", "").strip()
		self.feedback_api_url = feedback_api_url or os.getenv("FEEDBACK_API_URL", "").strip()
		self.api_bearer_token = api_bearer_token or os.getenv("PUBLISHER_API_BEARER_TOKEN", "").strip()

	def posting_strategy_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
		content_bundle = input_data.get("content_bundle", {})
		channels = input_data.get("channels", ["linkedin", "x"])
		email_recipients = input_data.get("email_recipients", [])

		prompt = f"""
You are a multi-channel campaign publishing strategist.

Create posting payloads from this campaign content.

INPUT:
{json.dumps(input_data, indent=2)}

CONTENT BUNDLE:
{json.dumps(content_bundle, indent=2)}

RULES:
- Keep each channel copy platform-native and concise
- Preserve key CTA intent
- Avoid generic filler wording
- Email body should be structured and clear

TASK:
1. Build social payloads for channels: {channels}
2. Build one email payload for recipients: {email_recipients}
3. Add metadata tags for tracking

OUTPUT STRICTLY IN JSON:
{{
  "social_posts": [
	{{
	  "channel": "linkedin",
	  "message": "",
	  "cta": "",
	  "hashtags": [""],
	  "metadata": {{"campaign_tag": ""}}
	}}
  ],
  "email_post": {{
	"subject": "",
	"body": "",
	"recipients": [""],
	"metadata": {{"campaign_tag": ""}}
  }}
}}
"""
		return self._call_llm(prompt)

	def feedback_analysis_agent(
		self,
		posting_results: Dict[str, Any],
		feedback_raw: Dict[str, Any],
	) -> Dict[str, Any]:
		prompt = f"""
You are a senior growth analyst.

Analyze campaign posting results and feedback metrics.

POSTING RESULTS:
{json.dumps(posting_results, indent=2)}

FEEDBACK RAW:
{json.dumps(feedback_raw, indent=2)}

TASK:
1. Summarize performance quality
2. Score each channel from 1 to 10
3. Highlight what worked and what failed
4. Provide concrete next actions

OUTPUT STRICTLY IN JSON:
{{
  "summary": "",
  "channel_scores": {{
	"linkedin": 0,
	"x": 0,
	"instagram": 0,
	"facebook": 0,
	"email": 0
  }},
  "insights": ["", ""],
  "next_actions": ["", "", ""]
}}
"""
		return self._call_llm(prompt)

	def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
		posting_plan = self.posting_strategy_agent(input_data)
		posting_results = self._publish_plan(posting_plan)
		feedback_raw = self._fetch_feedback(posting_results)
		feedback = self.feedback_analysis_agent(posting_results, feedback_raw)

		return {
			"posting_plan": posting_plan,
			"posting_results": posting_results,
			"feedback_raw": feedback_raw,
			"feedback": feedback,
		}

	def _publish_plan(self, posting_plan: Dict[str, Any]) -> Dict[str, Any]:
		social_posts = posting_plan.get("social_posts", [])
		email_post = posting_plan.get("email_post", {})

		social_results: List[Dict[str, Any]] = []
		for social_post in social_posts:
			social_results.append(self._post_social(social_post))

		email_result: Dict[str, Any] = {}
		recipients = email_post.get("recipients", []) if isinstance(email_post, dict) else []
		if recipients:
			email_result = self._post_email(email_post)

		return {
			"social_results": social_results,
			"email_result": email_result,
		}

	def _post_social(self, social_payload: Dict[str, Any]) -> Dict[str, Any]:
		if not self.social_post_api_url:
			return {
				"status": "skipped",
				"reason": "SOCIAL_POST_API_URL is not configured",
				"payload": social_payload,
			}

		response = self.http.post_json(
			url=self.social_post_api_url,
			payload=social_payload,
			headers=self._auth_headers(),
		)
		return {
			"status": "success" if 200 <= response.status_code < 300 else "failed",
			"status_code": response.status_code,
			"channel": social_payload.get("channel", "unknown"),
			"response": response.data,
		}

	def _post_email(self, email_payload: Dict[str, Any]) -> Dict[str, Any]:
		if not self.email_post_api_url:
			return {
				"status": "skipped",
				"reason": "EMAIL_POST_API_URL is not configured",
				"payload": email_payload,
			}

		response = self.http.post_json(
			url=self.email_post_api_url,
			payload=email_payload,
			headers=self._auth_headers(),
		)
		return {
			"status": "success" if 200 <= response.status_code < 300 else "failed",
			"status_code": response.status_code,
			"channel": "email",
			"response": response.data,
		}

	def _fetch_feedback(self, posting_results: Dict[str, Any]) -> Dict[str, Any]:
		if not self.feedback_api_url:
			return self._build_fallback_feedback(posting_results)

		query = {
			"channels": self._feedback_channels(posting_results),
		}
		response = self.http.get_json(
			url=self.feedback_api_url,
			query=query,
			headers=self._auth_headers(),
		)

		if 200 <= response.status_code < 300:
			return response.data

		return {
			"status": "failed",
			"status_code": response.status_code,
			"error": response.data,
			"fallback": self._build_fallback_feedback(posting_results),
		}

	@staticmethod
	def _feedback_channels(posting_results: Dict[str, Any]) -> str:
		channels: List[str] = []
		for item in posting_results.get("social_results", []):
			channels.append(str(item.get("channel", "unknown")))
		email_result = posting_results.get("email_result", {})
		if email_result:
			channels.append("email")
		return ",".join(channels)

	@staticmethod
	def _build_fallback_feedback(posting_results: Dict[str, Any]) -> Dict[str, Any]:
		social_results = posting_results.get("social_results", [])
		email_result = posting_results.get("email_result", {})

		channel_metrics: Dict[str, Dict[str, int]] = {}
		for index, item in enumerate(social_results):
			channel = str(item.get("channel", f"channel_{index + 1}"))
			seed = (len(channel) + index + 1) * 113
			channel_metrics[channel] = {
				"impressions": 500 + seed,
				"engagements": 30 + int(seed * 0.08),
				"clicks": 8 + int(seed * 0.02),
			}

		if email_result:
			seed = 241
			channel_metrics["email"] = {
				"deliveries": 120 + seed,
				"opens": 35 + int(seed * 0.1),
				"clicks": 6 + int(seed * 0.03),
			}

		return {
			"source": "fallback",
			"channel_metrics": channel_metrics,
		}

	def _auth_headers(self) -> Dict[str, str]:
		headers = {"Content-Type": "application/json"}
		if self.api_bearer_token:
			headers["Authorization"] = f"Bearer {self.api_bearer_token}"
		return headers

	def _call_llm(self, prompt: str) -> Dict[str, Any]:
		try:
			response = self.llm.generate_content(prompt)
			text = response.text.strip()

			try:
				return json.loads(text)
			except json.JSONDecodeError:
				pass

			if "```" in text:
				stripped = text.replace("```json", "").replace("```", "").strip()
				try:
					return json.loads(stripped)
				except json.JSONDecodeError:
					pass

			start = text.find("{")
			end = text.rfind("}")
			if start != -1 and end != -1 and start < end:
				return json.loads(text[start : end + 1])

			raise ValueError("No parseable JSON found in LLM response")
		except Exception:
			return {
				"error": "Parsing failed",
				"raw_output": text if "text" in locals() else "No response",
			}
