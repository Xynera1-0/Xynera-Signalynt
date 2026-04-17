import importlib
import json
import os
from pathlib import Path

from content_generation_agent import ContentAgentPool


def _load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    env_file = backend_root / ".env"
    _load_env_file(env_file)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing GOOGLE_API_KEY. Add it to backend/.env as GOOGLE_API_KEY=your_key"
        )

    try:
        genai = importlib.import_module("google.generativeai")
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency google-generativeai. Install it with: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3-flash-preview")
    agent = ContentAgentPool(model)

    input_data = {
        "audience": "University students",
        "goal": "Promote AI Hackathon",
        "tone": "Exciting and modern",
        "platform": "Flyer",
        "insights": "AI agents and automation are trending",
    }

    result = agent.run(input_data)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()