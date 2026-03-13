import os
import json
import base64
from typing import Dict, Any, Optional
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-nano")

SYSTEM_PROMPT = """You are a careful software engineer.
Output ONLY valid JSON (no markdown, no commentary).

Schema:
{
  "summary": "<short summary>",
  "files": [
    {"path": "<repo-relative path>", "content_b64": "<BASE64 of full UTF-8 file content>"},
    ...
  ]
}

Rules:
- content_b64 MUST be base64(utf-8 full file content).
- Do NOT use triple quotes.
- Keep changes small and focused.
- Follow the Issue acceptance criteria exactly.
"""

def generate_file_edits(
    issue_title: str,
    issue_body: str,
    repo_files: Dict[str, str],
    ci_feedback: Optional[str] = None
) -> Dict[str, Any]:
    files_block = "\n\n".join([f"--- FILE: {p} ---\n{c}" for p, c in repo_files.items()])
    feedback_block = f"\n\nCI FEEDBACK:\n{ci_feedback}\n" if ci_feedback else ""

    prompt = f"""
ISSUE TITLE:
{issue_title}

ISSUE BODY:
{issue_body}
{feedback_block}

REPO CONTEXT:
{files_block}

Return ONLY the JSON object described in the system prompt.
"""

    # Responses API (official)
    resp = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )
    text = resp.output_text

    # Parse strict JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Attempt salvage if there is leading/trailing noise
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(text[start:end+1])